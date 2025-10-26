import numpy as np
from lerobot.teleoperators.so101_leader import SO101LeaderConfig, SO101Leader
from lerobot.robots.so101_follower import SO101FollowerConfig, SO101Follower
from enum import Enum
import click
import argparse
import time
from dataclasses import dataclass

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

@dataclass
class ActuatorLayerRequest:
    x_m: float
    y_m: float
    z_m: float
    wrist_angle_rad: float # angle at which the wrist will approach a target end point
    gripper_cmd: float # 0.0 to 1.0, where 0.0 is fully closed and 1.0 is fully open

    def validate(self):
        assert self.gripper_cmd >= 0.0 and self.gripper_cmd <= 1.0, "Gripper command must be between 0.0 and 1.0"
        assert self.z >= 0.0, "Z coordinate must be non-negative"
        assert self.x >= 0.0, "X coordinate must be non-negative"
    
class ActuatorLayer:
    def __init__(self, mode, virtual: False, dry_run=False, use_visualizer=False):
        assert mode in Mode, "Invalid mode specified."
        if virtual:
            assert dry_run, "Virtual mode requires dry_run to be True."
            assert mode == Mode.AUTONOMOUS, "Virtual mode only supports AUTONOMOUS mode."

        self.mode = mode
        self.dry_run = dry_run
        self.virtual = virtual

        if not virtual:
            ports = detect_so101_ports()

            robot_config = SO101FollowerConfig(
                port=ports["follower_port"],
                id="follower_arm6",
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

        self.request = ActuatorLayerRequest(0.17, 0.0, 0.05, np.deg2rad(90.0), 0.1)
        self.request_fresh = True

        self.speed_limit_m_per_s = 0.4  # m/s

        # misc
        self.gripper_cmd_scale_y = [0.1027924, 1.7260]
        self.time_prev = time.time()
        self.close_to_target = False

    def is_close_to_target(self):
        return self.close_to_target

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
        # print(f"DH Joint Angles (rad): {self.dh_joint_angles_actual_rad}")
        self.end_effector_pos = compute_end_effector_pos_from_joints(np.array(self.dh_joint_angles_actual_rad))
        print(f"End Effector Position: x={self.end_effector_pos[0]:.3f}, y={self.end_effector_pos[1]:.3f}, z={self.end_effector_pos[2]:.3f}")

        if self.mode != Mode.AUTONOMOUS:
            teleop_joint_positions = self.teleop_device.get_action()
            teleop_joint_angles = [teleop_joint_positions[f"{joint}.pos"] for joint in JOINT_NAMES_AS_INDEX]
            self.teleop_mech_joint_angles_actual_rad = [np.deg2rad(angle) for angle in teleop_joint_angles]
            self.teleop_dh_joint_angles_actual_rad = mech_to_dh_angles(self.teleop_mech_joint_angles_actual_rad)
            self.teleop_end_effector_pos = compute_end_effector_pos_from_joints(np.array(self.teleop_dh_joint_angles_actual_rad))

        self.dt_measured = time.time() - self.time_prev
        self.time_prev = time.time()

    def is_commanded_location_safe(self, x, y, z):
        if get_euclidian_distance(
            x, y
        ) < L5:
            click.secho(f"Warning: target position of {x}, {y}, {z} ignored as it is too close to the base", fg="yellow")
            return False
        elif x < 0.0:
            click.secho(f"Warning: target position of {x}, {y}, {z} ignored as it is behind the base", fg="yellow")
            return False
        return True
        
    def run_full_teleop(self):
        action = self.teleop_dh_joint_angles_actual_rad
        return action        

    def run_elbow_control_only_teleop(self):
        target_elbow_location = get_instantenous_controller_target(
            current_pos=self.end_effector_pos,
            target_pos=self.teleop_end_effector_pos,
            linear_speed=self.speed_limit_m_per_s,
            dt=self.dt_measured
        )

        if not self.is_commanded_location_safe(
            self.teleop_end_effector_pos[0],
            self.teleop_end_effector_pos[1],
            self.teleop_end_effector_pos[2]
        ):
            return self.dh_joint_angles_actual_rad
        
        # solve for the required elbow joint angle to reach this position
        ik_solution = compute_inverse_kinematics_at_desired_wrist_position(
            target_elbow_location[0],
            target_elbow_location[1],
            target_elbow_location[2],
            wrist_approach_angle=-np.pi/4 # full up is np.pi/2, full down is -np.pi/2
        )

        # if any ik solution is NaN, ignore the command
        if np.isnan(ik_solution).any():
            click.secho(f"Warning: IK solution resulted in NaN for target position of {self.teleop_end_effector_pos}, ignoring command", fg="yellow")
            return self.dh_joint_angles_actual_rad

        # send only the elbow joint command to the follower arm
        joint_cmd_dh = np.zeros(len(JOINT_NAMES_AS_INDEX))
        for i in range(len(ik_solution)):
            joint_cmd_dh[i] = ik_solution[i]

        joint_cmd_dh[4] = self.teleop_dh_joint_angles_actual_rad[4]
        joint_cmd_dh[5] = self.teleop_dh_joint_angles_actual_rad[5]  # gripper

        return joint_cmd_dh
    
    def run_autonomous(self):
        if self.request_fresh:
            self.request_fresh = False
        # don't validate here... assume the user has done it
        request_pos = np.array([self.request.x_m, self.request.y_m, self.request.z_m])
        target_end_effector_location = get_instantenous_controller_target(
            current_pos=self.end_effector_pos,
            target_pos=request_pos,
            linear_speed=self.speed_limit_m_per_s,
            dt=self.dt_measured
        )
        x = target_end_effector_location[0]
        y = target_end_effector_location[1]
        z = target_end_effector_location[2]
        wrist_angle = self.request.wrist_angle_rad
        gripper_cmd = np.interp(
            self.request.gripper_cmd,
            [0.0, 1.0],
            self.gripper_cmd_scale_y
        )
        self.request_fresh = False

        if not self.is_commanded_location_safe(*request_pos):
            return self.dh_joint_angles_actual_rad
        
        wrist_approach_angle = -np.pi/4 # flat approach

        ik_solution = compute_inverse_kinematics_at_desired_wrist_position(
            x, y, z, wrist_approach_angle
        )

        if np.isnan(ik_solution).any():
            click.secho(f"Warning: IK solution resulted in NaN for target position of {x}, {y}, {z}, ignoring command", fg="yellow")
            return self.dh_joint_angles_actual_rad
    
        joint_cmd_dh = np.zeros(len(JOINT_NAMES_AS_INDEX))
        for i in range(len(ik_solution)):
            joint_cmd_dh[i] = ik_solution[i]
        
        joint_cmd_dh[4] = wrist_angle
        joint_cmd_dh[5] = gripper_cmd  # gripper

        # update if we're close to the target
        self.close_to_target = is_close_to_target(
            current_pos=self.end_effector_pos,
            target_pos=request_pos,
            threshold_m=0.075
        )
        return joint_cmd_dh



    def request_position(self, request: ActuatorLayerRequest):
        self.request = request
        self.request_fresh = True

    def step(self):
        self.update_robot_state()

        if self.mode == Mode.FULL_TELEOP:
            joint_angle_cmd = self.run_full_teleop()
        elif self.mode == Mode.ELBOW_CONTROL_ONLY_TELEOP:
            joint_angle_cmd = self.run_elbow_control_only_teleop()
        elif self.mode == Mode.AUTONOMOUS:
            joint_angle_cmd = self.run_autonomous()
            if joint_angle_cmd is None:
                joint_angle_cmd = self.joint_angle_cmd_prev
        else:
            raise NotImplementedError("Only FULL_TELEOP mode is implemented.")
        
        joint_angle_cmd_mech = dh_to_mech_angles(joint_angle_cmd)
        assert len(joint_angle_cmd_mech) == JOINT_NAMES_AS_INDEX.__len__(), "Joint command length mismatch."
        self.action = {f"{JOINT_NAMES_AS_INDEX[i]}.pos": np.rad2deg(joint_angle_cmd_mech[i]) for i in range(len(joint_angle_cmd_mech))}

        if self.dry_run:
            pass
        else:
            self.robot.send_action(self.action)

        self.joint_angle_cmd_prev = joint_angle_cmd
        
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
    parser.add_argument(
        "--virtual",
        action="store_true",
        help="If set, runs in virtual mode without connecting to real hardware. Implies dry run"
    )
    args = parser.parse_args()

    mode = Mode(args.mode)

    actuator_layer = ActuatorLayer(mode, use_visualizer=True, dry_run=args.dry_run, virtual=args.virtual)

    while True:
        actuator_layer.step()