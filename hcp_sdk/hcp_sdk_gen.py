#!/usr/bin/env python3
"""
HCP SDK Generator
-----------------
Usage:
    python hcp_sdk_gen.py --input examples/robot_arm.json --output ./out
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
def generate_device_code(data: Dict[str, Any]) -> str:
    meta = data["metadata"]
    device_id = meta["device_id"]
    desc = meta["freetext_desc"]
    commands = data["available_commands"]

    code_lines = [
        f'"""{device_id}_hcp_support.py — Auto-generated HCP SDK file"""',
        "import json",
        "import socket",
        "import threading",
        "",
        f"DEVICE_ID = '{device_id}'",
        f'DEVICE_DESC = """{desc}"""',
        "",
        "# Original JSON definition",
        f"HCP_DEVICE_JSON = {json.dumps(data, indent=2)}",
        "",
        "def handle_hcp_request(message: dict) -> str:",
        '    """Handles incoming HCP action requests."""',
        "    action = message.get('action')",
        "    payload = message.get('payload', {})",
        "",
        "    if action == 'REQUEST_HCP_DATA':",
        "        return json.dumps(HCP_DEVICE_JSON)",
        "",
    ]

    for cmd_name, cmd_data in commands.items():
        desc = cmd_data["freetext_desc"]
        params_doc = "\\n".join([f"      - {list(p.keys())[0]} ({list(p.values())[0]})" for p in cmd_data["params"]])

        code_lines += [
            f"    elif action == '{cmd_name}':",
            f"        # {desc}",
            f"        # Expected params:\\n{params_doc}",
            f"        # TODO: implement logic below",
            f"        print('Executing {cmd_name} with', payload)",
            "        # USER CODE HERE",
            "        return json.dumps({'status': 'ok', 'action': action})",
            "",
        ]

    code_lines += [
        "    else:",
        "        return json.dumps({'error': f'Unknown action: {action}'})",
        "",
        "def start_hcp_server(port: int = 9000):",
        '    """Start a TCP listener that handles HCP requests."""',
        "    def client_thread(conn, addr):",
        "        try:",
        "            data = conn.recv(4096).decode('utf-8')",
        "            message = json.loads(data)",
        "            response = handle_hcp_request(message)",
        "            conn.sendall(response.encode('utf-8'))",
        "        except Exception as e:",
        "            conn.sendall(json.dumps({'error': str(e)}).encode('utf-8'))",
        "        finally:",
        "            conn.close()",
        "",
        "    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)",
        "    server.bind(('localhost', port))",
        "    server.listen()",
        f"    print(f'[OK] {device_id} HCP server listening on port {{port}}')",
        "    while True:",
        "        conn, addr = server.accept()",
        "        threading.Thread(target=client_thread, args=(conn, addr), daemon=True).start()",
        "",
        "if __name__ == '__main__':",
        "    start_hcp_server()",
    ]

    return "\n".join(code_lines)


# ---------------- CLI Entry Point ----------------
def main():
    parser = argparse.ArgumentParser(description="Generate HCP support file from JSON spec.")
    parser.add_argument("--input", required=True, help="Path to input JSON spec.")
    parser.add_argument("--output", default=".", help="Output directory (default: current).")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.output)
    schema_path = Path(__file__).parent / "hcp_sdk_schema.json"

    # Load input JSON
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ---------------- Validation ----------------
    validate_hcp_json_schema(data, schema_path)

    # ---------------- Code Generation ----------------
    code = generate_device_code(data)
    device_id = data["metadata"]["device_id"]
    filename = f"{device_id}_hcp_support.py"

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"[OK] Generated: {out_path}")


if __name__ == "__main__":
    main()
