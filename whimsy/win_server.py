# server.py
import time
import threading
from flask import Flask, Response, render_template_string, jsonify
import cv2

app = Flask(__name__)

# Config
CAM_INDEX = 0           # change if your webcam is at different index
PORT = 8000

# Shared state
last_frame_time = 0.0
frames_served = 0
last_frame_shape = (0, 0)

# OpenCV capture
cap = cv2.VideoCapture(CAM_INDEX)
if not cap.isOpened():
    raise RuntimeError(f"Could not open camera index {CAM_INDEX}")

# Quick server-side preview window so you can visually confirm on the Windows host
def preview_loop():
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue
        cv2.imshow("Server webcam preview (press q to close)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()

# Start preview thread (daemon so flask shutdown doesn't hang)
preview_thread = threading.Thread(target=preview_loop, daemon=True)
preview_thread.start()

def generate_mjpeg():
    global last_frame_time, frames_served, last_frame_shape
    while True:
        ret, frame = cap.read()
        if not ret:
            # brief wait to avoid tight-loop if camera hiccups
            time.sleep(0.05)
            continue

        last_frame_time = time.time()
        last_frame_shape = frame.shape[:2]  # h, w
        # JPEG encode
        ret2, jpg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret2:
            continue
        jpg_bytes = jpg.tobytes()
        frames_served += 1

        # yield multipart chunk
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpg_bytes + b'\r\n')

@app.route('/')
def index():
    # Simple HTML page that embeds the MJPEG stream
    html = """
    <html>
    <head><title>Webcam MJPEG stream</title></head>
    <body>
      <h3>Webcam stream</h3>
      <img src="/video_feed" style="max-width:100%;">
      <p><a href="/status">/status</a> shows server-confirmation JSON.</p>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/video_feed')
def video_feed():
    return Response(generate_mjpeg(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    # Provide confirmation info that the webcam feed is working
    now = time.time()
    age = None
    if last_frame_time:
        age = now - last_frame_time
    return jsonify({
        "ok": True,
        "frames_served": frames_served,
        "last_frame_age_seconds": age,
        "last_frame_shape_hxw": last_frame_shape
    })

if __name__ == '__main__':
    print(f"Starting server on 0.0.0.0:{PORT}")
    print(f"Open http://<WINDOWS_IP>:{PORT}/ in WSL/web browser (or http://localhost:{PORT}/ if accessible).")
    # Bind to 0.0.0.0 so WSL can reach it via the host IP
    app.run(host='0.0.0.0', port=PORT, threaded=True)
