import cv2 as cv
import numpy as np

# ============================
# USER SETTINGS (EDIT THESE)
# ============================
CAM_INDEX = 0                 # camera index
CENTER_TAG_ID = 0              # the "host/center" AprilTag id
MARKER_LENGTH_M = 0.039        # tag edge length (meters), black square edge

# OFFSET_X = -135
# OFFSET_Y = -10 # measured camera offset + claw offset
PIXEL_TO_MM = 145/116
# ---- Paste your calibration here (examples below are placeholders) ----
camera_matrix = np.array([
    [685.46021183, 0.0, 944.39424736],
    [0.0, 684.30342537, 569.23975487],
    [0.0,   0.0,   1.0]
    ], dtype=np.float32)

# Accepts shapes (5,), (1,5), (1,8) etc. Fill with your real coeffs.
dist_coeffs = np.array([0.07242768, -0.08209194,  0.00019658, -0.00150527,  0.01044681], dtype=np.float32)
# =======================================================================
# If your K was calibrated at a known resolution (w,h),
# set CALIB_IMAGE_SIZE to that. The script will scale K to the live stream size.
# If K already matches your live resolution, set this to None.
CALIB_IMAGE_SIZE = None  # e.g., (1280, 720) or None
# ============================

class Item:
    def __init__(self, name , idx, offsetx, offsety):
        self.name = name
        self.idx = idx
        self.x = 0 # CAMERA FRAME
        self.y = 0 # CAMERA FRAME
        self.size = 0
        self.x_rel_arm = 0 # ARM FRAME
        self.y_rel_arm = 0 # ARM FRAME
        self.offsetx = offsetx
        self.offsety = offsety
    
    def setPosition(self, x, y, size):
        self.x = x + self.offsetx
        self.y = y + self.offsety
        self.size = size
    
    def getRelPosition(self, base):
        # Translate to arm frame
        self.x_rel_arm = round(((-self.y) - (-base.y)) * PIXEL_TO_MM)
        self.y_rel_arm = round((-self.x - (-base.x)) * PIXEL_TO_MM)

items = [Item("base", 0, -135, -10), Item("pepsi_cup", 1, -25, 0), Item("cookies_cup", 2, -40, 0), Item("lettuce_cup", 3, -80, 0)]

HEIGHT_OFFSET = -50
def getItemPositions():
    positions = []
    for i in items:
        positions.append({"Name": i.name, "Absolute X": i.x_rel_arm, "Absolute Y": i.y_rel_arm, "Absolute Z": HEIGHT_OFFSET})
    return positions

def relative_pos(base, item):
    return ((item.x - base.x), (item.y - base.y))

def scale_K(K, from_size, to_size):
    """Scale intrinsics from calibration resolution -> runtime resolution."""
    fx, fy = K[0,0], K[1,1]
    cx, cy = K[0,2], K[1,2]
    sx = to_size[0] / float(from_size[0])
    sy = to_size[1] / float(from_size[1])
    K2 = K.copy()
    K2[0,0] = fx * sx
    K2[1,1] = fy * sy
    K2[0,2] = cx * sx
    K2[1,2] = cy * sy
    return K2

def invert_rvec_tvec(rvec, tvec):
    R, _ = cv.Rodrigues(rvec)
    Rinv = R.T
    tinv = -Rinv @ tvec.reshape(3)
    rvec_inv, _ = cv.Rodrigues(Rinv)
    return rvec_inv.reshape(3), tinv.reshape(3)

def relative_pose_in_center(poses_cam, center_id):
    r_c_inv, t_c_inv = invert_rvec_tvec(*poses_cam[center_id])
    rel = {}
    for tid, (r, t) in poses_cam.items():
        r_rel, t_rel, *_ = cv.composeRT(r_c_inv, t_c_inv, r, t)
        rel[tid] = (r_rel.reshape(3), t_rel.reshape(3))
    return rel

def estimate_pose_best_ippe(corners, marker_length, K, D):
    """
    For each marker, run solvePnPGeneric(IPPE_SQUARE) and pick the solution
    with the lowest reprojection error. Returns arrays rvecs (N,3), tvecs (N,3).
    """
    half = marker_length / 2.0
    # Corner order must match detector's: TL, TR, BR, BL (OpenCV ArUco does this)
    obj_pts = np.array([
        [-half,  half, 0.0],  # TL
        [ half,  half, 0.0],  # TR
        [ half,-half, 0.0],   # BR
        [-half,-half, 0.0],   # BL
    ], dtype=np.float32)

    r_out, t_out = [], []
    for c in corners:
        pts2d = c.reshape(-1, 2).astype(np.float32)

        ok, rvecs, tvecs, _ = cv.solvePnPGeneric(
            obj_pts, pts2d, K, D, flags=cv.SOLVEPNP_IPPE_SQUARE
        )
        if not ok or len(rvecs) == 0:
            r_out.append(np.full(3, np.nan)); t_out.append(np.full(3, np.nan)); continue

        # Choose the solution with the smallest reprojection error
        best_i, best_err = 0, 1e9
        for i in range(len(rvecs)):
            proj, _ = cv.projectPoints(obj_pts, rvecs[i], tvecs[i], K, D)
            err = cv.norm(proj.reshape(-1, 2), pts2d, cv.NORM_L2) / len(pts2d)
            if err < best_err:
                best_err, best_i = err, i

        r_out.append(rvecs[best_i].reshape(3))
        t_out.append(tvecs[best_i].reshape(3))

    return np.asarray(r_out), np.asarray(t_out)


cap = None
detector = None

def camera_setup():
    global cap
    global detector

    # --- Detector setup with subpixel refinement ---
    aruco_dict = cv.aruco.getPredefinedDictionary(cv.aruco.DICT_APRILTAG_36h11)

    # Create detector parameters and detector
    params = cv.aruco.DetectorParameters()
    params.adaptiveThreshWinSizeMin = 3
    params.adaptiveThreshWinSizeMax = 15
    params.adaptiveThreshWinSizeStep = 2
    params.minMarkerPerimeterRate = 0.002   # lower threshold for smaller tags
    params.maxMarkerPerimeterRate = 4.0
    params.minCornerDistanceRate = 0.02
    params.minMarkerDistanceRate = 0.02
    params.cornerRefinementMethod = cv.aruco.CORNER_REFINE_SUBPIX
    params.polygonalApproxAccuracyRate = 0.03
    detector = cv.aruco.ArucoDetector(aruco_dict, params)

    cap = cv.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera")

    # Get runtime resolution
    W = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
    K_runtime = camera_matrix.copy()
    if CALIB_IMAGE_SIZE is not None and (W, H) != tuple(CALIB_IMAGE_SIZE):
        K_runtime = scale_K(camera_matrix, CALIB_IMAGE_SIZE, (W, H))
        print(f"Scaled K from {CALIB_IMAGE_SIZE} -> {(W, H)}")

def camera_run():
    global cap
    global detector
    show_viz = False

    ok, frame = cap.read()
    if not ok:
        return

    gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)

    if ids is not None:
        for i, corner in enumerate(corners):
            # Flatten the corner array
            pts = corner[0].astype(int)
            (ptA, ptB, ptC, ptD) = pts

            # Compute center
            cX = int(np.mean(pts[:, 0]))
            cY = int(np.mean(pts[:, 1]))

            # Compute average side length as size estimate
            side_lengths = [
                np.linalg.norm(ptA - ptB),
                np.linalg.norm(ptB - ptC),
                np.linalg.norm(ptC - ptD),
                np.linalg.norm(ptD - ptA)
            ]
            avg_size = np.mean(side_lengths)
            tag_id = int(ids[i])


            # Draw marker outline and center
            if show_viz:
                cv.polylines(frame, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
                cv.circle(frame, (cX, cY), 5, (0, 0, 255), -1)
                # # Draw tag ID
                cv.putText(frame, f"ID {tag_id}", (ptA[0], ptA[1] - 10),
                            cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Print info
            for item in items:
                if item.idx == tag_id:
                    # if tag_id == 0:
                    #     cX += OFFSET_X
                    #     cY += OFFSET_Y
                    item.setPosition(cX, cY, avg_size)
                    item.getRelPosition(items[0])

    # for i in items:
    #     print(f"Item {i.name}, ID: {i.idx}, Center: ({i.x}, {i.y}), Size: {i.size}px, x_rel_arm: {i.x_rel_arm}, y_rel_arm: {i.y_rel_arm}")
        # pass

    # print(f"run")

    # Show video
    if show_viz:
        cv.imshow("Detection", frame)
        if cv.waitKey(1) & 0xFF == ord('q'):
            return

# 210 0.155