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
robot.setup_motors()

