from lerobot.teleoperators.so101_leader import SO101LeaderConfig, SO101Leader
from lerobot.robots.so101_follower import SO101FollowerConfig, SO101Follower

# Add the parent directory to the Python path
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from actuator.dh_table import *
from actuator.arm_kinematics import *
from actuator.constants import *

robot_config = SO101FollowerConfig(
    port="/dev/ttyACM0",
    id="follower_arm2",
)

robot = SO101Follower(robot_config)
robot.connect()

teleop_config = SO101LeaderConfig(
    port="/dev/ttyACM1",
    id="leader_arm2",
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
    end_effector_pos = compute_end_effector_pos_from_joints(np.array(joint_angles))
    print(f"End Effector Position: x={end_effector_pos[0]:.2f}, y={end_effector_pos[1]:.2f}, z={end_effector_pos[2]:.2f}")