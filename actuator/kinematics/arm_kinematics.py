# include parent dir
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import math
import numpy as np
from actuator.kinematics.dh_table import *

def get_euclidian_distance(x, y):
    return (x**2 + y**2)**0.5

def compute_inverse_kinematics_elbow_desired_pos(x, y, z):
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

    joint_3 = np.arctan2(-np.sqrt(1 - F**2), F)  # elbow flex. 2 solutions, we take the elbow-up one (todo, mayb not?)
    joint_2 = np.arctan2(s, delta_r) - np.arctan2(L4 * np.sin(joint_3), L3 + L4 * np.cos(joint_3))  # shoulder lift

    return np.array([joint_1, joint_2, joint_3])

def compute_inverse_kinematics_at_desired_wrist_position(x, y, z, wrist_angle=0.0):
    """Compute inverse kinematics for a 3DOF arm with wrist angle consideration.

    Args:
        x (float): X coordinate of the end effector.
        y (float): Y coordinate of the end effector.
        z (float): Z coordinate of the end effector.
        wrist_angle (float): Desired wrist angle in radians. The wrist angle is defined as the
        rotation between x0 and x_end_effector about z_end_effector.

    Description:
        Adjusts for wrist orientation by calculating the position of the wrist joint
        before applying standard 2-link inverse kinematics.

    """

    # wrist position is desired to be located at the end effector. We need to backtrack L5 along the wrist angle
    # to find the elbow position
    joint_1 = np.arctan2(y, x) # base rotation angle, needed here
    elbow_z = z - L5 * np.sin(wrist_angle)
    elbow_r = L5 * np.cos(wrist_angle)

    # propagate back from end effector to elbow position
    elbow_x = x - elbow_r * np.cos(joint_1)
    elbow_y = y - elbow_r * np.sin(joint_1)

    elbow_joint_angles = compute_inverse_kinematics_elbow_desired_pos(elbow_x, elbow_y, elbow_z)
    # theta_2 + theta_3 + theta_4 = theta_5
    # where theta_5 = wrist_angle - np.pi/2
    joint_4 = wrist_angle - np.pi/2 - (elbow_joint_angles[1] + elbow_joint_angles[2])
    return np.array([elbow_joint_angles[0], elbow_joint_angles[1], elbow_joint_angles[2], joint_4])


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