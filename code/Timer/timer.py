import time
from typing import Dict, List, Optional
from Screen import app
start_time: Optional[float] = None  # timestamp when current run started, None when stopped
elapsed_before_start: float = 0.0   # accumulated elapsed time from previous runs

# --------------------
# Time helpers
# --------------------

# Returns the total time that has passed
def _current_elapsed(self) -> float:
    if self.running and start_time is not None:
        return elapsed_before_start + (time.time() - start_time)
    return elapsed_before_start

# Takes number of seconds and then returns it formatted into minutes,seconds and milliseconds
@staticmethod
def _format_timer_display(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    millis = int((seconds * 100) % 100)
    return f"{mins:02d}:{secs:02d}.{millis:02d}"

# Returns seconds formatted into a maximum amount of decimals
@staticmethod
def _format_seconds(seconds: float) -> str:
    return f"{seconds:5.2f}"