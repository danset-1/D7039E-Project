from machine import Pin
import time
import sys

switch = Pin(15, Pin.IN, Pin.PULL_UP)

class Stopwatch:
    def __init__(self):
        self.start_time = time.ticks_ms()
        self.running = True
    
    def get_current_time(self):
        current_time = time.ticks_ms()
        elapsed_ms = time.ticks_diff(current_time, self.start_time)
        return elapsed_ms / 1000.0
    
    def format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds_remaining = seconds % 60
        return f"{minutes:02d}:{seconds_remaining:06.3f}"

def main():
    stopwatch = Stopwatch()
    previous_state = switch.value()
    
    activated = False
    
    print("Timer start")
    print("------------------------------------------")
    
    try:
        while stopwatch.running:
            # Update timer display
            current = stopwatch.format_time(stopwatch.get_current_time())
            print(f"\rRunning: {current}", end='')
            
            # Check switch state
            current_state = switch.value()
            
            # Check if switch is pressed
            if previous_state == 1 and current_state == 0:
                if not activated:
                    current_time = stopwatch.get_current_time()
                    print(f"\nTime recorded: {stopwatch.format_time(current_time)}")
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