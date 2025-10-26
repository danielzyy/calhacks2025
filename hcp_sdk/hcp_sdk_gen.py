#!/usr/bin/env python3
"""
HCP SDK Generator (TCP Client Edition)
-------------------------------------
Usage:
    python hcp_sdk_gen.py --input examples/robot_arm.json --output ./out --host 127.0.0.1 --port 9000
"""

import os
import json
import argparse
from typing import Dict, Any
from pathlib import Path
import pprint
import queue

# JSON Schema validation library
try:
    from jsonschema import validate, ValidationError
except ImportError:
    raise ImportError("Please install jsonschema: pip install jsonschema")


# ---------------- JSON Schema Validation ----------------
def validate_hcp_json_schema(data: Dict[str, Any], schema_path: str) -> None:
    """Validate input JSON against a JSON Schema."""
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        raise ValueError(f"JSON Schema validation error: {e.message}")


# ---------------- Code Generation ----------------
def generate_device_code(data: Dict[str, Any], host: str, port: int) -> str:
    meta = data["metadata"]
    device_id = meta["device_id"]
    desc = meta["freetext_desc"]
    commands = data["available_commands"]

    code_lines = [
        f'"""{device_id}_hcp_support.py — Auto-generated HCP SDK TCP Client"""',
        "import json",
        "import socket",
        "import threading",
        "import time",
        "import queue",
        "",
        f"DEVICE_ID = '{device_id}'",
        f'DEVICE_DESC = """{desc}"""',
        f'HCP_HOST = "{host}"',
        f"HCP_PORT = {port}",
        "",
        "# Original JSON definition",
        "HCP_DEVICE_JSON = " + pprint.pformat(data, indent=2),
        "",
        "class HCPClient:",
        "    def __init__(self):",
        "        self.host = HCP_HOST",
        "        self.port = HCP_PORT",
        "        self.sock = None",
        "        self.running = False",
        "        self.events = queue.Queue()  # incoming (action, payload)",
        "        self._responses = queue.Queue()  # outgoing responses",
        "",
        "    def start(self):",
        "        if not self.running:",
        "            self.running = True",
        "            threading.Thread(target=self._connect_loop, daemon=True).start()",
        "            print(f'[OK] HCPClient started for {self.host}:{self.port}')",
        "",
        "    def send_response(self, action, body):",
        "        '''Thread-safe: enqueue a response to send back to HCP'''",
        "        self._responses.put({'action': action, 'body': body})",
        "",
        "    def _connect_loop(self):",
        "        while self.running:",
        "            try:",
        "                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)",
        "                self.sock.connect((self.host, self.port))",
        "                print(f'[OK] Connected to HCP host {self.host}:{self.port}')",
        "                self._listen_loop()",
        "            except (ConnectionRefusedError, OSError):",
        "                print('[WARN] Connection failed. Retrying in 3s...')",
        "                time.sleep(3)",
        "",
        "    def _listen_loop(self):",
        "        while self.running:",
        "            try:",
        "                data = self.sock.recv(4096).decode('utf-8')",
        "                if not data:",
        "                    print('[INFO] Disconnected, reconnecting...')",
        "                    return",
        "                message = json.loads(data)",
        "                action = message.get('action')",
        "                payload = message.get('payload', {})",
        "",
        "                if action == 'REQUEST_HCP_DATA':",
        "                    self._send_json(HCP_DEVICE_JSON)",
        "                else:",
        "                    # push incoming actions to main thread queue",
        "                    self.events.put((action, payload))",
        "                    # send response queued by main thread",
        "                    resp = self._responses.get()",
        "                    self._send_json(resp)",
        "",
        "            except Exception as e:",
        "                print('[ERROR]', e)",
        "                time.sleep(1)",
        "",
        "    def _send_json(self, obj):",
        "        try:",
        "            self.sock.sendall(json.dumps(obj).encode('utf-8'))",
        "        except Exception as e:",
        "            print('[ERROR] Failed to send JSON:', e)",
        "",
        "    def stop(self):",
        "        self.running = False",
        "        if self.sock:",
        "            try: self.sock.close()",
        "            except: pass",
        "        print('[OK] HCPClient stopped.')",
        "",
        "if __name__ == '__main__':",
        "    client = HCPClient()",
        "    client.start()",
        "    try:",
        "        while True:",
        "            try:",
        "                action, payload = client.events.get_nowait()",
        "                print(f'[EVENT] {action}: {payload}')",
        "",
        "                # Example: automatically send back a dummy response",
        "                client.send_response(action, {'status': 'ok', 'message': f'Handled {action}'})",
        "",
        "            except queue.Empty:",
        "                pass",
        "            time.sleep(0.01)",
        "    except KeyboardInterrupt:",
        "        client.stop()",
    ]

    return "\n".join(code_lines)


# ---------------- CLI Entry Point ----------------
def main():
    parser = argparse.ArgumentParser(description="Generate HCP TCP Client SDK from JSON spec.")
    parser.add_argument("--input", required=True, help="Path to input JSON spec.")
    parser.add_argument("--output", default=".", help="Output directory (default: current).")
    parser.add_argument("--host", required=True, help="HCP server host to connect to.")
    parser.add_argument("--port", required=True, type=int, help="HCP server port to connect to.")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.output)
    schema_path = Path(__file__).parent / "hcp_sdk_schema.json"

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate JSON schema
    validate_hcp_json_schema(data, schema_path)

    # Generate client SDK code
    code = generate_device_code(data, args.host, args.port)
    device_id = data["metadata"]["device_id"]
    filename = f"{device_id}_hcp_support.py"

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"[OK] Generated TCP client SDK: {out_path}")


if __name__ == "__main__":
    main()
