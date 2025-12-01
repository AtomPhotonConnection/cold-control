import serial
import time
import csv
import os
import threading
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import sys

# Replace with your port, e.g. "COM3" on Windows or "/dev/ttyUSB0" on Linux/macOS
PORT = "COM3"
BAUD = 115200       # TF930 requires 115200 bits per second, 8, no parity (baurd rate - speed of data transfer)
TIMEOUT = 2.0       # seconds (how long the program will wait for incoming response from the TF930)
STORE_PATH = " "    # csv file of freq vs time is stored

# two channels of the frequency counter
CHANNEL_INFO = {
    "1": {"name": "Channel A (input A)", "cmd": "F1", "range": "approx 30 Hz – 125 MHz"},
    "2": {"name": "Channel B (input B)", "cmd": "F3", "range": "approx 80 MHz – 3 GHz"},
}

def open_serial(port=PORT):
    """Open and return a serial.Serial object configured for TF930."""
    return serial.Serial(port, baudrate=BAUD, bytesize=8, parity='N', stopbits=1, timeout=TIMEOUT)

def query_once(ser, cmd):
    """
    Send a command to TF930
    Read one line of response from TF930
    Return as text terminated by LF (\\n) and read one response line.
    
    Send a command terminated by LF (\n) and read one response line.
    The TF930 expects commands terminated with LF; responses end with CR+LF.
    """
    # ensure remote mode is set when a character is received (manual covers remote/local)
    ser.write((cmd + "\n").encode('ascii')) # send the comment
    # read a response line (includes CRLF); strip CR/LF and decode
    resp = ser.readline().decode('ascii', errors='ignore').strip()
    return resp

def parse_tf930_result(s):
    """
    Try to parse an instrument result like '0012345.6789e+3 Hz' into a float and a unit.
    Returns (value_float or None, MHz.
    """
    if not s:
        return None, ""
    try:
        # remove leading/trailing whitespace
        s = s.strip()
        # try to find numeric portion by detecting 'e' (exponent) then whitespace
        # fallback: attempt float conversion of the first whitespace-separated token
        # split numbers and units
        tokens = s.split()
        # common full token is something like '0012345.6789e+3' or '1.234e+6'
        candidate = tokens[0]

        # handle cases where units are appended without space (rare) - try to find the first non-numeric char from end
        # but simplest: try direct float conversion; if fails, try to extract numeric substring
        try:
            val = float(candidate)
            units = " ".join(tokens[1:]) if len(tokens) > 1 else ""
            return val, units
        except ValueError:
            # attempt to find numeric substring: characters allowed in numeric: digits, + - . e E
            numchars = set("0123456789+-.eE") # allowed number characters
            num = "".join(ch for ch in s if ch in numchars) # extract the number from the token
            if not num:
                return None, "MHz"
            val = float(num)

            # units = original minus numeric substring
            units = s.replace(num, "").strip()

        # --- Unit normalization to MHz ---
        units = units.lower()  # normalize for matching

        if units == "hz":
            val_mhz = val / 1e6
        elif units == "khz":
            val_mhz = val / 1e3
        elif units == "mhz":
            val_mhz = val
        elif units == "ghz":
            val_mhz = val * 1e3
        else:
            # If unknown unit, assume Hz (safe fallback)
            val_mhz = val / 1e6

        return val_mhz, "MHz"
    
    except Exception:
        return None, s

def check_connection_and_get_idn(port=PORT):
    """
    Try to open the serial port and query *IDN? to verify the device.
    Returns (ser, idn_string). Raises SerialException on failure.
    """
    ser = open_serial(port)
    # small delay to let device settle
    time.sleep(0.1)
    # ask for ID string; if empty or times out, treat as error
    try:
        idn = query_once(ser, "*IDN?")
    except Exception:
        ser.close()
        raise

    if not idn:
        # attempt a fallback query or decide the device didn't respond
        ser.close()
        raise serial.serialutil.SerialException("TF930 did not respond to *IDN? on port {}".format(port))
    return ser, idn

def choose_channel():
    """Prompt user to select channel A or B and show the frequency range."""
    print("Select channel to measure:")
    for key in sorted(CHANNEL_INFO.keys()):
        info = CHANNEL_INFO[key]
        print(f" {key}) {info['name']} — freq range: {info['range']}")
    while True:
        choice = input("Enter 1 or 2 (default 1): ").strip() or "1"
        if choice in CHANNEL_INFO:
            return CHANNEL_INFO[choice]
        print("Invalid selection. Please type 1 or 2.")

def ensure_store_path(parent_dir):
    """
    Ensure the provided path is an existing directory and writable.
    This treats `parent_dir` as the parent folder where we will create:
        parent_dir/frequency_counter_calibration.csv

    Returns the full CSV file path.

    Raises:
      FileNotFoundError: if parent_dir does not exist
      PermissionError: if parent_dir is not writable
    """
    if not parent_dir:
        parent_dir = "."

    parent = os.path.abspath(parent_dir)

    if not os.path.exists(parent):
        raise FileNotFoundError(
            f"Error: The directory '{parent}' does not exist.\n"
            "Please create it manually or choose another save location."
        )

    # # Check write permission in the directory
    # testfile = os.path.join(parent, ".tf930_write_test")
    # try:
    #     with open(testfile, "w") as f:
    #         f.write("test")
    #     os.remove(testfile)
    # except Exception:
    #     raise PermissionError(
    #         f"Error: No write permission in directory '{parent}'.\n"
    #         "Please adjust permissions or choose another directory."
    #     )

    csv_name = "frequency_counter_calibration.csv"
    return os.path.join(parent, csv_name)

# === Recording logic ===
def record_loop(ser, channel_cmd, store_dir):
    """
    Record frequency readings from the TF930 on the selected channel.
    - store_dir: parent directory where the CSV file will be created
    - stops recording when the user presses ENTER again
    - keeps data in memory and writes CSV only after recording ends
    - CSV header: ["frequency","time"]

    Returns a list of recorded rows (dicts) for optional plotting:
      [{"time": datetime, "frequency": "<value and units or raw>"} ...]
    """
    # Validate / get final CSV file path
    csv_path = ensure_store_path(store_dir)

    # Configure instrument: set function (channel) and measurement time (M2 = 1s)
    ser.write((channel_cmd + "\n").encode())
    time.sleep(0.05)
    ser.write(("M2\n").encode())   # M2 -> 1 s measurement time (adjust if you want)
    time.sleep(0.05)

    # Event to signal stopping (set by the input thread)
    stop_event = threading.Event()

    def wait_for_enter_to_stop():
        """Thread target: blocks on input() and sets stop_event once user presses Enter."""
        input("\nPress ENTER to stop recording...\n")
        stop_event.set()

    # Start the stopper thread (daemon so it won't block program exit)
    stopper = threading.Thread(target=wait_for_enter_to_stop, daemon=True)
    stopper.start()

    print("\nRecording... (press ENTER to stop)\n")
    data_rows = []

    start_time = None

    try:
        while not stop_event.is_set():
            # blocking read of the next valid completed measurement
            raw = query_once(ser, "N?")  # reading the response from TF930
            ts = datetime.utcnow()       # current UTC time

            # set the start time at the moment of the first sample
            if start_time is None:
                start_time = ts

            # elapsed time in seconds since the first sample (first sample -> 0.0)
            t_sec = (ts - start_time).total_seconds()

            # parse the instrument string to get a numeric value in MHz
            # (assumes parse_tf930_result returns (value_in_MHz or None, "MHz"))
            val_mhz, _ = parse_tf930_result(raw)

            # ensure we store a Python float or None (no unit text)
            freq_val = float(val_mhz) if val_mhz is not None else None

            # keep in-memory for later CSV write / plotting
            # store minimal fields: time (s) and frequency (float or None)
            data_rows.append({
                "time_s": t_sec,
                "frequency_mhz": freq_val,
                "raw": raw,
                "timestamp": ts,
            })

            # console feedback (human readable)
            if freq_val is None:
                print(f"{ts.isoformat()}Z - parse failed: '{raw}'  (t={t_sec:.3f}s)")
            else:
                # show frequency to 6 decimal places for readability
                print(f"{ts.isoformat()}Z - {freq_val:.6f} MHz  (t={t_sec:.3f}s)")

            # loop continues until Enter pressed (stop_event set)

    except Exception as ex:
        # If something unexpected happens during reading, print it and stop recording
        print("\nError during recording:", ex)
        stop_event.set()


    # Write CSV after recording ends
    try:
        # header must be exactly: frequency, time
        with open(csv_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["frequency (MHz)", "time (s)"]) # write the header

            for row in data_rows:
                freq = row["frequency_mhz"]      # already a float or None
                t = row["time_s"]               # elapsed time in seconds (float)

                # If frequency is None (parse failure), write empty cell
                freq_cell = "" if freq is None else f"{freq:.12g}"
                time_cell = f"{t:.6f}"
                writer.writerow([freq_cell, time_cell])
    except Exception as ex:
        print(f"\nFailed to write CSV to {csv_path}: {ex}")

    return data_rows

def plot_results(data_rows, store_dir, title="Frequency vs Time"):
    """Plot frequency (value) vs timestamp using matplotlib. Ignore rows with None value."""
    if not data_rows:
        print("No data recorded.")
        return
    
    df = pd.DataFrame(data_rows)
    # drop rows without numeric value
    df = df.dropna(subset=["value"])
    if df.empty:
        print("No numeric values to plot.")
        return
    # convert timestamps for plotting
    df["ts"] = pd.to_datetime(df["timestamp"])  # they are already datetimes
    df = df.sort_values("epoch")
    plt.figure(figsize=(10, 5))
    plt.plot(df["ts"], df["value"], marker='o', linestyle='-')
    plt.xlabel("Time (s)")
    plt.ylabel("Frequency (MHz)")
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # storing the plot 
    plot_name = "frequency_counter_calibration_plot"
    path =  os.path.join(store_dir, plot_name)
    plt.savefig(path)

# === Main execution ===
def main():
    print("TF930 Recorder")
    print("Attempting to open port:", PORT)
    try:
        ser, idn = check_connection_and_get_idn(PORT)
    except serial.serialutil.SerialException as e:
        print("Error: could not open TF930 on port", PORT)
        print("Exception:", e)
        sys.exit(1)

    print("Connected to device. IDN response:", idn)
    # show current measurement quickly
    try:
        time.sleep(0.05)
        current = query_once(ser, "?")
        print("Current result string:", current)
    except Exception:
        print("Warning: couldn't read current result (?). Continuing.")

    # let the user choose channel
    info = choose_channel()
    print(f"Selected: {info['name']} ({info['cmd']}). Range note: {info['range']}")

    # prompt user to start recording
    input("Press Enter to start recording (Enter again to stop)...")

    # run the recorder loop
    try:
        data_rows = record_loop(ser, info['cmd'], STORE_PATH)
    finally:
        # ensure port closed
        try:
            ser.close()
        except Exception:
            pass

    # plot
    plot_results(data_rows, STORE_PATH)

if __name__ == "__main__":
    main()



######################################################################################################################
# analysis of data
def analyzing_frequency_fluc (data_rows):
    # times = [row["time_s"] for row in data_rows]
    freq_list = [row["frequency_mhz"] for row in data_rows]
    freq_arr = np.array(freq_list)

    f_min = np.min(freq_arr)
    f_max = np.max(freq_arr)
    f_avg = np.average(freq_arr)
    f_std = np.std(freq_arr)

    print("Max Freq: ", f_max)
    print("Min Freq: ", f_min)
    print("Avg Freq: ", f_avg)
    print("Standard deviation: ", f_std)






