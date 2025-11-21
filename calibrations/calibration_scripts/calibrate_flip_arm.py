#!/usr/bin/env python3
"""
Simple calibration helper (overwrites CSV each run).

Two main functions:
  - measure_loop(output_csv, set_voltage, read_power1, flip, read_power2, voltages=None, delay=0.25)
      Drive DAQ and record (voltage, power1, power2) repeatedly to CSV.
      Overwrites any existing calibration file.
  - fit_and_interpolate(calib_csv, out_png=None)
      Fits a linear mapping power2 = a*power1 + b, saves optional plot, and returns predict(power1).

Minimal and editable — intended for occasional use.
"""
import sys
import os
import csv
import time
from typing import Callable, Iterable, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


from classes.DAQ import DAQ_controller
from instruments.TF930 import TF930
from instruments.ThorlabsPM100 import ThorlabsPM100
from lab_control_functions.calibration_helper_functions import *

# -------------------------
# Measurement loop (always overwrites existing CSV)
# -------------------------
def measure_loop(
    output_csv: str,
    set_voltage: Callable[[float], None],
    read_power_flip: Callable[[], float],
    flip: Callable[[str], None],
    read_power_target: Callable[[], float],
    voltages: Iterable[float],
    repeats: int = 1,
    delay: float = 5.0,
):
    """
    Drive voltages and record paired powermeter readings.
    Overwrites existing CSV if it exists.

    Args:
      output_csv: path to CSV (will overwrite if exists).
      set_voltage: callable(voltage) -> None
      read_power1: callable() -> float  # reading before flip
      flip: callable("in"|"out") -> None  # "in" = send beam to powermeter 2 (target); "out" = to powermeter 1 (flip arm)
      read_power2: callable() -> float  # reading at target
      voltages: iterable of voltages to step.
      repeats: how many times to repeat whole sweep (useful for averaging)
      delay: seconds to wait after setting voltage or flipping before reading
    """
    
    data = []  # list to hold all measurements

    header = ["voltage", "power_flip", "power_target", "timestamp"]

    for _ in range(repeats):
        for v in voltages:
            print(f"Setting voltage to {v:.3f} V")
            set_voltage(float(v))
            flip("up")

            time.sleep(delay)
            p1 = float(read_power_flip())

            flip("down")

            time.sleep(delay)
            p2 = float(read_power_target())

            ts = time.time()
            data.append([v, p1, p2, ts])

    # create dataframe and save once
    df = pd.DataFrame(data, columns=header)
    df.to_csv(output_csv, index=False)
    print(f"Saved {len(df)} measurements to {output_csv}")


def measure_loop_test(
    output_csv: str,
    set_voltage: Callable[[float], None],
    read_power_flip: Callable[[], float],
    flip: Callable[[str], None],
    read_power_target: Callable[[], float],
    voltages: Iterable[float],
    repeats: int = 1,
    delay: float = 10.0,
):
    data = []  # list to hold all measurements
    header = ["voltage", "power_flip", "timestamp"]
    flip("up")

    for _ in range(repeats):
        for v in voltages:
            print(f"Setting voltage to {v:.3f} V")
            set_voltage(float(v))

            time.sleep(delay)
            p1 = float(read_power_flip())

            ts = time.time()
            data.append([v, p1, ts])

    # create dataframe and save once
    df = pd.DataFrame(data, columns=header)
    df.to_csv(output_csv, index=False)
    print(f"Saved {len(df)} measurements to {output_csv}")




# -------------------------
# Fit and interpolate
# -------------------------
def fit_and_interpolate(calib_csv: str, out_png: Optional[str] = None) -> Tuple[Callable[[float], float], dict]:
    df = pd.read_csv(calib_csv)
    if "power1" not in df.columns or "power2" not in df.columns:
        df = df.iloc[:, :3]
        df.columns = ["voltage", "power1", "power2"]

    x = df["power1"].values.astype(float)
    y = df["power2"].values.astype(float)

    a, b = np.polyfit(x, y, 1)
    y_pred = a * x + b
    residuals = y - y_pred
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot != 0 else float("nan")
    rmse = np.sqrt(np.mean(residuals ** 2))

    def predict(p1: float) -> float:
        return float(a * p1 + b)

    fit_info = {"a": float(a), "b": float(b), "r2": float(r2), "rmse": float(rmse), "n": int(len(x))}

    if out_png:
        plt.figure(figsize=(6, 4))
        plt.scatter(x, y, label="data")
        xs = np.linspace(min(x), max(x), 200)
        plt.plot(xs, a * xs + b, label=f"linear fit: y={a:.4g}x+{b:.4g}")
        plt.xlabel("power1 (flip arm)")
        plt.ylabel("power2 (target)")
        plt.title(f"Calibration (n={fit_info['n']}, R²={fit_info['r2']:.4f}, RMSE={fit_info['rmse']:.4g})")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(out_png, dpi=150)
        plt.close()

    return predict, fit_info





if __name__ == "__main__":
    config_reader = ConfigReader(os.getcwd() + '/configs/rootConfig.ini')
    daq_config_fname = config_reader.get_daq_config_fname()
    daq_reader = DaqReader(daq_config_fname)
    daq:DAQ_controller = daq_reader.load_DAQ_controller()
    daq.continuousOutput=True

    

    freq_channel = 3
    daq.updateChannelValue(int(freq_channel), 3.7409093554844883)# need to set correct freq
    amp_channel = 7
    flip_channel = 4 # note this is a DIO channel, not analog
    voltages_list = np.linspace(0, 4, 30)#[1.0, 1.6, 1.9, 2.1, 2.3] # Voltages to step through
    #
    rm = visa.ResourceManager()
    all_res = rm.list_resources()

    pm_address_target = "USB0::0x1313::0x8079::P1002347::0::INSTR"
    pm_address_flip = "USB0::0x1313::0x8079::P1002563::0::INSTR"

    try:
        pm_target_res = rm.open_resource(pm_address_target)
        #inst = rm.get_instrument(resource)
        print(pm_target_res.query("*IDN?").split(',')) # type: ignore
        if pm_target_res.query("*IDN?").split(',')[1] == 'PM100A': # type: ignore
            pm_target = ThorlabsPM100(pm_target_res) # --> Thorlabs,PM100A,P1002563,2.3.0
    except visa.errors.VisaIOError as e:
        print(f"powermeter with address {pm_address_target} is not available.")
        print(f"error message: {e}")

    try:
        pm_flip_res = rm.open_resource(pm_address_flip)
        #inst = rm.get_instrument(resource)
        print(pm_flip_res.query("*IDN?").split(',')) # type: ignore
        if pm_flip_res.query("*IDN?").split(',')[1] == 'PM100A': # type: ignore
            pm_flip = ThorlabsPM100(pm_flip_res) # --> Thorlabs,PM100A,P1002563,2.3.0
    except visa.errors.VisaIOError as e:
        print(f"powermeter with address {pm_address_flip} is not available.")
        print(f"error message: {e}")


    if pm_target is None or pm_flip is None:
        raise Exception("One of the power meters was not found, cannot continue.")
    
    configure_power_meter(pm_flip, nMeasurmentCounts=3)
    configure_power_meter(pm_target, nMeasurmentCounts=3)

    # Create hardware callables (replace daq, amp_channel, flip_channel with your objects/IDs)
    set_v = lambda v: daq.updateChannelValue(int(amp_channel), float(v))
    def flip_fn(pos: str):
        if pos == "up":
            daq.update_dio(flip_channel, True)
        elif pos == "down":
            daq.update_dio(flip_channel, False)
        else:
            raise ValueError("flip position must be 'up' or 'down'")
        
    read_fn_target = lambda: float(pm_target.read) # type: ignore
    read_fn_flip = lambda: float(pm_flip.read) # type: ignore

    # Now call measure_loop with your real functions:
    measure_loop(r"calibrations\miscellaneous\flip_mirror_calib.csv", set_v, read_fn_flip,
                  flip_fn, read_fn_target, voltages=voltages_list, repeats=2)

    # After measuring you can fit:
    pred, info = fit_and_interpolate(r"calibrations\miscellaneous\flip_mirror_calib.csv", 
                                     out_png=r"calibrations\miscellaneous\calib_plot.png")
    print(info)


    if pm_target_res is not None:
        try:
            pm_target_res.close()
        except Exception:
            pass

    if pm_flip_res is not None:
        try:
            pm_flip_res.close()
        except Exception:
            pass
    
    daq.releaseAll()