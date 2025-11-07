# main.py
import network
import socket
import json
import time
from machine import Pin

switch = Pin(15, Pin.IN, Pin.PULL_UP)

#Connect to wifi
SSID = "swim"
PASSWORD = "12345678"

wlan = network.WLAN(network.STA_IF)
wlan.disconnect()
wlan.active(True)
wlan.connect(SSID, PASSWORD)

print("Connecting to wifi...")
while not wlan.isconnected():
    time.sleep(0.5)
print("Connected:", wlan.ifconfig())

def start_program(laps):
    count = 0

    HOST = "10.42.0.1"  # Replace with your computer's local IP
    PORT = 5000
    while True:
        if switch.value() == 0 and laps > count:
                count += 1
                data = {"id": "2", "message": "lap", "lap_time": "59.2"}
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((HOST, PORT))
                s.sendall(json.dumps(data).encode("utf-8"))
                s.close()
                print("Sent:", data)

# Listen for start signal
HOST = "0.0.0.0"
PORT = 6555

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(1)
print("Listening on port:", PORT)

while True:
    conn, addr = s.accept()
    print("Anslutning från", addr)
    try:
        data = conn.recv(1024)
        if not data:
            conn.close()
            continue
        msg = data.decode("utf-8")
        print("Recieved:", msg)

        try:
            command = json.loads(msg)
            laps = command.get("laps")
            #print("JSON:", command)
            if command.get("command") == "start":
                start_program(laps)
            elif command.get("command") == "stop":
                stop_program()
            else:
                print("Unknown command:", command)
        except Exception as e:
            print("JSON Error:", e)

        conn.send(b"ACK")
    except Exception as e:
        print("Fel:", e)
    finally:
        conn.close()
