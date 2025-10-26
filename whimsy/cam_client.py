# client.py
import cv2
import sys
import time

# Replace with your host IP if needed. If WSL can reach localhost, use localhost.
# Example: url = "http://172.24.0.1:8000/video_feed"
#url = "http://{HOST_OR_IP}:8000/video_feed".replace("{HOST_OR_IP}", "localhost")  # edit if needed
url = "http://172.24.118.106:8000/video_feed"

cap = cv2.VideoCapture(url)
if not cap.isOpened():
    print(f"cv2.VideoCapture couldn't open {url}. Try editing HOST_OR_IP to your Windows host IP.")
    sys.exit(1)

print("Client: opened stream, press 'q' to quit.")
while True:
    ret, frame = cap.read()
    if not ret:
        # If stream breaks, wait and retry
        time.sleep(0.1)
        continue
    cv2.imshow("WSL client view", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
