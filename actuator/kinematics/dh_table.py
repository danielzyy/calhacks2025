# include parent dir
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from actuator.kinematics.constants import *

"""See https://github.com/Argo-Robot/controls/tree/main for derivation"""

# Follow this convention: theta , d, a, alpha
ROBOT_DH_TABLES = [
        [0, L2, L1, np.pi / 2],
        [0, 0.0, L3, 0.0],
        [0, 0.0, L4, 0.0],
        [0, 0.0, 0.0, -np.pi / 2],
        [0, L5, 0.0, 0.0],  # to increase length and include also gripper: [0, 0.155, 0.0, 0.0],
        [0, 0.0, 0.0, 0.0],  # gripper
]

def dh_to_mech_angles(q_dh):
    q_mech = np.zeros_like(q_dh)

    q_mech[0] = -q_dh[0]
    q_mech[1] = -q_dh[1] - beta + np.pi/2
    q_mech[2] = -q_dh[2] + beta - np.pi/2
    q_mech[3] = -q_dh[3] - np.pi/2
    q_mech[4] =  q_dh[4]
    q_mech[5] = q_dh[5]  # gripper

    return q_mech

def mech_to_dh_angles(q_mech):
    joint_1 = q_mech[0] * -1.0
    joint_2 = q_mech[1] * -1.0 - beta + np.pi/2
    joint_3 = q_mech[2] * -1.0 + beta - np.pi/2
    joint_4 = q_mech[3] * -1.0 - np.pi/2
    joint_5 = q_mech[4]
    joint_6 = q_mech[5]  # gripper
    return np.array([joint_1, joint_2, joint_3, joint_4, joint_5, joint_6])

def dh_transform_matrix(theta, d, a, alpha):
    """Compute the Denavit-Hartenberg transformation matrix.

    Args:
        theta (float): Joint angle in radians.
        d (float): Link offset.
        a (float): Link length.
        alpha (float): Link twist in radians.

    Returns:
        np.array: 4x4 transformation matrix.

    """
    ct = np.cos(theta)
    st = np.sin(theta)
    ca = np.cos(alpha)
    sa = np.sin(alpha)

    return np.array([
        [ct, -st * ca, st * sa, a * ct],
        [st, ct * ca, -ct * sa, a * st],
        [0, sa, ca, d],
        [0, 0, 0, 1]
    ])
