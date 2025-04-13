# =================================================================
# Section 1: Imports and Flask App Initialization
# =================================================================
from flask import Flask, Response, jsonify
import socket
import struct
import threading
import time
import traceback
import cv2
import numpy as np
from fall_detection import process_frame

app = Flask(__name__)

# =================================================================
# Section 2: Global Variables
# =================================================================
latest_frame_jpeg = None
frame_lock = threading.Lock()
fall_warning = "No Fall Detected"

# =================================================================
# Section 3: Socket Server Thread for Receiving Image Data
# =================================================================
def socket_server_thread():
    global latest_frame_jpeg
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', 9999))
    server_socket.listen(5)
    print("[*] Socket server is listening on 0.0.0.0:9999")
    payload_size = struct.calcsize(">L")

    while True:
        conn = None
        addr = None
        try:
            conn, addr = server_socket.accept()
            print(f"[*] Accepted connection from {addr}")
            data = b""
            while True:
                while len(data) < payload_size:
                    packet = conn.recv(4096)
                    if not packet:
                        break
                    data += packet
                if not packet:
                    print(f"[*] Client {addr} disconnected (payload size)")
                    break

                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                if len(packed_msg_size) < payload_size:
                    print(f"[*] Client {addr} disconnected (incomplete size)")
                    break

                msg_size = struct.unpack(">L", packed_msg_size)[0]
                while len(data) < msg_size:
                    packet = conn.recv(4096)
                    if not packet:
                        break
                    data += packet
                if not packet:
                    print(f"[*] Client {addr} disconnected (data reception)")
                    break
                if len(data) < msg_size:
                    print(f"[*] Client {addr} disconnected (incomplete data)")
                    break

                frame_data = data[:msg_size]
                data = data[msg_size:]
                with frame_lock:
                    latest_frame_jpeg = frame_data
        except Exception as e:
            print(f"[!] Socket thread error: {e}")
            traceback.print_exc()
        finally:
            if conn:
                print(f"[*] Closed connection from {addr}")
                conn.close()
            time.sleep(0.5)

# =================================================================
# Section 4: Frame Generator for the Video Feed
# =================================================================
def generate_frames():
    while True:
        frame_to_send = None
        with frame_lock:
            if latest_frame_jpeg:
                frame_to_send = latest_frame_jpeg
        if frame_to_send is None:
            time.sleep(0.1)
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')
        time.sleep(0.03)

# =================================================================
# Section 5: Flask Routes
# =================================================================
@app.route('/')
def index():
    vm_tailscale_ip = "change to your ip"
    return f"""
    <html>
    <head>
        <title>Raspberry Pi Video Streaming (Tailscale)</title>
        <script>
            async function updateFallStatus() {{
                try {{
                    let response = await fetch('/fall_status');
                    let data = await response.json();
                    document.getElementById('fall_warning').innerText = data.status;
                }} catch (error) {{
                    console.error('Failed to fetch fall status:', error);
                }}
            }}
            setInterval(updateFallStatus, 1000);
            window.onload = updateFallStatus;
        </script>
    </head>
    <body>
        <h1>Real-time Video from Raspberry Pi (Tailscale)</h1>
        <p>Access this page using the VM's Tailscale IP: http://{vm_tailscale_ip}:{5000}</p>
        <img src="/video_feed" width="640" height="480">
        <h2>Fall Warning:</h2>
        <div id="fall_warning" style="font-size: 24px; color: red;">No Fall Detected</div>
        <p>Server Time: <span id="time"></span></p>
         <script>
            function updateTime() {{
                document.getElementById('time').innerText = new Date().toLocaleTimeString();
            }}
            setInterval(updateTime, 1000);
            updateTime();
         </script>
    </body>
    </html>
    """

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/fall_status')
def fall_status():
    global fall_warning
    return jsonify(status=fall_warning)

# =================================================================
# Section 6: Fall Detection Thread
# =================================================================
def fall_detection_thread():
    global latest_frame_jpeg, fall_warning
    while True:
        frame_data = None
        with frame_lock:
            if latest_frame_jpeg:
                frame_data = latest_frame_jpeg[:]
        if frame_data:
            np_data = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
            if frame is not None:
                fall_detected, annotated_frame = process_frame(frame)
                ret, jpeg = cv2.imencode('.jpg', annotated_frame)
                if ret:
                    with frame_lock:
                        latest_frame_jpeg = jpeg.tobytes()
                fall_warning = "Fall Detected!" if fall_detected else "No Fall Detected"
                if fall_detected:
                    print("[INFO] Fall or abnormal movement detected!")
        time.sleep(0.2)

# =================================================================
# Section 7: Server Startup
# =================================================================
if __name__ == '__main__':
    socket_thread = threading.Thread(target=socket_server_thread, daemon=True)
    socket_thread.start()
    detection_thread = threading.Thread(target=fall_detection_thread, daemon=True)
    detection_thread.start()
    print("[*] Flask server is running on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
