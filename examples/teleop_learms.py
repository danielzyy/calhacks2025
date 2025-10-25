from lerobot.teleoperators.so101_leader import SO101LeaderConfig, SO101Leader
from lerobot.robots.so101_follower import SO101FollowerConfig, SO101Follower

robot_config = SO101FollowerConfig(
    port="/dev/ttyACM0",
    id="leader_arm",
)

robot = SO101Follower(robot_config)
robot.connect()

teleop_config = SO101LeaderConfig(
    port="/dev/ttyACM1",
    id="follower_arm",
)
teleop_device = SO101Leader(teleop_config)
teleop_device.connect()

while True:
    action = teleop_device.get_action()
    robot.send_action(action)