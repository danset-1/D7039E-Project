import threading
import socket
import json
from Screen import app as tk

HOST = '0.0.0.0'
PORT = 5000

PICO_IP = '10.42.0.225'
PO = 6000
pico_addr = {
    ("10.42.0.39", 6000),
    ("10.42.0.225", 6000)
}
send = threading.Event()

def sendData(addr, data):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(addr)

        # send.wait()

        s.sendall(json.dumps(data).encode('utf-8'))
        s.close()
    except Exception as e:
        print("Error: ",e)

def start_server(callback, app):
    def server_thread():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen()
            print(f"Listening on port {PORT}...")
            while True:
                conn, addr = s.accept()
                print(f"Connected by {addr}")
                threading.Thread(target=receiveData, args=(conn, callback, app), daemon=True).start()

    threading.Thread(target=server_thread, daemon=True).start()

# Handle signals that comes in, can handle rust and python
def receiveData(conn, callback, app):
    with conn:
        buffer = b""
        while True:
            chunk = conn.recv(1024)
            if not chunk:
                break
            buffer += chunk

            while True:
                if len(buffer) == 0:
                    break

                # --- Case 1: Length-prefixed (Rust) ---
                if len(buffer) >= 4:
                    length = int.from_bytes(buffer[:4], "big")

                    if 1 <= length <= 10_000 and len(buffer) >= 4 + length:
                        json_bytes = buffer[4:4 + length]
                        buffer = buffer[4 + length:]
                        try:
                            msg = json.loads(json_bytes.decode("utf-8"))
                            callback(msg)
                        except json.JSONDecodeError:
                            print("Invalid JSON (Rust format)")
                        continue

                # --- Case 2: Plain JSON (Python) ---
                try:
                    msg = json.loads(buffer.decode("utf-8"))
                    buffer = b""  # fully consumed
                    callback(msg, app)
                except json.JSONDecodeError:
                    # Wait for more data
                    break

    print("Client disconnected.")

# Take the data from the signal and call action based on the data
def handle_message(msg, app):
    print("Received:", msg)
    # label.config(text=f"Message: {msg}")
    id = msg.get("id")
    cmd = msg.get("command")
    time = msg.get("lap_time")
    swimmer = app.key_map[id]
    if cmd == "start":
        tk.SwimTimerApp.start(app)
    elif cmd == "stop":
        tk.SwimTimerApp.stop(app)
    elif cmd == "split":
        tk.SwimTimerApp.record_lap(app, swimmer)
    elif cmd == "lap":
        tk.SwimTimerApp.set_lap(app, time,  swimmer)
