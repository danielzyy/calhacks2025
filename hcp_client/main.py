import socket
import threading
import queue
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable
import hcp_executor
from hcp_executor import Client
import json
from asi1client import ASI1Client, ASI1ClientError
import re
import argparse
import requests
import uuid

UI_URL = "http://127.0.0.1:5000"  # UI base address (change if needed)
USE_UI = False  # will be set by argparse

# =========================
# Voice support (optional)
# =========================
USE_VOICE = False
recognizer = None
mic = None
try:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", action="store_true", help="Use voice input instead of keyboard")
    parser.add_argument("--ui", action="store_true", help="Enable UI updates to Flask dashboard")
    args = parser.parse_args()
    USE_VOICE = args.voice
    USE_UI = args.ui
    if USE_VOICE:
        import speech_recognition as sr
        import keyboard
        recognizer = sr.Recognizer()
        mic = sr.Microphone()
except Exception as e:
    print(f"[!] Voice support disabled: {e}")
    
def listen_to_speech() -> str:
    if not USE_VOICE or not recognizer or not mic:
        return ""
    print("\n🎙️ Hold SPACE to talk... (release when done)")
    keyboard.wait("space")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        print("🎧 Listening... (release space when finished)")
        audio = recognizer.listen(source)
    while keyboard.is_pressed("space"):
        time.sleep(0.05)
    print("🧠 Processing speech...")
    try:
        text = recognizer.recognize_google(audio)
        print(f"You said: {text}")
        return text
    except sr.UnknownValueError:
        print("❌ Could not understand audio.")
    except sr.RequestError:
        print("⚠️ Speech recognition service unavailable.")
    return ""

hcp = hcp_executor.HCPExecutor()

try:
    client = ASI1Client()
except ASI1ClientError as e:
    print(f"Error initializing ASI1Client: {e}")

messages = []

HOST = '127.0.0.1'
PORT = 9000

MAX_MALFORMED_MESSAGE_RETRY = 3

def extract_dashed_section(text):
    """
    Looks for a section delimited by five dashes (-----) at the start and end.
    Returns:
        inside: content between the dashes (exclusive)
        outside: everything else
        found: boolean indicating if section existed
    """
    # Regex to match content between two sets of 5+ dashes
    pattern = r"-----\s*(.*?)\s*-----"
    match = re.search(pattern, text, re.DOTALL)

    if match:
        inside = match.group(1).strip()
        # everything before + after the section
        outside = (text[:match.start()] + text[match.end():]).strip()
        return inside, outside, True
    else:
        return None, text.strip(), False
    
def extract_main_json_with_context(text):
    """
    Extract the first JSON object (dict) from a string.
    Returns a tuple: (parsed_json or None, text_outside_json, json_exists_bool)
    """
    brace_count = 0
    current_json = ""
    in_json = False
    outside_text = ""
    json_found = False

    for char in text:
        if char == '{':
            if not in_json:
                in_json = True
                current_json = ""
            brace_count += 1
        if in_json:
            current_json += char
        else:
            outside_text += char
        if char == '}':
            if in_json:
                brace_count -= 1
                if brace_count == 0:
                    # Attempt to parse JSON
                    try:
                        parsed_json = json.loads(current_json)
                        json_found = True
                        return parsed_json, outside_text, True
                    except json.JSONDecodeError:
                        return None, text, False  # Invalid JSON

    # No JSON found
    return None, text, False

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
# Internal plumbing
# =========================

@dataclass
class ClientEvent:
    kind: str                  # 'connect', 'data', 'disconnect', 'error'
    addr: tuple
    payload: bytes | None = None
    error: Exception | None = None

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
    ready_for_user_input = False
    retryCount = 0
    event_q: queue.Queue[ClientEvent] = queue.Queue()
    clients: dict[tuple, Client] = {}
    clients_lock = threading.Lock()

    def running_tick() -> None:
        nonlocal ready_for_user_input, retryCount
        """
        Called repeatedly during RUNNING (very frequently).
        Use send_to/broadcast/list_clients from here to drive real-time behavior.
        Keep it quick/non-blocking.
        """
        if ready_for_user_input:
            try:
                if USE_VOICE:
                    user_input = listen_to_speech()
                else:
                    user_input = input("You: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...")
                exit(0)

            if user_input.lower() in {"exit", "quit"}:
                print("Goodbye!")
                exit(0)

            if not user_input:
                return
            
            messages.append({"role": "user", "content": user_input})
            ready_for_user_input = False
        else:
            # Add user message to history
            try:
                response = client.chat_completion(messages)
                ai_reply = response["choices"][0]["message"]["content"].strip()
                messages.append({"role": "assistant", "content": ai_reply})
                action, outside, isCommand = extract_main_json_with_context(ai_reply)
                print(f"AI: {outside}\n")
                if not isCommand:
                    ready_for_user_input = True
                    return
                with clients_lock:
                    if USE_UI:
                        req_id = str(uuid.uuid4())
                        try:
                            requests.post(f"{UI_URL}/api/log_request", json={
                                "request_id": req_id,
                                "target_hardware": action["target_hardware"],
                                "toolname": action["toolname"],
                                "command_body": action["command_body"]
                            }, timeout=0.5)
                        except Exception as e:
                            print(f"[UI] Failed to log request: {e}")
        
                    if (False == hcp.execute_action(action["target_hardware"], action["toolname"], action["command_body"])):
                        if retryCount < MAX_MALFORMED_MESSAGE_RETRY:
                            retryCount += 1
                            print(f"AI: Malformed command JSON. Retrying ({retryCount}/{MAX_MALFORMED_MESSAGE_RETRY})...\n")
                            messages.append({"role": "user", "content": "ERROR: Malformed message. Check your message structure against the system prompt and try again without prompting the user."})
                        else:
                            messages.append({"role": "user", "content": "ERROR: Message is continously malformed. Stop retrying and instructor the user that you were unable to send a command and that they should retry."})
                    else:
                        retryCount = 0
            except ASI1ClientError as e:
                print(f"[Error] {e}")
            except Exception as e:
                print(f"[Unexpected error] {e}")
    

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
                    connecting_deadline = now + 3.0
                    print("[state] STARTUP -> CONNECTING (3s window)")
                    state = State.CONNECTING

                elif state == State.CONNECTING and now >= connecting_deadline:
                    print("[state] CONNECTING -> RUNNING")
                    state = State.RUNNING
                    messages.append(
                        {"role": "system", "content": "You are controlling these following pieces of hardware with the following actions:\n\n" + hcp.get_all_devices_llm_context_str() + "\n\nI will give you commands and you can call any of these tools to fulfill them. If you need more info ask me. Whenever you want to call a tool you should put a ----- at the start and end of the call. the call should be a properly formatted json with a \"target_hardware\", \"toolname\" and \"command_body\" entry where command body is a nested json. If you want to make multiple commands in a row make them one by one and wait for a status response back from the hardware!"}
                    )
                    ready_for_user_input = True

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
                                "payload": {}
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
                            hcp.register_device(metadata["device_id"], metadata["freetext_desc"], evt.addr, clients.get(evt.addr))
                            
                            if USE_UI:
                                try:
                                    requests.post(f"{UI_URL}/api/register_device", json={
                                        "device_id": metadata["device_id"],
                                        "freetext_desc": metadata.get("freetext_desc", ""),
                                        "addr": list(evt.addr),
                                        "available_commands": available_commands
                                    }, timeout=0.5)
                                except Exception as e:
                                    print(f"[UI] Device registration failed: {e}")
                            
                            for command_name, command_data in available_commands.items():
                                hcp.register_action(*convert_command(metadata["device_id"], command_name, command_data))
                        elif state == State.RUNNING:
                            messages.append({"role": "user", "content": "Response from device: " + str(evt.payload)})
                            if USE_UI:
                                try:
                                    requests.post(f"{UI_URL}/api/log_response", json={
                                        "request_id": str(uuid.uuid4()),
                                        "target_hardware": str(evt.addr),
                                        "status": "ok",
                                        "payload": evt.payload.decode("utf-8", errors="ignore")
                                    }, timeout=0.5)
                                except Exception as e:
                                    print(f"[UI] Failed to log device response: {e}")

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
                    running_tick()

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
