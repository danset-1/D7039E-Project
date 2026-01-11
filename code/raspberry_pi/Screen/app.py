import tkinter as tk
import time
from typing import Dict, List, Optional
import threading
import socket
import json
import pygame

from Connection import MicrocontrollerConnection as mConn
from Timer import timer

# ---------- Config ----------
# Stores how many swimming lanes there are and how many laps the swimmers are going to do
CONFIG_PATH = "screen/config.json"

# Opens the config.json file and reads the stored values and sets the app to use those values
def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"swimmers": 4, "laps": 8}

# If the values for swimming lanes and or number of laps are changed save the new values to the config.json file
def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f)

# ---------- Networking & Audio ----------
HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 5000      # Port to listen on

PICO_IP = '10.42.0.225'
PO = 6000
pico_addr = {
    ("10.42.0.39", 6000),
    ("10.42.0.225", 6000)
}

# Initialize being able to play a sound and load the sound file
pygame.mixer.init()
pygame.mixer.music.load("music/start.mp3")      # Load gun sound

class SwimTimerApp:
    def __init__(self, root: tk.Tk, swimmers: List[str], max_laps: int):
        self.root = root
        self.root.title("Swim Timer")
        self.root.geometry("1300x650")
        self.root.config(bg="#ebe8e1")

        # Escape button to exit fullscreen
        self.root.bind("<Escape>", lambda event: self.root.attributes("-fullscreen", False))

        # Core data
        self.swimmers = swimmers[:]  # list of swimmer names (Lane 1..N)
        self.max_laps = max_laps
        print(self.max_laps)

        # per-swimmer runtime data
        self.key_map: Dict[str, str] = {}  # maps "1","2"... -> swimmer name
        self.laps: Dict[str, List[float]] = {}
        self.last_lap_elapsed: Dict[str, float] = {}
        self.total_lap_time: Dict[str, float] = {}

        # Timer state
        self.start_time: Optional[float] = None
        self.elapsed_before_start: float = 0.0
        self.running: bool = False

        # Top timer label
        self.timer_label = tk.Label(
            root, text="00:00.00", font=("Arial", 60, "bold"),
            fg="#0f0f0f", bg="#ebe8e1"
        )
        self.timer_label.pack(pady=20)

        # Buttons frame (start/stop/reset/settings)
        btn_frame = tk.Frame(root, bg="#ebe8e1")
        btn_frame.pack(pady=5)

        start_btn = tk.Button(btn_frame, text="Start (S)", font=("Arial", 14), command=self.start)
        start_btn.grid(row=0, column=0, padx=8)

        stop_btn = tk.Button(btn_frame, text="Stop (D)", font=("Arial", 14), command=self.stop)
        stop_btn.grid(row=0, column=1, padx=8)

        reset_btn = tk.Button(btn_frame, text="Reset (R)", font=("Arial", 14), command=self.reset)
        reset_btn.grid(row=0, column=2, padx=8)

        settings_btn = tk.Button(btn_frame, text="Settings", font=("Arial", 14), command=self.open_settings_window)
        settings_btn.grid(row=0, column=3, padx=8)

        # Table/frame for swimmers - created via helper so it can be rebuilt.
        self.table_frame: Optional[tk.Frame] = None
        self.row_widgets: Dict[str, Dict[str, tk.Widget]] = {}

        # Build initial runtime containers & table
        self._init_swimmer_data_structures()
        self._create_table()

        # Key bindings
        self.root.bind("<KeyPress>", self.on_key_press)

    def _init_swimmer_data_structures(self):
        """Ensure data structures exist for current self.swimmers."""
        for name in self.swimmers:
            self.laps.setdefault(name, [])
            self.last_lap_elapsed.setdefault(name, 0.0)
            self.total_lap_time.setdefault(name, 0.0)
        # Remove any swimmers that are no longer present
        for name in list(self.laps.keys()):
            if name not in self.swimmers:
                del self.laps[name]
                del self.last_lap_elapsed[name]
                del self.total_lap_time[name]

        # key_map maps numeric keys (1..N) to swimmer names
        self.key_map = {str(i + 1): name for i, name in enumerate(self.swimmers)}

    # -----------------------
    # UI: (re)build table
    # -----------------------
    def _create_table(self):
        # Destroy existing table frame if present
        if self.table_frame is not None:
            self.table_frame.destroy()
            self.row_widgets = {}

        table = tk.Frame(self.root, bg="#ebe8e1")
        table.pack(pady=20)
        self.table_frame = table

        headers = ["Swimmer", "Current Lap", "Latest Lap", "Fastest Lap", "Total Time", "Lap #"]
        widths = [12, 14, 12, 14, 14, 8]
        for c, (text, w) in enumerate(zip(headers, widths)):
            tk.Label(table, text=text, font=("Arial", 18, "bold"), fg="#0f0f0f", bg="#ebe8e1", width=w).grid(row=0, column=c)

        for i, name in enumerate(self.swimmers, start=1):
            row: Dict[str, tk.Widget] = {}

            row["name_label"] = tk.Label(table, text=name, font=("Arial", 18), fg="#0f0f0f", bg="#ebe8e1")
            row["name_label"].grid(row=i, column=0, padx=10, pady=8)

            row["current_lap_label"] = tk.Label(table, text="0.00", font=("Courier", 18), fg="#0f0f0f", bg="#ebe8e1")
            row["current_lap_label"].grid(row=i, column=1)

            row["latest_lap_label"] = tk.Label(table, text="-", font=("Courier", 18), fg="#0f0f0f", bg="#ebe8e1")
            row["latest_lap_label"].grid(row=i, column=2)

            row["best_lap_label"] = tk.Label(table, text="-", font=("Courier", 18), fg="#0f0f0f", bg="#ebe8e1")
            row["best_lap_label"].grid(row=i, column=3)

            row["total_label"] = tk.Label(table, text="0.00", font=("Courier", 18), fg="#0f0f0f", bg="#ebe8e1")
            row["total_label"].grid(row=i, column=4)

            row["lap_count_label"] = tk.Label(table, text=str(len(self.laps.get(name, []))), font=("Arial", 18), fg="#0f0f0f", bg="#ebe8e1")
            row["lap_count_label"].grid(row=i, column=5)

            tk.Label(table, text="", bg="#ebe8e1", width=4).grid(row=i, column=6, padx=5)

            self.row_widgets[name] = row

    # -----------------------
    # Settings window
    # -----------------------
    def open_settings_window(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("320x260")
        win.config(bg="#ebe8e1")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="Number of swimmers:", bg="#ebe8e1", font=("Arial", 14)).pack(pady=(12,6))
        swimmer_entry = tk.Entry(win, font=("Arial", 14), justify="center")
        swimmer_entry.insert(0, str(len(self.swimmers)))
        swimmer_entry.pack(pady=4)

        tk.Label(win, text="Number of laps:", bg="#ebe8e1", font=("Arial", 14)).pack(pady=(12,6))
        laps_entry = tk.Entry(win, font=("Arial", 14), justify="center")
        laps_entry.insert(0, str(self.max_laps))
        laps_entry.pack(pady=4)

        hint = tk.Label(win, text="(Min 1, Max 10 swimmers)", bg="#ebe8e1", font=("Arial", 10))
        hint.pack(pady=(6,0))

        def apply_settings():
            try:
                new_swimmers = int(swimmer_entry.get())
                new_laps = int(laps_entry.get())
                if new_swimmers < 1 or new_swimmers > 10:
                    return
                if new_laps < 1:
                    return

                # Save config persistently
                save_config({"swimmers": new_swimmers, "laps": new_laps})

                # Apply new settings live (preserve as much state as reasonably possible)
                self.apply_new_settings(new_swimmers, new_laps)

                win.destroy()
            except ValueError:
                # ignore invalid input
                return

        tk.Button(win, text="Apply", font=("Arial", 14), command=apply_settings).pack(pady=16)

    def apply_new_settings(self, num_swimmers: int, num_laps: int):
        """
        Apply new settings live: rebuild swimmer list and UI.
        We'll stop the timer and reset per-swimmer lap state for a clean start.
        """
        # Stop timer and reset time keeping
        self.running = False
        self.start_time = None
        self.elapsed_before_start = 0.0

        # Build new swimmer names
        new_swimmers = [f"Lane {i}" for i in range(1, num_swimmers + 1)]
        self.swimmers = new_swimmers
        self.max_laps = num_laps

        # Reinitialize data structures for each swimmer (fresh)
        self.laps = {name: [] for name in self.swimmers}
        self.last_lap_elapsed = {name: 0.0 for name in self.swimmers}
        self.total_lap_time = {name: 0.0 for name in self.swimmers}
        self._init_swimmer_data_structures()

        # Recreate table UI
        self._create_table()

        # Reset main timer label
        self.timer_label.config(text="00:00.00")

    # --------------------
    # Event handlers
    # --------------------
    def on_key_press(self, event):
        key = (event.char or "").lower()

        # Control keys
        if key == "s":          # start / resume
            self.start()
            return
        if key == "d":          # stop / pause
            self.stop()
            return
        if key == "r":          # reset
            self.reset()
            return

        # Lap keys (digits) — only while running
        if key in self.key_map and self.running:
            swimmer = self.key_map[key]
            if len(self.laps.get(swimmer, [])) < self.max_laps:
                self.record_lap(swimmer)

    # Start the timer
    def start(self):
        if not self.running:
            data = {"command": "start", "laps": self.max_laps}
            try:
                for addr in pico_addr:
                    threading.Thread(target=mConn.sendData, args=(addr, data)).start()
            except Exception as e:
                print("Error: ",e)

            self.running = True
            SwimTimerApp.countdown(self, 5)

    # Make a countdown before starting timer and play start sound 
    def countdown(self, count):
        if count > 0:
            self.timer_label.config(text=str(count))
            # schedule next countdown step after 1 second
            self.root.after(1000, self.countdown, count - 1)
        else:
            pygame.mixer.music.play()
            timer.start_time = time.time()
            # self.running = True
            self.update_timer()

    # Stop the timer and all lane times
    def stop(self):
        if self.running and timer.start_time is not None:
            # Accumulate elapsed time and mark stopped
            timer.elapsed_before_start += time.time() - timer.start_time
            timer.start_time = None
            self.running = False

        data = {"command": "stop"}
        try:
            for addr in pico_addr:
                threading.Thread(target=mConn.sendData, args=(addr, data)).start()
        except Exception as e:
            print("Error: ",e)


    # Resets all variables, if called while the timer is running it stops and resets the timer
    def reset(self):
        self.running = False
        timer.start_time = None
        timer.elapsed_before_start = 0.0
        self.timer_label.config(text="00:00.00")
        for name in self.swimmers:
            self.laps[name] = []
            self.last_lap_elapsed[name] = 0.0
            self.total_lap_time[name] = 0.0
            row = self.row_widgets[name]
            row["current_lap_label"].config(text="0.00")
            row["best_lap_label"].config(text="-")
            row["latest_lap_label"].config(text="-")
            row["total_label"].config(text="0.00")
            row["lap_count_label"].config(text="0")

        # Call function to send a signal
        data = {"command": "reset"}     # Data to send with the signal
        try:
            for addr in pico_addr:
                threading.Thread(target=mConn.sendData, args=(addr, data)).start()
        except Exception as e:
            print("Error: ",e)


    # Update the timer
    def update_timer(self):
        # Always compute current elapsed and show it in the main timer.
        # Per-lane "Total Time" will use the same value/format so they match.
        elapsed = timer._current_elapsed(self)
        self.timer_label.config(text=timer._format_timer_display(elapsed))

        # Update per-swimmer timers (both while running and when stopped)
        for name in self.swimmers:
            laps = self.laps[name]
            row = self.row_widgets[name]
            if len(laps) < self.max_laps:
                current_lap_time = elapsed - self.last_lap_elapsed[name]
                row["current_lap_label"].config(text=timer._format_seconds(current_lap_time))
                # Use same format/value as the main timer so they match visually
                row["total_label"].config(text=timer._format_timer_display(elapsed))
            else:
                row["current_lap_label"].config(text="DONE")
                row["total_label"].config(text=timer._format_timer_display(self.total_lap_time[name]))

        # Continue updating repeatedly only when running
        # Update every 0.05s 
        if self.running:
            self.root.after(50, self.update_timer)

    # Record a lap time for a swimmer, is used when timesplit is called from keyboard input
    def record_lap(self, name: str):
        if not self.running:
            return  # ignore lap presses when timer is not running

        # ignore if swimmer already reached max laps
        if len(self.laps.get(name, [])) >= self.max_laps:
            return

        elapsed = timer._current_elapsed(self)
        lap_time = elapsed - self.last_lap_elapsed[name]
        self.last_lap_elapsed[name] = elapsed
        self.laps[name].append(lap_time)

        self.total_lap_time[name] += lap_time


        # Update labels
        row = self.row_widgets[name]
        row["lap_count_label"].config(text=str(len(self.laps[name])))
        row["latest_lap_label"].config(text=timer._format_seconds(lap_time))
        best = min(self.laps[name]) if self.laps[name] else None
        if best is not None:
            best_idx = self.laps[name].index(best) + 1  # first occurrence → lap number (1-based)
            row["best_lap_label"].config(text=f"{timer._format_seconds(best)} (#{best_idx})")
        else:
            row["best_lap_label"].config(text="-")

        # Stop swimmer after reaching max laps
        if len(self.laps[name]) >= self.max_laps:
            
            row["current_lap_label"].config(text="DONE")

        # If every swimmer has finished, stop main timer
        if all(len(self.laps[s]) >= self.max_laps for s in self.swimmers):
            self.stop()
    
    # Record a lap from an external time input
    def set_lap(self, lap: str,  name: str):
        if not self.running:
            return  # ignore lap presses when timer is not running

        # ignore if swimmer already reached max laps
        if len(self.laps.get(name, [])) >= self.max_laps:
            return
        elapsed = float(lap)
        lap_time = float(lap) - self.total_lap_time[name]
        self.last_lap_elapsed[name] = elapsed
        self.laps[name].append(lap_time)

        self.total_lap_time[name] += lap_time

        # Update labels
        row = self.row_widgets[name]
        row["lap_count_label"].config(text=str(len(self.laps[name])))
        row["latest_lap_label"].config(text=timer._format_seconds(lap_time))
        best = min(self.laps[name]) if self.laps[name] else None
        if best is not None:
            best_idx = self.laps[name].index(best) + 1  # first occurrence → lap number (1-based)
            row["best_lap_label"].config(text=f"{timer._format_seconds(best)} (#{best_idx})")
        else:
            row["best_lap_label"].config(text="-")

        # Stop swimmer after reaching max laps
        if len(self.laps[name]) >= self.max_laps:
            
            row["current_lap_label"].config(text="DONE")

        # If every swimmer has finished, stop main timer
        if all(len(self.laps[s]) >= self.max_laps for s in self.swimmers):
            self.stop()




# if __name__ == "__main__":
#     swimmers = [f"Lane {i}" for i in range(1, 5)] # change to ID swimmers
#     root = tk.Tk()
#     app = SwimTimerApp(root, swimmers, max_laps=8)

#     mConn.start_server(mConn.handle_message, app)
#     root.mainloop()