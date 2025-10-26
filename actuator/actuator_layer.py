import numpy as np
from lerobot.teleoperators.so101_leader import SO101LeaderConfig, SO101Leader
from lerobot.robots.so101_follower import SO101FollowerConfig, SO101Follower
from enum import Enum
import argparse

# Add the parent directory to the Python path
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from actuator.utils.detect_serial import detect_so101_ports
from actuator.visualizer import Visualizer
from actuator.kinematics.dh_table import *
from actuator.kinematics.arm_kinematics import *
from actuator.kinematics.constants import *

class Mode(Enum):
    FULL_TELEOP = "FULL_TELEOP"
    TELEOP_ONLY_JOINT_3_POS = "TELEOP_ONLY_JOINT_3_POS"
    AUTONOMOUS = "AUTONOMOUS"
    
class ActuatorLayer:
    def __init__(self, mode, use_visualizer=False):
        assert mode in Mode, "Invalid mode specified."
        self.mode = mode

        ports = detect_so101_ports()

        robot_config = SO101FollowerConfig(
            port=ports["follower_port"],
            id="follower_arm5",
        )
        self.robot = SO101Follower(robot_config)
        self.robot.connect()

        if mode != Mode.AUTONOMOUS:
            teleop_config = SO101LeaderConfig(
                port=ports["leader_port"],
                id="leader_arm4",
            )
            self.teleop_device = SO101Leader(teleop_config)
            self.teleop_device.connect()

        self.use_visualizer = use_visualizer
        if use_visualizer:
            self.visualizer = Visualizer()
            self.visualizer_count = 0

    def run_full_teleop(self):
        action = self.teleop_device.get_action()
        self.robot.send_action(action)

    def step(self):
        if self.mode == Mode.FULL_TELEOP:
            self.run_full_teleop()
        else:
            raise NotImplementedError("Only FULL_TELEOP mode is implemented.")
        joint_positions = self.robot.get_observation()
        joint_angles = [joint_positions[f"{joint}.pos"] for joint in JOINT_NAMES_AS_INDEX]
        self.mech_joint_angles_actual_rad = [np.deg2rad(angle) for angle in joint_angles]
        self.dh_joint_angles_actual_rad = mech_to_dh_angles(self.mech_joint_angles_actual_rad)
        
        if self.use_visualizer:
            self.visualizer_count += 1
            if self.visualizer_count % 1 == 0:
                self.visualizer.plot(self.dh_joint_angles_actual_rad)
                self.visualizer_count = 0 

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Actuator Layer Teleoperation")
    parser.add_argument(
        "--mode",
        type=str,
        choices=[mode.name for mode in Mode],
        default="FULL_TELEOP"
    )
    args = parser.parse_args()

    mode = Mode(args.mode)
    actuator_layer = ActuatorLayer(mode, use_visualizer=True)

    while True:
        actuator_layer.step()