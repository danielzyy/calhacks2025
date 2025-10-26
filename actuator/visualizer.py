import matplotlib.pyplot as plt
import numpy as np
from collections import deque
from actuator.kinematics.arm_kinematics import compute_end_effector_pos_from_joints

class Visualizer:
    def __init__(self, base_coordinate_marker_size=0.01, trail_len=100):
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111, projection='3d')

        # Aesthetic tweaks
        self.ax.set_facecolor((0.98, 0.98, 1.0))
        self.ax.grid(True, alpha=0.25)
        self.ax.view_init(elev=20, azim=-45)

        # Lighter pane colors
        for axis in (self.ax.xaxis, self.ax.yaxis, self.ax.zaxis):
            axis.pane.set_edgecolor((0.85, 0.85, 0.95, 0.6))
            axis.pane.set_facecolor((0.92, 0.92, 0.98, 0.6))

        self.base_axes_len = float(base_coordinate_marker_size)
        self.ee_traj = deque(maxlen=int(trail_len))

        self.ax.set_xlabel('X axis')
        self.ax.set_ylabel('Y axis')
        self.ax.set_zlabel('Z axis')
        self.ax.set_title('Robotic Arm Visualization')
        plt.ion()
        plt.show(block=False)

    def _draw_base_triad(self):
        L = self.base_axes_len
        O = np.array([0.0, 0.0, 0.0])

        # Axis triad
        self.ax.quiver(O[0], O[1], O[2], L, 0, 0, length=1.0, normalize=False, arrow_length_ratio=0.15)
        self.ax.quiver(O[0], O[1], O[2], 0, L, 0, length=1.0, normalize=False, arrow_length_ratio=0.15)
        self.ax.quiver(O[0], O[1], O[2], 0, 0, L, length=1.0, normalize=False, arrow_length_ratio=0.15)
        # Labels
        self.ax.text(L, 0, 0, 'X', fontsize=9, ha='left', va='bottom')
        self.ax.text(0, L, 0, 'Y', fontsize=9, ha='left', va='bottom')
        self.ax.text(0, 0, L, 'Z', fontsize=9, ha='left', va='bottom')

    def plot(self, joint_positions, target=None):
        """
        Plot the arm skeleton (base -> joints -> end-effector), optional target, and EE trail.

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
        self.ax.grid(True, alpha=0.25)

        # Base coordinate marker (triad)
        self._draw_base_triad()

        # Collect points: base -> joints -> EE
        points = [np.array([0.0, 0.0, 0.0], dtype=float)]
        q = np.asarray(joint_positions, dtype=float)
        n = len(q)

        for idx in range(1, n + 1):
            # FK for first idx joints
            ee_pos = compute_end_effector_pos_from_joints(q[:idx])
            p = np.asarray(ee_pos, dtype=float).reshape(3)
            points.append(p)

        pts = np.vstack(points)  # (n+1, 3)
        xs, ys, zs = pts[:, 0], pts[:, 1], pts[:, 2]

        # Links + joints styling
        self.ax.plot(xs, ys, zs, linewidth=3.0, alpha=0.9)
        self.ax.scatter(xs[1:-1], ys[1:-1], zs[1:-1], s=25, depthshade=True)  # intermediate joints
        self.ax.scatter(xs[0], ys[0], zs[0], s=40, depthshade=True)           # base
        self.ax.scatter(xs[-1], ys[-1], zs[-1], s=70, depthshade=True)        # EE

        # Optional target + line from EE to target
        if target is not None:
            tx, ty, tz = np.asarray(target, dtype=float).reshape(3)
            self.ax.scatter([tx], [ty], [tz], s=60, marker='x')
            self.ax.plot([xs[-1], tx], [ys[-1], ty], [zs[-1], tz], linestyle='--', linewidth=1.5, alpha=0.7)

        # EE trail (smooth motion feel)
        self.ee_traj.append(pts[-1])
        if len(self.ee_traj) > 1:
            tr = np.vstack(self.ee_traj)
            self.ax.plot(tr[:, 0], tr[:, 1], tr[:, 2], linewidth=1.5, alpha=0.6)

        # Auto-scale with margin; equal aspect
        all_pts = pts.copy()
        if target is not None:
            all_pts = np.vstack([all_pts, np.array([tx, ty, tz])])

        mins = all_pts.min(axis=0)
        maxs = all_pts.max(axis=0)
        center = 0.5 * (mins + maxs)
        span = (maxs - mins)
        max_range = max(span.max(), 1e-3)
        margin = 0.20 * max_range
        low = center - 0.5 * max_range - margin
        high = center + 0.5 * max_range + margin

        self.ax.set_xlim(low[0], high[0])
        self.ax.set_ylim(low[1], high[1])
        self.ax.set_zlim(low[2], high[2])
        self.ax.set_box_aspect((high - low))

        # Subtle camera drift to avoid static feel (optional)
        elev, azim = self.ax.elev, self.ax.azim
        self.ax.view_init(elev=elev, azim=azim + 0.2)

        # Draw now
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(0.001)
