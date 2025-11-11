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
    start_time_minutes = 0
    start_time_seconds = 15
    
    stopwatch = Stopwatch(start_minutes=start_time_minutes, start_seconds=start_time_seconds)
    previous_state = switch.value()
    activated = False
    
    # Add cooldown
    last_press_time = 0
    delay = 5  
    program_starttime = time.ticks_ms()
    initial_delay = 5  
    
    # Initial time is set to the given time
    initial_time = start_time_minutes * 60 + start_time_seconds
    print(f"Start Time: {stopwatch.format_time(initial_time)}")
    print("------------------------------------------")
    
    try:
        while True:
            # Update timer display
            current = stopwatch.format_time(stopwatch.get_current_time())
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
                        if last_press >= delay:
                            print(f"\nTimestamp: {stopwatch.format_time(current_time_seconds)}")
                            last_press_time = current_time_seconds
                            activated = True
                        else:
                            remaining_cooldown = delay - last_press
                    else:
                        remaining_delay = initial_delay - start_time
            
            # If switch is released
            elif previous_state == 0 and current_state == 1:
                activated = False  
            
            # Update state
            previous_state = current_state
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\nStopped")

main()