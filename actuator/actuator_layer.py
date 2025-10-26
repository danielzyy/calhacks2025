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
    ELBOW_CONTROL_ONLY_TELEOP = "ELBOW_CONTROL_ONLY_TELEOP"
    AUTONOMOUS = "AUTONOMOUS"
    
class ActuatorLayer:
    def __init__(self, mode, dry_run=False, use_visualizer=False):
        assert mode in Mode, "Invalid mode specified."
        self.mode = mode
        self.dry_run = dry_run

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
        action = self.teleop_dh_joint_angles_actual_rad
        return action
        

    def run_elbow_control_only_teleop(self):
        
        leader_arm_elbow_location =compute_end_effector_pos_from_joints(
            self.teleop_dh_joint_angles_actual_rad[:3]
        )
        
        # solve for the required elbow joint angle to reach this position
        ik_solution = compute_inverse_kinematics_elbow_desired_pos(
            leader_arm_elbow_location[0],
            leader_arm_elbow_location[1],
            leader_arm_elbow_location[2],
        )

        # send only the elbow joint command to the follower arm
        joint_cmd_dh = np.zeros(len(JOINT_NAMES_AS_INDEX))
        for i in range(len(ik_solution)):
            joint_cmd_dh[i] = ik_solution[i]

        # theta_2 + theta_3 + theta_4 = theta_5
        # constrain theta_5 to be -pi/2 to keep wrist flat
        # therefore, set -pi/2 = theta_2 + theta_3 + theta_4
        # => theta_4 = -pi/2 - theta_2 - theta_3

        joint_cmd_dh[3] = -np.pi/2 - (joint_cmd_dh[1] + joint_cmd_dh[2])
        joint_cmd_dh[4] = 0.0  # neutral wrist roll
        joint_cmd_dh[5] = 0.0

        return joint_cmd_dh

    def update_robot_state(self):
        if self.dry_run:
            if not hasattr(self, 'action'):
                self.action = {f"{joint}.pos": 0.0 for joint in JOINT_NAMES_AS_INDEX}
            joint_positions = self.action
        else:
            joint_positions = self.robot.get_observation()
        joint_angles = [joint_positions[f"{joint}.pos"] for joint in JOINT_NAMES_AS_INDEX]
        self.mech_joint_angles_actual_rad = [np.deg2rad(angle) for angle in joint_angles]
        self.dh_joint_angles_actual_rad = mech_to_dh_angles(self.mech_joint_angles_actual_rad)
        self.end_effector_pos = compute_end_effector_pos_from_joints(np.array(self.dh_joint_angles_actual_rad))
        # print(f"End Effector Position: x={self.end_effector_pos[0]:.3f}, y={self.end_effector_pos[1]:.3f}, z={self.end_effector_pos[2]:.3f}")

        teleop_joint_positions = self.teleop_device.get_action()
        teleop_joint_angles = [teleop_joint_positions[f"{joint}.pos"] for joint in JOINT_NAMES_AS_INDEX]
        self.teleop_mech_joint_angles_actual_rad = [np.deg2rad(angle) for angle in teleop_joint_angles]
        self.teleop_dh_joint_angles_actual_rad = mech_to_dh_angles(self.teleop_mech_joint_angles_actual_rad)
        self.teleop_end_effector_pos = compute_end_effector_pos_from_joints(np.array(self.teleop_dh_joint_angles_actual_rad))

    def step(self):
        self.update_robot_state()

        if self.mode == Mode.FULL_TELEOP:
            joint_angle_cmd = self.run_full_teleop()
        elif self.mode == Mode.ELBOW_CONTROL_ONLY_TELEOP:
            joint_angle_cmd = self.run_elbow_control_only_teleop()
        else:
            raise NotImplementedError("Only FULL_TELEOP mode is implemented.")
        
        joint_angle_cmd_mech = dh_to_mech_angles(joint_angle_cmd)
        assert len(joint_angle_cmd_mech) == JOINT_NAMES_AS_INDEX.__len__(), "Joint command length mismatch."
        self.action = {f"{JOINT_NAMES_AS_INDEX[i]}.pos": np.rad2deg(joint_angle_cmd_mech[i]) for i in range(len(joint_angle_cmd_mech))}

        if self.dry_run:
            pass
        else:
            self.robot.send_action(self.action)
        
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
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="If set, runs in dry run mode without sending commands to the robot."
    )
    args = parser.parse_args()

    mode = Mode(args.mode)
    actuator_layer = ActuatorLayer(mode, use_visualizer=True, dry_run=args.dry_run)

    while True:
        actuator_layer.step()