from machine import Pin
import time
import sys

switch = Pin(15, Pin.IN, Pin.PULL_UP)

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

def main():
    # Start Time
    starttime_minutes = 0
    starttime_seconds = 15
    
    stopwatch = Stopwatch(start_minutes=starttime_minutes, start_seconds=starttime_seconds)
    previous_state = switch.value()
    activated = False
    
    # Initial time is set to the given time
    initial_time = starttime_minutes * 60 + starttime_seconds
    print(f"Start Time: {stopwatch.format_time(initial_time)}")
    print("------------------------------------------")
    
    try:
        while True:
            # Update timer display
            current = stopwatch.format_time(stopwatch.get_current_time())
            print(f"\rStopwatch: {current}", end='')
            
            # Check switch state
            current_state = switch.value()
            
            # Check if switch is pressed
            if previous_state == 1 and current_state == 0:
                if not activated:
                    current_time = stopwatch.get_current_time()
                    print(f"\nTimestamp: {stopwatch.format_time(current_time)}")
                    activated = True
            
            # If switch is released
            elif previous_state == 0 and current_state == 1:
                activated = False  
            
            # Update state
            previous_state = current_state
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\nStopped")

main()
