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
        "",
        f"DEVICE_ID = '{device_id}'",
        f'DEVICE_DESC = \"\"\"{desc}\"\"\"',
        f'HCP_HOST = \"{host}\"',
        f"HCP_PORT = {port}",
        "",
        "# Original JSON definition",
        f"HCP_DEVICE_JSON = {json.dumps(data, indent=2)}",
        "",
        "class HCPClient:",
        "    def __init__(self):",
        "        self.host = HCP_HOST",
        "        self.port = HCP_PORT",
        "        self.sock = None",
        "        self.running = False",
        "",
        "    def connect(self):",
        "        while True:",
        "            try:",
        "                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)",
        "                self.sock.connect((self.host, self.port))",
        "                print(f'[OK] Connected to HCP host {self.host}:{self.port}')",
        "                self.running = True",
        "                threading.Thread(target=self.listen_loop, daemon=True).start()",
        "                break",
        "            except ConnectionRefusedError:",
        "                print('[WARN] Connection refused. Retrying in 3 seconds...')",
        "                time.sleep(3)",
        "",
        "    def listen_loop(self):",
        "        while self.running:",
        "            try:",
        "                data = self.sock.recv(4096).decode('utf-8')",
        "                if not data:",
        "                    print('[INFO] Disconnected from host, attempting reconnect...')",
        "                    self.connect()",
        "                    continue",
        "                message = json.loads(data)",
        "                response = self.handle_hcp_request(message)",
        "                if response:",
        "                    self.sock.sendall(json.dumps(response).encode('utf-8'))",
        "            except Exception as e:",
        "                print('[ERROR]', e)",
        "                time.sleep(1)",
        "",
        "    def handle_hcp_request(self, message: dict) -> dict:",
        "        action = message.get('action')",
        "        payload = message.get('payload', {})",
        "",
        "        if action == 'REQUEST_HCP_DATA':",
        "            return HCP_DEVICE_JSON",
        "",
    ]

    # Commands
    for cmd_name, cmd_data in commands.items():
        desc = cmd_data["freetext_desc"]
        params_doc = "\n".join(
            [f"        # - {list(p.keys())[0]} ({list(p.values())[0]})" for p in cmd_data["params"]]
        )

        code_lines += [
            f"        elif action == '{cmd_name}':",
            f"            # {desc}",
            f"            # Expected params:\n{params_doc}",
            f"            print('Executing {cmd_name} with', payload)",
            "            # TODO: user-implemented logic here",
            "            return {'status': 'ok', 'action': action}",
            "",
        ]

    code_lines += [
        "        else:",
        "            return {'error': f'Unknown action: {action}'}",
        "",
        "    def close(self):",
        "        self.running = False",
        "        if self.sock:",
        "            self.sock.close()",
        "        print('[OK] Disconnected from HCP host.')",
        "",
        "if __name__ == '__main__':",
        "    client = HCPClient()",
        "    client.connect()",
        "    try:",
        "        while True:",
        "            time.sleep(1)",
        "    except KeyboardInterrupt:",
        "        client.close()",
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
