import cv2
import socket
import struct
import time

# =================================================================
# Section 1: Configuration Parameters
# =================================================================
SERVER_IP = 'change to your vpn ip'  # Virtual Machine Tailscale IP
SERVER_PORT = 9999                   # Server port
RECONNECT_DELAY = 5                  # Delay for reconnect attempts (seconds)
JPEG_QUALITY = 70                    # JPEG compression quality (0-100)
RESIZE_WIDTH = 640                   # Target width for image resizing (0 means no resize)

# =================================================================
# Section 2: Establishing Connection to the Server
# =================================================================
def connect_to_server():
    """Continuously attempts to connect to the backend server."""
    while True:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"[INFO] Attempting to connect to {SERVER_IP}:{SERVER_PORT} ...")
            client_socket.connect((SERVER_IP, SERVER_PORT))
            print("[INFO] Successfully connected to the server!")
            return client_socket
        except socket.error as e:
            print(f"[ERROR] Connection failed: {e}. Retrying in {RECONNECT_DELAY} seconds...")
            time.sleep(RECONNECT_DELAY)

# =================================================================
# Section 3: Frame Resizing Function
# =================================================================
def resize_frame(frame, target_width):
    """Resizes the frame to the target width while preserving the aspect ratio."""
    if target_width > 0 and frame.shape[1] > target_width:
        ratio = target_width / float(frame.shape[1])
        new_height = int(frame.shape[0] * ratio)
        return cv2.resize(frame, (target_width, new_height))
    return frame

# =================================================================
# Section 4: Main Processing Loop
# =================================================================
def main():
    client_socket = None
    vid = None
    while True:
        try:
            # Ensure valid socket connection
            if client_socket is None or client_socket.fileno() == -1:
                if client_socket:
                    client_socket.close()
                client_socket = connect_to_server()

            # Ensure the camera is opened
            if vid is None or not vid.isOpened():
                print("[INFO] Opening the camera...")
                vid = cv2.VideoCapture(0)
                if not vid.isOpened():
                    print("[ERROR] Unable to open camera. Check connection and permissions.")
                    time.sleep(RECONNECT_DELAY)
                    continue
                print("[INFO] Camera successfully opened.")

            # Read frame from the camera
            ret, frame = vid.read()
            if not ret:
                print("[WARNING] Unable to read frame. Possible camera disconnection.")
                vid.release()
                vid = None
                time.sleep(1)
                continue

            # Resize frame if necessary
            frame = resize_frame(frame, RESIZE_WIDTH)

            # Encode frame as JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
            result, frame_encoded = cv2.imencode('.jpg', frame, encode_param)
            if not result:
                print("[ERROR] JPEG encoding failed.")
                continue

            # Send data: first the 4-byte length, then the JPEG bytes
            data = frame_encoded.tobytes()
            size = len(data)
            client_socket.sendall(struct.pack(">L", size) + data)

            # Control the frame rate (~30 FPS)
            time.sleep(0.03)

        except (socket.error, ConnectionResetError, BrokenPipeError) as e:
            print(f"[ERROR] Socket error: {e}. Reconnecting...")
            if client_socket:
                client_socket.close()
            client_socket = None
            if vid and vid.isOpened():
                vid.release()
                vid = None
            time.sleep(RECONNECT_DELAY / 2)

        except KeyboardInterrupt:
            print("[INFO] Received interrupt signal. Shutting down...")
            break

        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            if client_socket:
                client_socket.close()
            client_socket = None
            if vid and vid.isOpened():
                vid.release()
                vid = None
            time.sleep(RECONNECT_DELAY)

    # =================================================================
    # Section 5: Resource Cleanup
    # =================================================================
    print("[INFO] Cleaning up resources...")
    if vid and vid.isOpened():
        vid.release()
        print("[INFO] Camera released.")
    if client_socket:
        client_socket.close()
        print("[INFO] Socket connection closed.")
    cv2.destroyAllWindows()
    print("[INFO] Program terminated.")

if __name__ == '__main__':
    main()
