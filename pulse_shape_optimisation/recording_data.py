#!/usr/bin/env python3
"""
run_awg_and_scope.py

Usage:
    python run_awg_and_scope.py /path/to/awg_config.ini \
        [--awg-resource USB0::0xAAAA::0xBBBB::SERIAL::INSTR] \
        [--scope-resource USB0::0x0957::0x9009::MY123::INSTR] \
        [--scope-channel 1] \
        [--averages 16]

What it does:
 - Loads the AWG configuration from the provided .ini (uses AwgConfigReader).
 - Programs the AWG (AWGManager.upload_and_play(cfg)).
 - Runs an oscilloscope acquisition (hardware-averaged by default) and
   saves the resulting DataFrame as a CSV in the same folder as the AWG .ini.
 - (Optional) plotting section at the bottom (commented out).
 
Note: this script is intentionally defensive about attribute names found
in the loaded AwgConfiguration and accepts explicit resource strings via CLI.
"""

import sys
import os

import argparse
import datetime
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# Import classes from your uploaded modules
# pulse_experiment provides the AwgConfigReader / AwgConfiguration usage.
sys.path.append(
    os.path.dirname(
        os.path.abspath(r"C:\Users\LabUser\Documents\cold-control\pulse_shape_optimisation")
    )
)
from classes.config_readers import (
    AwgConfigReader,
)  # used in pulse_experiment flow. :contentReference[oaicite:2]{index=2}
from classes.experimental_configs import (
    ScopeConfiguration,
)  # used to set up scope parameters from config.
from instruments.Oscilloscopes.agilent_mso9254A import (
    OscilloscopeManager,
)  # scope helpers (digitize/read/save).
from instruments.WX218x.awg_manager import AWGManager


def find_awg_resource_name(cfg_obj):
    """Try common attribute names for AWG resource identifier in AwgConfiguration."""
    for name in ("awg_id", "resource_id", "resource", "id", "visa_resource"):
        if hasattr(cfg_obj, name):
            val = getattr(cfg_obj, name)
            if val:
                return val
    return None


def find_default_scope_channels(cfg_obj):
    """Try to find a sensible channel list from AWG config (fallback: [1])."""
    # AWG config likely doesn't contain scope channels; return [1] as safe default.
    return [1]


def timestamp_str():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def main(ini_path_str, save_csv_path_str, awg_res=None, scope_res=None, averages=16):
    ini_path = Path(ini_path_str).expanduser().resolve()
    if not ini_path.exists():
        print(f"ERROR: AWG config not found: {ini_path}")
        sys.exit(2)

    # 1. Load AWG configuration
    print(f"Loading AWG configuration from: {ini_path}")
    awg_cfg = AwgConfigReader(str(ini_path)).load_awg_configuration()

    # 2. Connect to AWG
    awg_resource = awg_res or find_awg_resource_name(awg_cfg)
    if awg_resource is None:
        print("ERROR: No AWG resource ID found! Please provide it manually.")
        return

    print(f"Connecting to AWG: {awg_resource}")

    awg = AWGManager(resource_id=awg_resource)
    try:
        # We call reset BEFORE upload_and_play to ensure a clean slate
        # but avoid calling it inside the loop if possible.
        awg.reset()
        print("Uploading waveforms to AWG...")
        # This calls your _upload_core function
        awg.upload_and_play(awg_cfg)
    except Exception as e:
        print(f"AWG Error: {e}")
        # If -113 persists, it's likely the WX218x firmware
        # rejecting a command while in the wrong 'Run' state.
        return

    print("Uploading & playing waveforms...")
    awg.upload_and_play(awg_cfg)

    # 3. Connect to Scope
    print(f"Connecting to oscilloscope at: {scope_res}")
    # Pass the scope_res into the manager
    scope = OscilloscopeManager(scope_id=scope_res)

    try:
        _scope_config = ScopeConfiguration(
            trigger_channel=4,
            trigger_level=0.3,
            sample_rate=1e9,
            time_range=(-0.23e-6, 3e-6),
            data_channels={
                1: {"range": (-0.8, 0.8), "impedance": "low", "coupling": "DC"},
                2: {"range": (-4, 4), "impedance": "low", "coupling": "DC"},
                3: {"range": (-4, 4), "impedance": "low", "coupling": "DC"},
                4: {"range": (-0.8, 0.8), "impedance": "low", "coupling": "DC"},
            },
        )
        target_scope_channel = 3

        trigger_lvl = 2  # Adjust this value to cross your signal threshold
        scope.configure_from_config(scope_config=_scope_config)

        # 3. Proceed with acquisition as usual
        df = scope.read_slow_return_data_avgd([3], averages=16)

        if df is not None and not df.empty:
            # Save the CSV
            final_path = Path(save_csv_path_str)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(final_path, index=False)
            print(f"SUCCESS: Data saved to {final_path}")

            # --- PLOTTING ---
            plt.figure(figsize=(10, 6))
            # Assuming first column is Time, others are Voltage
            time_data = df.iloc[:, 0]
            volt_data = df.iloc[:, 1]

            plt.plot(
                time_data, volt_data, label=f"Channel {target_scope_channel}", color="tab:blue"
            )
            plt.title(f"Scope Capture: {ini_path.stem}")
            plt.xlabel("Time (s)")
            plt.ylabel("Voltage (V)")
            plt.grid(True, alpha=0.3)
            plt.legend()
            plt.show()
            # ------------------------
        else:
            print("Warning: Scope returned no data.")

    except Exception as e:
        print(f"Error during scope acquisition: {e}")
    finally:
        scope.quit()

    print("Done.")


if __name__ == "__main__":
    # SET YOUR PATHS HERE
    MY_INI = r"C:\Users\LabUser\Documents\cold-control\configs\pulse_shaping_expt\awg_configs\feb26_awg_updated.ini"
    MY_SAVE_PATH = r"C:\pulse_shaping_data\optimisation_results\channel_delay\channel_2_0.50.csv"
    # MY_SAVE_PATH = r"C:\pulse_shaping_data\optimisation_results\channel_delay\testing.csv"

    MY_AWG_ADDRESS = "USB0::0x168C::0x1284::0000215582::0::INSTR"
    MY_SCOPE_ADDRESS = "USB0::0x2A8D::0x900E::MY53450121::0::INSTR"

    # Run the function directly
    main(MY_INI, MY_SAVE_PATH, awg_res=MY_AWG_ADDRESS, scope_res=MY_SCOPE_ADDRESS, averages=16)
