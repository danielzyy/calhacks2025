from typing import Any, Dict, List, Tuple, Optional
import socket
import json
import threading
from dataclasses import dataclass, field

@dataclass
class Client:
    conn: socket.socket
    addr: tuple
    thread: threading.Thread
    alive: bool = field(default=True)

class HCPExecutor:
    def __init__(self):
        # Structure:
        # devices = {
        #   "device_id": {
        #       "description": str,
        #       "port": int,
        #       "actions": {
        #           "action_name": {
        #               "description": str,
        #               "params": [(name, type), ...],
        #           }
        #       }
        #   }
        # }
        self.devices: Dict[str, Dict[str, Any]] = {}

    # ---------- Registration ----------
    def register_device(self, device_id: str, description: str, port: int, client: Client):
        """Register a hardware device reachable over TCP."""
        if device_id in self.devices:
            raise ValueError(f"Device '{device_id}' already registered.")
        self.devices[device_id] = {
            "description": description,
            "port": port,
            "client": client,
            "actions": {}
        }

    def register_action(
        self,
        device_id: str,
        action_name: str,
        description: str,
        params: List[Tuple[str, type]],
    ):
        """Register an action for a device."""
        if device_id not in self.devices:
            raise ValueError(f"Device '{device_id}' not found.")
        device = self.devices[device_id]
        if action_name in device["actions"]:
            raise ValueError(f"Action '{action_name}' already registered for '{device_id}'.")
        device["actions"][action_name] = {
            "description": description,
            "params": params
        }

    # ---------- Validation ----------
    def validate_payload(self, device_id: str, action_name: str, payload: Dict[str, Any]) -> bool:
        """Ensure payload matches expected parameter schema."""
        device = self.devices.get(device_id)
        if not device:
            print(f"❌ Unknown device '{device_id}'")
            return False
        action = device["actions"].get(action_name)
        if not action:
            print(f"❌ Unknown action '{action_name}' for '{device_id}'")
            return False

        for param_name, param_type in action["params"]:
            if param_name not in payload:
                print(f"❌ Missing parameter '{param_name}'")
                return False
            if not isinstance(payload[param_name], param_type):
                print(f"❌ Parameter '{param_name}' should be {param_type.__name__}, got {type(payload[param_name]).__name__}")
                return False

        # Check for unexpected params
        for key in payload:
            if key not in [p[0] for p in action["params"]]:
                print(f"⚠️ Unexpected parameter '{key}'")
                return False

        return True

    def execute_action(self, device_id: str, action_name: str, payload: Dict[str, Any]) -> bool:
        """Validate and send action request over TCP."""
        if not self.validate_payload(device_id, action_name, payload):
            return False

        device = self.devices[device_id]

        message = {
            "action": action_name,
            "payload": payload
        }

        try:
            device["client"].conn.sendall(json.dumps(message).encode("utf-8"))
            print(f"✅ Sent to {device_id}:{device['port']}")
            return True
        except Exception as e:
            print(f"⚠️ TCP send failed for {device_id}:{device['port']} — {e}")
            return False
        
    # ---------- LLM Integration ----------
    def get_device_llm_context_str(self, device_id: str) -> str:
        """Return device info in an LLM-friendly string format."""
        if device_id not in self.devices:
            raise ValueError(f"Device '{device_id}' not found.")
        
        device = self.devices[device_id]
        lines = [f"Device '{device_id}': {device['description']}", "Available actions:"]
        
        for action_name, action_info in device["actions"].items():
            param_str = ", ".join([f"{name}: {ptype.__name__}" for name, ptype in action_info["params"]])
            lines.append(f" - {action_name}({param_str}) → {action_info['description']}")
        
        return "\n".join(lines)
    
    def get_all_devices_llm_context_str(self) -> str:
        """Return all registered devices and actions in an LLM-friendly string format."""
        if not self.devices:
            return "No devices are currently registered."
        
        lines = []
        for device_id in self.devices.keys():
            lines.append(self.get_device_llm_context_str(device_id))
            lines.append("")  # blank line between devices
        return "\n".join(lines)

    # ---------- Query helpers ----------
    def list_devices(self) -> Dict[str, Dict[str, Any]]:
        return {n: {"desc": d["description"], "port": d["port"]} for n, d in self.devices.items()}

    def list_actions(self, device_id: str) -> Dict[str, Dict[str, Any]]:
        if device_id not in self.devices:
            raise ValueError(f"Device '{device_id}' not found.")
        actions = self.devices[device_id]["actions"]
        return {a: {"desc": d["description"]} for a, d in actions.items()}
