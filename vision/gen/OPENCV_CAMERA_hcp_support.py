"""OPENCV_CAMERA_hcp_support.py — Auto-generated HCP SDK TCP Client"""
import json
import socket
import threading
import time
import queue

DEVICE_ID = 'OPENCV_CAMERA'
DEVICE_DESC = """A camera that is parsed through opencv to return distance between an april tag and the arm."""
HCP_HOST = "172.20.10.4"
HCP_PORT = 9000

# Original JSON definition
HCP_DEVICE_JSON = { 'available_commands': { 'get_tags': { 'freetext_desc': 'Returns the '
                                                         'coordinates of every '
                                                         'april tag in '
                                                         'reference to the '
                                                         'origin 0, 0, 0.',
                                        'params': []}},
  'metadata': { 'device_id': 'OPENCV_CAMERA',
                'freetext_desc': 'A camera that is parsed through opencv to '
                                 'return distance between an april tag and the '
                                 'arm.'}}

class HCPClient:
    def __init__(self):
        self.host = HCP_HOST
        self.port = HCP_PORT
        self.sock = None
        self.running = False
        self.events = queue.Queue()  # incoming (action, payload)
        self._responses = queue.Queue()  # outgoing responses

    def start(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self._connect_loop, daemon=True).start()
            print(f'[OK] HCPClient started for {self.host}:{self.port}')

    def send_response(self, action, body):
        '''Thread-safe: enqueue a response to send back to HCP'''
        self._responses.put({'action': action, 'body': body})

    def _connect_loop(self):
        while self.running:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.host, self.port))
                print(f'[OK] Connected to HCP host {self.host}:{self.port}')
                self._listen_loop()
            except (ConnectionRefusedError, OSError):
                print('[WARN] Connection failed. Retrying in 3s...')
                time.sleep(3)

    def _listen_loop(self):
        while self.running:
            try:
                data = self.sock.recv(4096).decode('utf-8')
                if not data:
                    print('[INFO] Disconnected, reconnecting...')
                    return
                message = json.loads(data)
                action = message.get('action')
                payload = message.get('payload', {})

                if action == 'REQUEST_HCP_DATA':
                    self._send_json(HCP_DEVICE_JSON)
                else:
                    # push incoming actions to main thread queue
                    self.events.put((action, payload))
                    # send response queued by main thread
                    resp = self._responses.get()
                    self._send_json(resp)

            except Exception as e:
                print('[ERROR]', e)
                time.sleep(1)

    def _send_json(self, obj):
        try:
            self.sock.sendall(json.dumps(obj).encode('utf-8'))
        except Exception as e:
            print('[ERROR] Failed to send JSON:', e)

    def stop(self):
        self.running = False
        if self.sock:
            try: self.sock.close()
            except: pass
        print('[OK] HCPClient stopped.')

if __name__ == '__main__':
    client = HCPClient()
    client.start()
    try:
        while True:
            try:
                action, payload = client.events.get_nowait()
                print(f'[EVENT] {action}: {payload}')

                # Example: automatically send back a dummy response
                client.send_response(action, {'status': 'ok', 'message': f'Handled {action}'})

            except queue.Empty:
                pass
            time.sleep(0.01)
    except KeyboardInterrupt:
        client.stop()