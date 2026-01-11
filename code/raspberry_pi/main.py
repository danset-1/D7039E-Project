# Starts the program
from Connection import MicrocontrollerConnection as mConn
from Timer import timer
from Screen import app
import tkinter as tk

# Load and setup to run the program
if __name__ == "__main__":
    # Load config with number of laps and lanes stored
    cfg = app.load_config()
    # Get values from config for maximum laps and number of swimming lanes/swimmers
    num_swimmers = int(cfg.get("swimmers"))
    max_laps = int(cfg.get("laps"))

    # Creates variable for each lane
    swimmers = [f"Lane {i}" for i in range(1, num_swimmers + 1)]

    # Setup for GUI
    root = tk.Tk()
    root.attributes("-fullscreen", True)    # Make the GUI open in fullscreen

    # Create the class that operates the swimming timer part
    ap = app.SwimTimerApp(root, swimmers, max_laps=max_laps)

    # Setup server to listen for signals from microcontroller (Becomes its own thread so it can run in background)
    mConn.start_server(mConn.handle_message, ap)

    # Start the app
    root.mainloop()