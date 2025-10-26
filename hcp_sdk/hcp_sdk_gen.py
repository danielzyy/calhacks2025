"""ROBOT_ARM_hcp_support.py — Auto-generated HCP SDK TCP Client"""
import json
import socket
import threading
import time

DEVICE_ID = 'ROBOT_ARM'
DEVICE_DESC = """A robot arm that can pick and place objects."""
HCP_HOST = "127.0.0.1"
HCP_PORT = 9000

# Original JSON definition
HCP_DEVICE_JSON = {
  "metadata": {
    "device_id": "ROBOT_ARM",
    "freetext_desc": "A robot arm that can pick and place objects."
  },
  "available_commands": {
    "move_arm": {
      "freetext_desc": "Moves the arm to the specified 3D coordinates.",
      "params": [
        {
          "x": "int"
        },
        {
          "y": "int"
        },
        {
          "z": "int"
        }
      ]
    },
    "control_grip": {
      "freetext_desc": "Opens or closes the gripper.",
      "params": [
        {
          "closed": "bool"
        }
      ]
    },
    "set_grip_angle": {
      "freetext_desc": "Sets the angle of the gripper in degrees.",
      "params": [
        {
          "angle": "float"
        }
      ]
    }
  }
}

class HCPClient:
    def __init__(self):
        self.host = HCP_HOST
        self.port = HCP_PORT
        self.sock = None
        self.running = False

    def connect(self):
        while True:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.host, self.port))
                print(f'[OK] Connected to HCP host {self.host}:{self.port}')
                self.running = True
                threading.Thread(target=self.listen_loop, daemon=True).start()
                break
            except ConnectionRefusedError:
                print('[WARN] Connection refused. Retrying in 3 seconds...')
                time.sleep(3)

    def listen_loop(self):
        while self.running:
            try:
                data = self.sock.recv(4096).decode('utf-8')
                if not data:
                    print('[INFO] Disconnected from host, attempting reconnect...')
                    self.connect()
                    continue
                message = json.loads(data)
                response = self.handle_hcp_request(message)
                if response:
                    self.sock.sendall(json.dumps(response).encode('utf-8'))
            except Exception as e:
                print('[ERROR]', e)
                time.sleep(1)

    def handle_hcp_request(self, message: dict) -> dict:
        action = message.get('action')
        payload = message.get('payload', {})

        if action == 'REQUEST_HCP_DATA':
            return HCP_DEVICE_JSON

        elif action == 'move_arm':
            # Moves the arm to the specified 3D coordinates.
            # Expected params:
        # - x (int)
        # - y (int)
        # - z (int)
            print('Executing move_arm with', payload)
            # TODO: user-implemented logic here
            return {'status': 'ok', 'action': action}

        elif action == 'control_grip':
            # Opens or closes the gripper.
            # Expected params:
        # - closed (bool)
            print('Executing control_grip with', payload)
            # TODO: user-implemented logic here
            return {'status': 'ok', 'action': action}

        elif action == 'set_grip_angle':
            # Sets the angle of the gripper in degrees.
            # Expected params:
        # - angle (float)
            print('Executing set_grip_angle with', payload)
            # TODO: user-implemented logic here
            return {'status': 'ok', 'action': action}

        else:
            return {'error': f'Unknown action: {action}'}

    def close(self):
        self.running = False
        if self.sock:
            self.sock.close()
        print('[OK] Disconnected from HCP host.')

if __name__ == '__main__':
    client = HCPClient()
    client.connect()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.close()