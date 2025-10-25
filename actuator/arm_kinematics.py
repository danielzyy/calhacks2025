# include parent dir
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import math
import numpy as np
from actuator.dh_table import *

def compute_inverse_kinematics_wrist_desired_pos(x, y, z):
    """Compute inverse kinematics for a 3DOF arm.

    Args:
        x (float): X coordinate of the end effector.
        y (float): Y coordinate of the end effector.
        z (float): Z coordinate of the end effector.

    Description:
        Straight out of ME547 lol

    """

    joint_1 = np.arctan2(y, x) # base rotation
    r = np.sqrt(x**2 + y**2)
    delta_r = r - L1 # horizontal distance from shoulder joint
    s = z - L2 # vertical distance from shoulder joint

    # Solve standard 2 link inverse kinematics problem
    F = (delta_r**2 + s**2 - L3**2 - L4**2) / (2 * L3 * L4)

    joint_3 = np.arctan2(np.sqrt(1 - F**2), F)  # elbow flex. 2 solutions, we take the elbow-up one (todo, mayb not?)
    joint_2 = np.arctan2(s, delta_r) - np.arctan2(L4 * np.sin(joint_3), L3 + L4 * np.cos(joint_3))  # shoulder lift

    return np.array([joint_1, joint_2, joint_3])

def compute_end_effector_pos_from_joints(joint_angles):
    """Compute end effector position from joint angles using forward kinematics.

    Args:
        joint_angles (np.array): Array of joint angles [joint_1, joint_2, joint_3, joint_4, joint_5].
    Returns:
        np.array: End effector position [x, y, z].

    """

    T = []
    T_overall = np.eye(4)
    for i in range(len(joint_angles)):
        theta = joint_angles[i] + ROBOT_DH_TABLES[i][0]
        d = ROBOT_DH_TABLES[i][1]
        a = ROBOT_DH_TABLES[i][2]
        alpha = ROBOT_DH_TABLES[i][3]
        T.append(dh_transform_matrix(theta, d, a, alpha))
        T_overall = T_overall @ T[-1]

    # End effector position
    end_effector_pos = T_overall[:3, 3]
    return end_effector_pos

if __name__ == "__main__":
    # Test conversion functions
    dh_angles = np.zeros(5)
    dh_angles = [0, 90, 0, 00, 0]
    dh_angles = np.deg2rad(dh_angles)
    compute_end_effector_pos_from_joints(dh_angles)
    breakpoint()