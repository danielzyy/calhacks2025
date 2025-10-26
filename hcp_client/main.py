import socket
import threading
import queue
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable

HOST = '127.0.0.1'
PORT = 65432

# =========================
# User-provided hooks (fill these)
# =========================

def get_connecting_message(addr: tuple) -> bytes | None:
    """
    Called during CONNECTING when a new client connects.
    Return the bytes you want to send immediately to this client,
    or None to send nothing.
    """
    # Example:
    # return f"welcome {addr[0]}:{addr[1]}".encode()
    return f"GET_API".encode()

def on_client_data(addr: tuple, data: bytes) -> None:
    """
    Called whenever any client sends data (in CONNECTING and RUNNING).
    Do whatever you want with data here.
    """
    # Example:
    if data.startswith(b"API_SCHEMA"):
        print("API SCHEMA received")
        # fill array of available commands
    elif data == b"COMPLETE":
        print("Action complete confirmation received")
        # let MCP know action is done
    print(f"[hook] from {addr}: {data!r}")
    pass

def running_tick(send_to: Callable[[tuple, bytes], None],
                 broadcast: Callable[[bytes], None],
                 list_clients: Callable[[], list[tuple]]) -> None:
    """
    Called repeatedly during RUNNING (very frequently).
    Use send_to/broadcast/list_clients from here to drive real-time behavior.
    Keep it quick/non-blocking.
    """
    # Example (no-op):
    # for a in list_clients():
    #     send_to(a, b"ping")
    pass

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
                            # Send your connecting message (if any)
                            msg = get_connecting_message(evt.addr)
                            if msg:
                                send_to(evt.addr, msg)

                    elif evt.kind == 'data':
                        # Always deliver data to your handler
                        on_client_data(evt.addr, evt.payload)

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
