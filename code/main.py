from Connection import MicrocontrollerConnection as mConn
from Timer import timer
from Screen import app
import tkinter as tk

if __name__ == "__main__":
    cfg = app.load_config()
    num_swimmers = int(cfg.get("swimmers", 4))
    max_laps = int(cfg.get("laps", 8))

    swimmers = [f"Lane {i}" for i in range(1, num_swimmers + 1)]
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    ap = app.SwimTimerApp(root, swimmers, max_laps=max_laps)

    mConn.start_server(mConn.handle_message, ap)
    root.mainloop()