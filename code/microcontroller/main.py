from machine import Pin
import time
import sys
import network
import socket
import json
import _thread


switch = Pin(15, Pin.IN, Pin.PULL_UP)
stopwatch_Active = False
curTime = 0
led = machine.Pin("LED", machine.Pin.OUT)
led.on()
#Connect to wifi
SSID = "swim"
PASSWORD = "12345678"

wlan = network.WLAN(network.STA_IF)
wlan.disconnect()
wlan.active(True)
wlan.config(pm=0xa11140)
wlan.connect(SSID, PASSWORD)

print("Connecting to wifi...")
while not wlan.isconnected():
    time.sleep(0.5)
print("Connected:", wlan.ifconfig())

class Stopwatch:
    def __init__(self, start_minutes, start_seconds):
        self.start_time = time.ticks_ms()
        self.time_offset = (start_minutes * 60 + start_seconds) * 1000
    
    def get_current_time(self):
        current_time = time.ticks_ms()
        elapsed_ms = time.ticks_diff(current_time, self.start_time) + self.time_offset
        return elapsed_ms / 1000.0
    
    def format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds_remaining = seconds % 60
        return f"{minutes:02d}:{seconds_remaining:06.3f}"

def start_program(laps):
    global stopwatch_Active
    global curTime
    count = 0
    stopwatch_Active = True
    # Start Time
    start_time_minutes = 0
    start_time_seconds = 0
    
    stopwatch = Stopwatch(start_minutes=start_time_minutes, start_seconds=start_time_seconds)
    previous_state = switch.value()
    activated = False
    
    # Add cooldown
    last_press_time = 0
    delay = 0
    program_starttime = time.ticks_ms()
    initial_delay = 0
    
    # Initial time is set to the given time
    initial_time = start_time_minutes * 60 + start_time_seconds
    print(f"Start Time: {stopwatch.format_time(initial_time)}")
    print("------------------------------------------")
    
    try:
        while int(laps) > count and stopwatch_Active == True:
            # Update timer display
            current = stopwatch.format_time(stopwatch.get_current_time())
            curTime = current
            print(f"\rStopwatch: {current}", end='')
            
            # Check switch state
            current_state = switch.value()
            current_time_seconds = stopwatch.get_current_time()
            
            # Calculates time since start
            start_time = time.ticks_diff(time.ticks_ms(), program_starttime) / 1000.0
            
            # Check if switch is pressed
            if previous_state == 1 and current_state == 0:
                if not activated:
                    # Check for initial delay
                    if start_time >= initial_delay:
                        # Check for normal delay
                        last_press = current_time_seconds - last_press_time
                        #If it's a valid press send signal to Raspberry Pi with timestamp
                        if last_press >= delay:
                            print(f"\nTimestamp: {stopwatch.format_time(current_time_seconds)}")
                            last_press_time = current_time_seconds
                            activated = True

                            count+=1

                            HOST2 = "10.42.0.1"     #Raspberry Pi IP
                            PORT2 = 5000

                            data = {"id": "2", "command": "lap", "lap_time": current_time_seconds}
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.connect((HOST2, PORT2))
                            s.sendall(json.dumps(data).encode("utf-8"))
                            s.close()
                            print("Sent:", data)
            
            # If switch is released
            elif previous_state == 0 and current_state == 1:
                activated = False  
            
            # Update state
            previous_state = current_state
            
            time.sleep_ms(5)
            
    except KeyboardInterrupt:
        stopwatch_Active = False
        print("\nStopped")
    finally:
        stopwatch_Active = False
        # curTime = current
        # print("\nSwimmer finished. Listening for next command:")        


# Listen for signal from Raspberry Pi to start timer
def main():
    HOST = '0.0.0.0'
    PORT = 6000

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(1)
    print("Listening on port:", PORT)

    global stopwatch_Active
    global curTime
    try:
        while True:
            s.settimeout(1)
            try:
                conn, addr = s.accept()
            except OSError:
                # no incoming connection, just continue
                continue
            print("\nConnected by", addr)
            try:
                data = conn.recv(1024)
                if not data:
                    conn.close()
                    continue
                msg = data.decode("utf-8")
                print("\nRecieved:", msg)

                try:
                    command = json.loads(msg)
                    laps = command.get("laps")
                    if command.get("command") == "start":
                        if stopwatch_Active == False:
                            _thread.start_new_thread(start_program, (laps,))
                        else:
                            print("ignoring command")
                    
                    elif command.get("command") == "reset":
                        stopwatch_Active = False
                        print("Timer reset")
                        print("\nListening on port:", PORT)
                        
                    elif command.get("command") == "stop":
                        stopwatch_Active = False
                        print("Timer stopped")
                        print("Listening on port:", PORT)
                        print("\n",curTime)
                    else:
                        print("Unknown command:", command)
                except Exception as e:
                    print("JSON Error:", e)
                conn.close()
            except Exception as e:
                print("Error:", e)
    except KeyboardInterrupt:
        stopwatch_Active = False
        print("\nStopped")


main()
        
