from gen.OPENCV_CAMERA_hcp_support import HCPClient
import time
import queue

import tag_detections

client = HCPClient()
client.start()

tag_detections.camera_setup()

while True:
    tag_detections.camera_run()
    try:
        # Non-blocking check for new HCP commands
        action, payload = client.events.get_nowait()        
        print(f"[EVENT] {action}: {payload}")

        if (action == "get_tags"):
            # handle the command
            # tag_detections.getItemPositions()
            result = {"status": "ok", "result": tag_detections.getItemPositions()}

            # send the response back to HCP
            print(result)
            client.send_response(action, result)
            print("after send")

    except queue.Empty:
        pass

    # other main loop tasks
    time.sleep(0.1)