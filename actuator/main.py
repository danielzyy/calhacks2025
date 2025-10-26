from gen.SOARM100_ROBOT_ARM_hcp_support import HCPClient
import time
import queue
import numpy as np
from copy import deepcopy
from actuator_layer import ActuatorLayer, Mode, ActuatorLayerRequest   

client = HCPClient()
client.start()

requestActive = False

actuator_layer = ActuatorLayer(Mode.AUTONOMOUS, use_visualizer=True, dry_run=False, virtual=False)

while True:
    actuator_layer.step()
    try:
        # Non-blocking check for new HCP commands
        action, payload = client.events.get_nowait()        
        print(f"[EVENT] {action}: {payload}")
        prev_request = deepcopy(actuator_layer.request)
        
        request = prev_request

        if (action == "move_arm"):
            request.x_m = payload.get("x", 0)/1000
            request.y_m = payload.get("y", 0)/1000
            request.z_m = payload.get("z", 0)/1000
            actuator_layer.request_position(request)
        elif (action == "control_grip"):
            closed = payload.get("closed", False)
            gripper_cmd = 0.0 if closed else 1.0
            request = prev_request
            request.gripper_cmd = gripper_cmd
            actuator_layer.request_position(request)
        elif (action == "set_wrist_angle"):
            angle = payload.get("angle", 0.0)
            request.wrist_angle_rad = np.deg2rad(angle)
            actuator_layer.request_position(request)

        # handle the command
        result = {"status": "ok", "message": f"Handled {action}"}
        requestActive = True
    
    except queue.Empty:
        pass

    if requestActive:
        is_actuator_close_to_target_now = actuator_layer.is_close_to_target()
        print(f"Is actuator close to target? {is_actuator_close_to_target_now}")
        # send the response back to HCP
        if is_actuator_close_to_target_now:
            print("[EVENT] reached_target")
            client.send_response(action, result)
            requestActive = False

    # other main loop tasks
    time.sleep(0.01)