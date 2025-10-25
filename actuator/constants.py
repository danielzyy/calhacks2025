import numpy as np

JOINT_NAMES_AS_INDEX = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
]

L1 = 0.0304
L2 = 0.0542
L3 = 0.116
L4 = 0.1347
L5 = 0.0155  # including gripper length 
L5 = 0

beta = np.deg2rad(14.45)  # make reference to dh2.png in README.md