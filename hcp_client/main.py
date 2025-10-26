import socket
import threading
import queue
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable
import hcp_executor
import json
import asi1client

hcp = hcp_executor.HCPExecutor()

try:
    client = ASI1Client()
except ASI1ClientError as e:
    print(f"Error initializing ASI1Client: {e}")

messages = [
    {"role": "system", "content": "You are a helpful AI assistant that can control hardware if asked."}
]

HOST = '127.0.0.1'
PORT = 65432

def bytes_to_json(byte_string):
    """
    Convert a byte string to a Python dictionary (parsed JSON).
    Handles both UTF-8 decoding and JSON parsing errors.
    """
    try:
        # Step 1: Decode bytes to string
        decoded_str = byte_string.decode('utf-8')
        
        # Step 2: Clean up if there are stray characters (optional)
        decoded_str = decoded_str.strip()

        # Step 3: Parse JSON
        data = json.loads(decoded_str)
        return data

    except UnicodeDecodeError:
        print("Error: Could not decode bytes to UTF-8 string.")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON data — {e}")

def convert_command(device_id, command_name, command_data):
    # Map string types to Python equivalents
    type_map = {
        "int": int,
        "float": float,
        "bool": bool,
        "str": str
    }

    # Extract the description
    description = command_data.get("freetext_desc", "")

    # Build the parameter list as tuples (name, python_type)
    params = []
    for p in command_data.get("params", []):
        for k, v in p.items():
            params.append((k, type_map.get(v, str)))

    # Return your target structure
    return (
        device_id,              # fixed platform name
        command_name,                    # command name
        description,              # human description
        params                    # typed parameter list
    )

# =========================
# User-provided hooks (fill these)
# =========================

def running_tick(send_to: Callable[[tuple, bytes], None],
                 broadcast: Callable[[bytes], None],
                 list_clients: Callable[[], list[tuple]]) -> None:
    """
    Called repeatedly during RUNNING (very frequently).
    Use send_to/broadcast/list_clients from here to drive real-time behavior.
    Keep it quick/non-blocking.
    """
    try:
        response = client.chat_completion(messages)
        ai_reply = response["choices"][0]["message"]["content"].strip()
        messages.append({"role": "assistant", "content": ai_reply})
        action = json.loads(ai_reply)
        hcp.execute_action(action["target_hardware"], action["toolname"], action["command_body"])
    except ASI1ClientError as e:
        print(f"[Error] {e}")
    except Exception as e:
        print(f"[Unexpected error] {e}")
    

# =========================
# Internal plumbing
# =========================

@dataclass
class ClientEvent:
    kind: str                  # 'connect', 'data', 'disconnect', 'error'
    addr: tuple
    payload: bytes | None = None
    error: Exception | None = None

@dataclass
class Client:
    conn: socket.socket
    addr: tuple
    thread: threading.Thread
    alive: bool = field(default=True)

class State(Enum):
    STARTUP = auto()
    CONNECTING = auto()
    RUNNING = auto()

def handle_client(conn: socket.socket, addr: tuple, event_q: queue.Queue):
    event_q.put(ClientEvent('connect', addr))
    try:
        with conn:
            while True:
                data = conn.recv(4096)
                if not data:
                    event_q.put(ClientEvent('disconnect', addr))
                    break
                event_q.put(ClientEvent('data', addr, payload=data))
    except Exception as e:
        event_q.put(ClientEvent('error', addr, error=e))
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass

def start_server():
    event_q: queue.Queue[ClientEvent] = queue.Queue()
    clients: dict[tuple, Client] = {}
    clients_lock = threading.Lock()

    def accept_loop(server_sock: socket.socket):
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr, event_q), daemon=True)
            with clients_lock:
                clients[addr] = Client(conn=conn, addr=addr, thread=t, alive=True)
            t.start()

    # helpers safe to use from hooks
    def send_to(addr: tuple, data: bytes) -> None:
        with clients_lock:
            c = clients.get(addr)
            if c and c.alive:
                try:
                    c.conn.sendall(data)
                except Exception as e:
                    print(f"[!] send_to {addr} failed: {e}")

    def broadcast(data: bytes) -> None:
        with clients_lock:
            for a, c in list(clients.items()):
                if c.alive:
                    try:
                        c.conn.sendall(data)
                    except Exception as e:
                        print(f"[!] broadcast to {a} failed: {e}")

    def list_clients() -> list[tuple]:
        with clients_lock:
            return [a for a, c in clients.items() if c.alive]

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        print(f"Server listening on {HOST}:{PORT}")

        threading.Thread(target=accept_loop, args=(server,), daemon=True).start()

        # ============
        # State machine
        # ============
        state = State.STARTUP
        connecting_deadline = None

        try:
            while True:
                now = time.monotonic()

                # --- state transitions ---
                if state == State.STARTUP:
                    # Immediately go to CONNECTING and start 5s window
                    connecting_deadline = now + 25.0
                    print("[state] STARTUP -> CONNECTING (25s window)")
                    state = State.CONNECTING

                elif state == State.CONNECTING and now >= connecting_deadline:
                    print("[state] CONNECTING -> RUNNING")
                    state = State.RUNNING
                    # optional: call a hook when entering running
                    # (you can also do setup in running_tick)

                # --- event processing (common) ---
                # Use a short timeout so RUNNING gets frequent ticks.
                timeout = 0.1
                try:
                    evt = event_q.get(timeout=timeout)
                except queue.Empty:
                    evt = None

                if evt:
                    if evt.kind == 'connect':
                        print(f"[+] {evt.addr} connected")
                        if state == State.CONNECTING:
                            # Send GET_API request on startup
                            msg_json = """
                            {
                                "action": "REQUEST_HCP_DATA",
                                "payload": \{\}
                            }
                            """
                            msg = msg_json.encode()
                            send_to(evt.addr, msg)

                    elif evt.kind == 'data':
                        # Always deliver data to your handler
                        if state == State.CONNECTING:
                            json_payload = bytes_to_json(evt.payload)
                            metadata = json_payload["metadata"]
                            available_commands = json_payload["available_commands"]
                            hcp.register_device(metadata["device_id"], metadata["freetext_desc"], evt.addr)
                            for command_name, command_data in available_commands.items():
                                hcp.register_action(convert_command(metadata["device_id"], command_name, command_data))
                        elif state == State.RUNNING:
                            messages.append("Response from device: " + str(evt.payload))

                    elif evt.kind == 'disconnect':
                        print(f"[-] {evt.addr} disconnected")
                        with clients_lock:
                            c = clients.pop(evt.addr, None)
                            if c:
                                try: c.conn.close()
                                except Exception: pass

                    elif evt.kind == 'error':
                        print(f"[!] {evt.addr} error: {evt.error}")
                        with clients_lock:
                            c = clients.pop(evt.addr, None)
                            if c:
                                try: c.conn.close()
                                except Exception: pass

                # --- per-state behavior ---
                if state == State.RUNNING:
                    # Give you a frequent, lightweight hook to drive logic
                    running_tick(send_to, broadcast, list_clients)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            with clients_lock:
                for c in clients.values():
                    try: c.conn.shutdown(socket.SHUT_RDWR)
                    except Exception: pass
                    try: c.conn.close()
                    except Exception: pass
            # server socket closed by context manager

if __name__ == "__main__":
    start_server()
