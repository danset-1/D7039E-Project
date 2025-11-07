import tkinter as tk
import time
from typing import Dict, List, Optional
import threading
import socket
import json
import pygame

HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 5000      # Port to listen on
pygame.mixer.init()
pygame.mixer.music.load("music/start.mp3")

PICO_IP = '10.42.0.225'
PO = 12345

class SwimTimerApp:
    def __init__(self, root: tk.Tk, swimmers: List[str], max_laps: int = 8):
        self.root = root
        self.root.title("Swim Timer")
        self.root.geometry("1300x650")
        self.root.config(bg="#ebe8e1")

        self.swimmers = swimmers
        self.max_laps = max_laps

        # key_map maps '1','2',.. to swimmer names
        self.key_map: Dict[str, str] = {str(i + 1): name for i, name in enumerate(swimmers)}
        self.laps: Dict[str, List[float]] = {name: [] for name in swimmers}
        self.last_lap_elapsed: Dict[str, float] = {name: 0.0 for name in swimmers}
        self.total_lap_time: Dict[str, float] = {name: 0.0 for name in swimmers}

        # Timer state
        self.start_time: Optional[float] = None  # timestamp when current run started, None when stopped
        self.elapsed_before_start: float = 0.0   # accumulated elapsed time from previous runs
        self.running: bool = False

        # --- Timer display ---
        self.timer_label = tk.Label(
            root, text="00:00.00", font=("Arial", 60, "bold"),
            fg="#0f0f0f", bg="#ebe8e1"
        )
        self.timer_label.pack(pady=20)
    

        # --- Table setup ---
        table = tk.Frame(root, bg="#ebe8e1")
        table.pack(pady=20)

        headers = ["Swimmer", "Current Lap", "Latest Lap", "Fastest Lap", "Total Time", "Lap #"]
        widths = [12, 14, 12, 14, 14, 8]
        for c, (text, w) in enumerate(zip(headers, widths)):
            tk.Label(table, text=text, font=("Arial", 18, "bold"), fg="#0f0f0f", bg="#ebe8e1", width=w).grid(row=0, column=c)

        # --- Swimmer rows ---
        self.row_widgets: Dict[str, Dict[str, tk.Widget]] = {}
        for i, name in enumerate(swimmers, start=1):
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

            row["lap_count_label"] = tk.Label(table, text="0", font=("Arial", 18), fg="#0f0f0f", bg="#ebe8e1")
            row["lap_count_label"].grid(row=i, column=5)

            
            tk.Label(table, text="", bg="#ebe8e1", width=4).grid(row=i, column=6, padx=5)

            self.row_widgets[name] = row

        # --- Bind keys ---
        self.root.bind("<KeyPress>", self.on_key_press)

    # --------------------
    # Time helpers
    # --------------------
    def _current_elapsed(self) -> float:
        """Return total elapsed seconds (including previous runs)."""
        if self.running and self.start_time is not None:
            return self.elapsed_before_start + (time.time() - self.start_time)
        return self.elapsed_before_start

    @staticmethod
    def _format_timer_display(seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        millis = int((seconds * 100) % 100)
        return f"{mins:02d}:{secs:02d}.{millis:02d}"

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        return f"{seconds:5.2f}"

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

    # Make a countdown before starting timer and play start sound 
    def countdown(self, count):
        if count > 0:
            self.timer_label.config(text=str(count))
            # schedule next countdown step after 1 second
            self.root.after(1000, self.countdown, count - 1)
        else:
            start_server(handle_message)
            pygame.mixer.music.play()
            self.start_time = time.time()
            # self.running = True
            self.update_timer()

    # Stop the timer and all lane times
    def stop(self):
        if self.running and self.start_time is not None:
            # Accumulate elapsed time and mark stopped
            self.elapsed_before_start += time.time() - self.start_time
            self.start_time = None
            self.running = False

    # Resets all variables, if called while the timer is running it stops and resets the timer
    def reset(self):
        self.running = False
        self.start_time = None
        self.elapsed_before_start = 0.0
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

    # Update the timer
    def update_timer(self):
        # Always compute current elapsed and show it in the main timer.
        # Per-lane "Total Time" will use the same value/format so they match.
        elapsed = self._current_elapsed()
        self.timer_label.config(text=self._format_timer_display(elapsed))

        # Update per-swimmer timers (both while running and when stopped)
        for name in self.swimmers:
            laps = self.laps[name]
            row = self.row_widgets[name]
            if len(laps) < self.max_laps:
                current_lap_time = elapsed - self.last_lap_elapsed[name]
                row["current_lap_label"].config(text=self._format_seconds(current_lap_time))
                # Use same format/value as the main timer so they match visually
                row["total_label"].config(text=self._format_timer_display(elapsed))
            else:
                row["current_lap_label"].config(text="DONE")
                row["total_label"].config(text=self._format_timer_display(self.total_lap_time[name]))

        # Continue updating repeatedly only when running
        # Update every 0.05s 
        if self.running:
            self.root.after(50, self.update_timer)

    # Record a lap time for a swimmer
    def record_lap(self, name: str):
        if not self.running:
            return  # ignore lap presses when timer is not running

        # ignore if swimmer already reached max laps
        if len(self.laps.get(name, [])) >= self.max_laps:
            return

        elapsed = self._current_elapsed()
        lap_time = elapsed - self.last_lap_elapsed[name]
        self.last_lap_elapsed[name] = elapsed
        self.laps[name].append(lap_time)

        self.total_lap_time[name] += lap_time


        # Update labels
        row = self.row_widgets[name]
        row["lap_count_label"].config(text=str(len(self.laps[name])))
        row["latest_lap_label"].config(text=self._format_seconds(lap_time))
        best = min(self.laps[name]) if self.laps[name] else None
        if best is not None:
            best_idx = self.laps[name].index(best) + 1  # first occurrence → lap number (1-based)
            row["best_lap_label"].config(text=f"{self._format_seconds(best)} (#{best_idx})")
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
        # time = float(lap)
        if not self.running:
            return  # ignore lap presses when timer is not running

        # ignore if swimmer already reached max laps
        if len(self.laps.get(name, [])) >= self.max_laps:
            return

        lap_time = float(lap) - self.total_lap_time[name]
        # self.last_lap_elapsed[name] = elapsed
        self.laps[name].append(lap_time)

        self.total_lap_time[name] += lap_time

        # Update labels
        row = self.row_widgets[name]
        row["lap_count_label"].config(text=str(len(self.laps[name])))
        row["latest_lap_label"].config(text=self._format_seconds(lap_time))
        best = min(self.laps[name]) if self.laps[name] else None
        if best is not None:
            best_idx = self.laps[name].index(best) + 1  # first occurrence → lap number (1-based)
            row["best_lap_label"].config(text=f"{self._format_seconds(best)} (#{best_idx})")
        else:
            row["best_lap_label"].config(text="-")

        # Stop swimmer after reaching max laps
        if len(self.laps[name]) >= self.max_laps:
            
            row["current_lap_label"].config(text="DONE")

        # If every swimmer has finished, stop main timer
        if all(len(self.laps[s]) >= self.max_laps for s in self.swimmers):
            self.stop()

# Start the timer
def start(self):
    if not self.running:
        data = {"command": "start"}
        a = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        a.connect((PICO_IP, PO))
        a.sendall(json.dumps(data).encode('utf-8'))
        a.close()
        app.running = True
        SwimTimerApp.countdown(app, 5)

def start_server(callback):
    def server_thread():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen()
            print(f"Listening on port {PORT}...")
            while True:
                conn, addr = s.accept()
                print(f"Connected by {addr}")
                threading.Thread(target=handle_client, args=(conn, callback), daemon=True).start()

    threading.Thread(target=server_thread, daemon=True).start()

# Handle signals that comes in, can handle rust and python
def handle_client(conn, callback):
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
                    callback(msg)
                except json.JSONDecodeError:
                    # Wait for more data
                    break

    print("Client disconnected.")

# Take the data from the signal and call action based on the data
def handle_message(msg):
    print("Received:", msg)
    # label.config(text=f"Message: {msg}")
    id = msg.get("id")
    m = msg.get("message")
    time = msg.get("lap_time")
    swimmer = app.key_map[id]
    if m == "start":
        SwimTimerApp.start(app)
    elif m == "stop":
        SwimTimerApp.stop(app)
    elif m == "split":
        SwimTimerApp.record_lap(app, swimmer)
    elif m == "lap":
        SwimTimerApp.set_lap(app, time,  swimmer)


if __name__ == "__main__":
    swimmers = [f"Lane {i}" for i in range(1, 5)] # change to ID swimmers
    root = tk.Tk()
    app = SwimTimerApp(root, swimmers, max_laps=8)

    # start_server(handle_message)
    root.mainloop()