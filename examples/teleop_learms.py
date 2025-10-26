from lerobot.teleoperators.so101_leader import SO101LeaderConfig, SO101Leader
from lerobot.robots.so101_follower import SO101FollowerConfig, SO101Follower

# Add the parent directory to the Python path
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from actuator.kinematics.dh_table import *
from actuator.kinematics.arm_kinematics import *
from actuator.kinematics.constants import *
from actuator.utils.detect_serial import detect_so101_ports

ports = detect_so101_ports()

robot_config = SO101FollowerConfig(
    port=ports["follower_port"],
    id="follower_arm5",
)

robot = SO101Follower(robot_config)
robot.connect()

teleop_config = SO101LeaderConfig(
    port=ports["leader_port"],
    id="leader_arm4",
)
teleop_device = SO101Leader(teleop_config)
teleop_device.connect()

while True:
    action = teleop_device.get_action()
    robot.send_action(action)
    robot_pos = robot.get_observation()
    print(robot_pos)
    joint_angles = [robot_pos[f"{joint}.pos"] for joint in JOINT_NAMES_AS_INDEX]
    joint_angles_rad = [np.deg2rad(angle) for angle in joint_angles]
    joint_angles_dh = mech_to_dh_angles(joint_angles_rad)
    for i in range(len(joint_angles_dh)):
        print(f"Joint {i+1} Angle (DH): {np.rad2deg(joint_angles_dh[i]):.2f} degrees")
    end_effector_pos = compute_end_effector_pos_from_joints(np.array(joint_angles_dh))
    print(f"End Effector Position: x={end_effector_pos[0]:.3f}, y={end_effector_pos[1]:.3f}, z={end_effector_pos[2]:.3f}")

    # solve for inverse kinematics position of the 3rd joint
    joint_angles_for_ik_solution = joint_angles_dh[:3]
    pos_of_third_joint = compute_end_effector_pos_from_joints(np.array(joint_angles_for_ik_solution))
    ik_solution = compute_inverse_kinematics_wrist_desired_pos(
        pos_of_third_joint[0],
        pos_of_third_joint[1],
        pos_of_third_joint[2],
    )
    fwd_kinematics_check = compute_end_effector_pos_from_joints(ik_solution)
    print(f"IK Solution Check: x={fwd_kinematics_check[0]:.3f}, y={fwd_kinematics_check[1]:.3f}, z={fwd_kinematics_check[2]:.3f}")
    print(f"Third joint position: x={pos_of_third_joint[0]:.3f}, y={pos_of_third_joint[1]:.3f}, z={pos_of_third_joint[2]:.3f}")