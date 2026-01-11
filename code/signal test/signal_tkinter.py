import socket
import json

HOST = '127.0.0.1'  # Replace with IP of computer running the Tkinter app
PORT = 5000
data = {"id": "2", "message": "lap", "lap_time": "59.2"}

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    #s.sendall(b'Hello from another computer!') 
    s.sendall(json.dumps(data).encode('utf-8'))