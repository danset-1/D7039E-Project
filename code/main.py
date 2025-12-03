from Connection import MicrocontrollerConnection as mConn
from Timer import timer
from Screen import app
import tkinter as tk

if __name__ == "__main__":
    swimmers = [f"Lane {i}" for i in range(1, 5)] # change to ID swimmers
    root = tk.Tk()
    ap = app.SwimTimerApp(root, swimmers, max_laps=8)

    mConn.start_server(mConn.handle_message, ap)
    root.mainloop()