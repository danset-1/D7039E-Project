# swim_timer_with_settings.py
# Single-file Swim Timer with a Settings window (live UI rebuild) and persistent config.

import tkinter as tk
import time
from typing import Dict, List, Optional
import threading
import socket
import json
import pygame
import sys
import os

# ---------- Config ----------
CONFIG_PATH = "config.json"

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"swimmers": 4, "laps": 8}

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f)

# ---------- Networking & Audio ----------
HOST = '0.0.0.0'
PORT = 5000

# Try to init pygame only if available
try:
    pygame.mixer.init()
    pygame.mixer.music.load("music/start.mp3")
    PYGAME_OK = True
except Exception as e:
    print("Warning: pygame audio not available:", e)
    PYGAME_OK = False

# Example pico addresses (unchanged from your original)
pico_addr = {
    ("10.42.0.39", 6000),
    ("10.42.0.225", 6000)
}

send = threading.Event()

def send_signal(addr, data):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(addr)
        # Wait until send event is set (keeps behavior similar to original)
        send.wait(timeout=1.0)
        s.sendall(json.dumps(data).encode('utf-8'))
        s.close()
    except Exception as e:
        print("Error sending to", addr, ":", e)

# ---------- SwimTimerApp ----------
class SwimTimerApp:
    def __init__(self, root: tk.Tk, swimmers: List[str], max_laps: int = 8):
        self.root = root
        self.root.title("Swim Timer")
        self.root.geometry("1300x650")
        self.root.config(bg="#ebe8e1")

        # Escape button to exit fullscreen
        self.root.bind("<Escape>", lambda event: self.root.attributes("-fullscreen", False))

        # Core data
        self.swimmers = swimmers[:]  # list of swimmer names (Lane 1..N)
        self.max_laps = max_laps

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

    # -----------------------
    # Internal helpers
    # -----------------------
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

    def _format_timer_display(self, seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        millis = int((seconds * 100) % 100)
        return f"{mins:02d}:{secs:02d}.{millis:02d}"

    def _format_seconds(self, seconds: float) -> str:
        return f"{seconds:5.2f}"

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

    # -----------------------
    # Timer logic
    # -----------------------
    def _current_elapsed(self) -> float:
        if self.running and self.start_time is not None:
            return self.elapsed_before_start + (time.time() - self.start_time)
        return self.elapsed_before_start

    def start(self):
        if not self.running:
            # send start command to connected devices with correct lap count
            data = {"command": "start", "laps": str(self.max_laps)}
            for addr in pico_addr:
                threading.Thread(target=send_signal, args=(addr, data), daemon=True).start()

            # signal sending thread to proceed once connection established
            send.set()

            self.running = True
            # do a short countdown (5s)
            self.countdown(5)

    def countdown(self, count):
        if count > 0:
            self.timer_label.config(text=str(count))
            self.root.after(1000, self.countdown, count - 1)
        else:
            if PYGAME_OK:
                try:
                    pygame.mixer.music.play()
                except Exception:
                    pass
            self.start_time = time.time()
            self.update_timer()

    def stop(self):
        if self.running and self.start_time is not None:
            self.elapsed_before_start += time.time() - self.start_time
            self.start_time = None
            self.running = False

        data = {"command": "stop"}
        for addr in pico_addr:
            threading.Thread(target=send_signal, args=(addr, data), daemon=True).start()

        send.set()

    def reset(self):
        self.running = False
        self.start_time = None
        self.elapsed_before_start = 0.0
        self.timer_label.config(text="00:00.00")

        # reset swimmers' lap data & UI
        for name in self.swimmers:
            self.laps[name] = []
            self.last_lap_elapsed[name] = 0.0
            self.total_lap_time[name] = 0.0
            row = self.row_widgets.get(name)
            if row:
                row["current_lap_label"].config(text="0.00")
                row["best_lap_label"].config(text="-")
                row["latest_lap_label"].config(text="-")
                row["total_label"].config(text="0.00")
                row["lap_count_label"].config(text="0")

        data = {"command": "reset"}
        for addr in pico_addr:
            threading.Thread(target=send_signal, args=(addr, data), daemon=True).start()

        send.set()

    def update_timer(self):
        elapsed = self._current_elapsed()
        self.timer_label.config(text=self._format_timer_display(elapsed))

        for name in self.swimmers:
            laps = self.laps.get(name, [])
            row = self.row_widgets.get(name)
            if not row:
                continue

            if len(laps) < self.max_laps:
                current_lap_time = elapsed - self.last_lap_elapsed.get(name, 0.0)
                row["current_lap_label"].config(text=self._format_seconds(current_lap_time))
                row["total_label"].config(text=self._format_timer_display(elapsed))
            else:
                row["current_lap_label"].config(text="DONE")
                row["total_label"].config(text=self._format_timer_display(self.total_lap_time.get(name, 0.0)))

        if self.running:
            self.root.after(50, self.update_timer)

    # -----------------------
    # Lap recording
    # -----------------------
    def record_lap(self, name: str):
        if not self.running:
            return
        if len(self.laps.get(name, [])) >= self.max_laps:
            return

        elapsed = self._current_elapsed()
        lap_time = elapsed - self.last_lap_elapsed.get(name, 0.0)
        self.last_lap_elapsed[name] = elapsed
        self.laps[name].append(lap_time)
        self.total_lap_time[name] = self.total_lap_time.get(name, 0.0) + lap_time

        row = self.row_widgets.get(name)
        if row:
            row["lap_count_label"].config(text=str(len(self.laps[name])))
            row["latest_lap_label"].config(text=self._format_seconds(lap_time))
            best = min(self.laps[name]) if self.laps[name] else None
            if best is not None:
                best_idx = self.laps[name].index(best) + 1
                row["best_lap_label"].config(text=f"{self._format_seconds(best)} (#{best_idx})")

            if len(self.laps[name]) >= self.max_laps:
                row["current_lap_label"].config(text="DONE")

        # if all finished -> stop main timer
        if all(len(self.laps[s]) >= self.max_laps for s in self.swimmers):
            self.stop()

    def set_lap(self, lap: str, name: str):
        """
        External lap set (from network): lap is elapsed time (float or string)
        Behavior kept similar to original code.
        """
        if not self.running:
            return
        if len(self.laps.get(name, [])) >= self.max_laps:
            return

        elapsed = float(lap)
        lap_time = elapsed - self.total_lap_time.get(name, 0.0)
        self.last_lap_elapsed[name] = elapsed
        self.laps[name].append(lap_time)
        self.total_lap_time[name] = self.total_lap_time.get(name, 0.0) + lap_time

        row = self.row_widgets.get(name)
        if row:
            row["lap_count_label"].config(text=str(len(self.laps[name])))
            row["latest_lap_label"].config(text=self._format_seconds(lap_time))
            best = min(self.laps[name]) if self.laps[name] else None
            if best is not None:
                best_idx = self.laps[name].index(best) + 1
                row["best_lap_label"].config(text=f"{self._format_seconds(best)} (#{best_idx})")

            if len(self.laps[name]) >= self.max_laps:
                row["current_lap_label"].config(text="DONE")

        if all(len(self.laps[s]) >= self.max_laps for s in self.swimmers):
            self.stop()

    # -----------------------
    # Key handler
    # -----------------------
    def on_key_press(self, event):
        key = (event.char or "").lower()

        if key == "s":
            self.start()
            return
        if key == "d":
            self.stop()
            return
        if key == "r":
            self.reset()
            return

        if key in self.key_map and self.running:
            swimmer = self.key_map[key]
            if len(self.laps.get(swimmer, [])) < self.max_laps:
                self.record_lap(swimmer)

# ---------- Networking server ----------
def start_server(callback):
    def server_thread():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, PORT))
            s.listen()
            print(f"Listening on port {PORT}...")
            while True:
                try:
                    conn, addr = s.accept()
                    print(f"Connected by {addr}")
                    threading.Thread(target=handle_client, args=(conn, callback), daemon=True).start()
                except Exception as e:
                    print("Server accept error:", e)
                    time.sleep(0.5)

    threading.Thread(target=server_thread, daemon=True).start()

def handle_client(conn, callback):
    with conn:
        buffer = b""
        while True:
            try:
                chunk = conn.recv(1024)
            except Exception:
                break
            if not chunk:
                break
            buffer += chunk

            while True:
                if len(buffer) == 0:
                    break

                # Case 1: Length-prefixed (Rust)
                if len(buffer) >= 4:
                    length = int.from_bytes(buffer[:4], "big")
                    if 1 <= length <= 10000 and len(buffer) >= 4 + length:
                        json_bytes = buffer[4:4 + length]
                        buffer = buffer[4 + length:]
                        try:
                            msg = json.loads(json_bytes.decode("utf-8"))
                            callback(msg)
                        except json.JSONDecodeError:
                            print("Invalid JSON (Rust format)")
                        continue

                # Case 2: Plain JSON (Python)
                try:
                    msg = json.loads(buffer.decode("utf-8"))
                    buffer = b""
                    callback(msg)
                except json.JSONDecodeError:
                    # need more data
                    break
    print("Client disconnected.")

# This will be replaced by the app instance in __main__
app: Optional[SwimTimerApp] = None

def handle_message(msg):
    """Called by server thread when a JSON message arrives."""
    try:
        if app is None:
            return
        id = msg.get("id")
        cmd = msg.get("command")
        lap_time = msg.get("lap_time")
        # Map id (string) to swimmer name via app.key_map
        swimmer = app.key_map.get(str(id)) or app.key_map.get(id)
        if cmd == "start":
            app.start()
        elif cmd == "stop":
            app.stop()
        elif cmd == "split":
            if swimmer:
                app.record_lap(swimmer)
        elif cmd == "lap":
            # lap_time expected to be elapsed float (string/number)
            if swimmer and lap_time is not None:
                app.set_lap(lap_time, swimmer)
    except Exception as e:
        print("Error handling message:", e)

# ---------- Main ----------
if __name__ == "__main__":
    cfg = load_config()
    num_swimmers = int(cfg.get("swimmers", 4))
    max_laps = int(cfg.get("laps", 8))

    swimmers = [f"Lane {i}" for i in range(1, num_swimmers + 1)]

    root = tk.Tk()
    root.attributes("-fullscreen", True)
    app = SwimTimerApp(root, swimmers, max_laps=max_laps)

    start_server(handle_message)
    root.mainloop()
