from OPENCV_CAMERA_hcp_support import HCPClient
import time
import queue
import numpy as np
from copy import deepcopy

import sys
import os

# Add project root (C:.) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import vision.tag_detections

client = HCPClient()
client.start()

camera_setup()

while True:
    try:
        # Non-blocking check for new HCP commands
        action, payload = client.events.get_nowait()        
        print(f"[EVENT] {action}: {payload}")
        
        request = prev_request

        if (action == "get_tags"):
            items = camera_run()
            data = []
            if items is not None:
                for i in items:
                    data.append({"Name": i.name, "ID": i.idx, "Relative X Coordinate": i.xrel, "Relative Y Coordinate": i.yrel})

                # handle the command
                result = {"status": "ok", "message": data}

                # send the response back to HCP
                client.send_response(action, result)

    except queue.Empty:
        pass

    # other main loop tasks
    time.sleep(0.01)