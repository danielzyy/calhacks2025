import matplotlib.pyplot as plt

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from actuator.kinematics.dh_table import *
from actuator.kinematics.arm_kinematics import *
from actuator.kinematics.constants import *

class Visualizer:
    def __init__(self):
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_xlabel('X axis')
        self.ax.set_ylabel('Y axis')
        self.ax.set_zlabel('Z axis')
        self.ax.set_title('Robotic Arm Visualization')
        plt.show(block=False)

    def plot(self, joint_positions, target=None):
        """
        Plot the arm skeleton (base -> joints -> end-effector) and optional target.

        Args:
            joint_positions: iterable of joint angles (radians) expected by
                            compute_end_effector_pos_from_joints().
            target: optional (x, y, z) tuple/array to draw as a marker.
        """

        # Clear and relabel
        self.ax.cla()
        self.ax.set_xlabel('X axis')
        self.ax.set_ylabel('Y axis')
        self.ax.set_zlabel('Z axis')
        self.ax.set_title('Robotic Arm Visualization')

        # Collect points: start at base (0,0,0), then each joint/EE position
        points = [np.array([0.0, 0.0, 0.0], dtype=float)]

        # Number of plotted segments = len(joint_positions)
        # We assume the FK function returns the position of the frame after `idx` joints.
        n = len(joint_positions)
        q = np.asarray(joint_positions, dtype=float)

        for idx in range(1, n + 1):
            ee_pos = compute_end_effector_pos_from_joints(q[:idx])
            p = np.asarray(ee_pos, dtype=float).reshape(3)
            points.append(p)

        pts = np.vstack(points)  # shape (n+1, 3)
        xs, ys, zs = pts[:, 0], pts[:, 1], pts[:, 2]

        # Plot links and joints
        self.ax.plot(xs, ys, zs, marker='o')  # skeleton
        self.ax.scatter(xs[0], ys[0], zs[0], s=40)         # base marker
        self.ax.scatter(xs[-1], ys[-1], zs[-1], s=60)      # EE marker

        # Optional target
        if target is not None:
            tx, ty, tz = np.asarray(target, dtype=float).reshape(3)
            self.ax.scatter([tx], [ty], [tz], s=60, marker='x')

        # Auto-scale with a margin and set equal aspect
        all_pts = pts.copy()
        if target is not None:
            all_pts = np.vstack([all_pts, np.asarray(target, dtype=float).reshape(3)])

        mins = all_pts.min(axis=0)
        maxs = all_pts.max(axis=0)
        center = 0.5 * (mins + maxs)
        span = (maxs - mins)
        max_range = max(span.max(), 1e-3)  # avoid zero range
        margin = 0.15 * max_range
        low = center - 0.5 * max_range - margin
        high = center + 0.5 * max_range + margin

        self.ax.set_xlim(low[0], high[0])
        self.ax.set_ylim(low[1], high[1])
        self.ax.set_zlim(low[2], high[2])
        # equal aspect for 3D
        self.ax.set_box_aspect((high - low))

        # Make interactive updates smooth when called inside a loop
        plt.pause(0.001)

