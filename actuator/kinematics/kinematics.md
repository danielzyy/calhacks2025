# SOARM-100 Kinematics

A key requirement of being able to make a hardware-context-protocol (HCP) compliant device is creating an abstraction that makes it easy to command the device's physical behaviour. For a robot arm like the SOARM-101, this means exposing an API by which the end effector position can be controlled.

The SOARM-100 library offers us only the ability to do joint control, and as a result, required us to analytically develop the inverse kinematic solution to be able to command arbitrary end effector position.

## DH Parameters
The axis convention and D-H parameters are identical to those defined in [this repository](https://github.com/Argo-Robot/controls/tree/main).

## Forward Kinematics Modelling
The forward kinematics model works by propagating the D-H parameters across all of the joints to determine the end effector rotation and translation matrix. The forward kinematics model is primarily used as a sanity check on the inverse kinematic model to ensure that the joint angles lead to the same solution, as the forward kinematics are easy to experimentally verify and visualize.

The algorithm is summarized as follows:
1) Define the D-H parameters for each joint in the robot arm.
2) For each joint, compute the individual transformation matrix using the D-H parameters.
3) Multiply the individual transformation matrices together to get the overall transformation matrix from the base to the end effector.
4) Extract the position and orientation of the end effector from the overall transformation matrix.

## Inverse Kinematics Solution Development
The inverse kinematics solution was analytically derived via a geometric approach. 

Let $x_t, y_t, z_t$ be the target end effector parameters. 

### Base Link
Since the robot is axially constrained about the +Z world frame axis, the first link's solution can be determined by finding the angle of incidence from the target end effector position to the base. 
$\theta_1 = atan2(y_t, x_t)$ 

### Radial Links
In order to simplify the kinematic analysis, the scope of the inverse kinematic problem is limited to find solutions which support a wrist approach angle (in laymans terms, the angle at which the wrist approaches a point). As a result, the inverse kinematics problem breaks apart into 2 steps
1) Solve for the required elbow position given the target end effector position and desired wrist approach angle ($\theta_{wrist-approach}$). 

We can solve for the required height of the elbow as a function of the wrist length ($L_5$) and wrist approach angle as follows:

$z_t = z_{elbow} + L_5\sin(\theta_5)$

We can also solve for the required radial length (how far out the arm needs to be) at the elbow as a function of the above-mentioned wrist parameters. Let $r_{target} = (x_t ^ 2 + y_t ^ 2)$
$r_{elbow} = r_{target} - L_5\cos(\theta_5) = r_{target} - r_{wrist}$

This allows us to define
- $x_{elbow} = x_{target} - r_{wrist}\cos{\theta_1}$
- $y_{elbow} = y_{target} - r_{wrist}\sin{\theta_1}$

2) Solve the 2-link planar arm problem to find the required joint angles to reach the elbow position.

The 2-link planar arm inverse kinematics solution is well-documented and applied to the $x_{elbow}, y_{elbow}, z_{elbow}$ position to find the required joint angles $\theta_2, \theta_3$.
- Let $r = \sqrt{x_{elbow}^2 + y_{elbow}^2}$
- Let $F = \frac{r^2 + (z_{elbow} - L_1)^2 - L_2^2 - L_3^2}{2 L_2 L_3}$ (where $L_1$ is the height of the first joint from the base)
- Then $\theta_3 = atan2(\pm \sqrt{1 - F^2}, F)$ (elbow up/down - elbow up is chosen.)
- And $\theta_2 = atan2(z_{elbow} - L_1, r) - atan2(L_3 \sin(\theta_3), L_2 + L_3 \cos(\theta_3))$

### Wrist Orientation
Finally, the wrist orientation is determined by the desired wrist approach angle and the previously calculated joint angles.
$\theta_5 = \theta_2 + \theta_3 + \theta_4 = \theta_{wrist-approach} - \pi/2$
Therefore, $\theta_4 = \theta_{wrist-approach} - \pi/2 - (\theta_2 + \theta_3)$

## Implementation
The inverse kinematics solution to the 2-link problem is implemented in `actuator/kinematics/arm_kinematics.py` in the `compute_inverse_kinematics_arm_target_pos` function. This is invoked by a higher-level function `compute_inverse_kinematics_arm_target_pos_wrist_approach` which computes the elbow position given the wrist approach angle before invoking the 2-link solution.