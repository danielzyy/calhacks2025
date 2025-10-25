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

    theta1, theta2, theta3, theta4, theta5 = joint_angles

    T1 = dh_transform_matrix(joint_angles[0], L2, L1, np.pi / 2)
    T2 = dh_transform_matrix(joint_angles[1], 0, L3, 0)
    T3 = dh_transform_matrix(joint_angles[2], 0, L4, 0)
    T4 = dh_transform_matrix(joint_angles[3], 0, 0, -np.pi / 2)
    T5 = dh_transform_matrix(joint_angles[4], L5, 0, 0)

    # Overall transformation matrix
    T = T1 @ T2 @ T3 @ T4 @ T5

    # End effector position
    end_effector_pos = T[:3, 3]

    return end_effector_pos
