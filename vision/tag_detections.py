import cv2
import numpy as np

class Item:
    def __init__(self, name , idx):
        self.name = name
        self.idx = idx
        self.x = 0
        self.y = 0
        self.size = 0
    
    def setPosition(self, x, y, size):
        self.x = x
        self.y = y
        self.size = size

items = [Item("cup", 0), Item("bowl", 1), Item("fruit", 2)]

cam = cv2.VideoCapture(1)

# Load AprilTag 36h11 dictionary
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)

# Create detector parameters and detector
params = cv2.aruco.DetectorParameters()
params.adaptiveThreshWinSizeMin = 3
params.adaptiveThreshWinSizeMax = 15
params.adaptiveThreshWinSizeStep = 2
params.minMarkerPerimeterRate = 0.002   # lower threshold for smaller tags
params.maxMarkerPerimeterRate = 4.0
params.minCornerDistanceRate = 0.02
params.minMarkerDistanceRate = 0.02
params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
params.polygonalApproxAccuracyRate = 0.03

detector = cv2.aruco.ArucoDetector(aruco_dict, params)

while True:
    ret, frame = cam.read()
    if not ret:
        break

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # denoise
    # gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # # increase contrast
    # clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    # gray = clahe.apply(gray)

    # # sharpen
    # gray = cv2.addWeighted(gray, 1.5, cv2.GaussianBlur(gray, (0, 0), 3), -0.5, 0)

    # Detect AprilTags
    corners, ids, rejected = detector.detectMarkers(gray)

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

            # Draw marker outline and center
            cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
            cv2.circle(frame, (cX, cY), 5, (0, 0, 255), -1)

            # Draw tag ID
            tag_id = int(ids[i])
            cv2.putText(frame, f"ID {tag_id}", (ptA[0], ptA[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Print info
            for i in items:
                if i.idx == tag_id:
                    i.setPosition(cX, cY, avg_size)

    for i in items:
        print(f"Item {i.name}, ID: {i.idx}, Center: ({i.x}, {i.y}), Size: {i.size}px")

    # Show video
    cv2.imshow("Detection", frame)

    # Quit with 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cam.release()
cv2.destroyAllWindows()
