"""
Checks that the selected optimized pulses are correct.

Refactored 09/12/2024
Updated 28/02/2026 — migrated to AWGManager and OscilloscopeManager classes.

@author: Marina Llano
"""

import time

import matplotlib.pylab as plt
import numpy as np
import pandas as pd
import scipy.integrate as spi
from configobj import ConfigObj

from classes.experimental_configs import (
    AwgConfiguration,
    PhotonProductionConfiguration,
    TdcConfiguration,
    Waveform,
)
from instruments.Oscilloscopes.agilent_mso9254A import OscilloscopeManager
from instruments.WX218x.awg_manager import AWGManager


def to_bool(string):
    return string.lower() in ["true", "t", "yes", "y"]


def setup_awg(config):
    """Configures the AWG and returns the AwgConfiguration and PhotonProductionConfiguration."""
    waveform_sequence = list(eval(config["waveform sequence"]))

    waveforms: dict[int, Waveform] = {}
    for key, v in config["waveforms"].items():
        phases_raw = v.get("phases")
        phases = [(float(p), int(i)) for p, i in phases_raw] if phases_raw else None
        waveforms[int(key)] = Waveform(
            fname=v["filename"],
            mod_frequency=float(v["modulation frequency"]),
            phases=phases,
        )

    marker_width_raw = config["AWG"].get("marker width")
    marker_width_samps = int(eval(marker_width_raw)) if marker_width_raw else None

    awg_config = AwgConfiguration(
        waveform_sequence=waveform_sequence,
        waveforms=waveforms,
        sample_rate=float(config["AWG"]["sample rate"]),
        burst_count=int(config["AWG"]["burst count"]),
        waveform_output_channels=tuple(int(ch) for ch in config["AWG"]["waveform output channels"]),
        marker_width_samps=marker_width_samps,
        waveform_output_channel_lags=tuple(
            float(lag_time) for lag_time in config["AWG"]["waveform output channel lags"]
        ),
    )

    tdc_config = TdcConfiguration(
        counter_channels=[int(eval(ch)) for ch in config["TDC"]["counter channels"]],
        marker_channel=int(config["TDC"]["marker channel"]),
        timestamp_buffer_size=int(config["TDC"]["timestamp buffer size"]),
    )

    photon_production_config = PhotonProductionConfiguration(
        save_location=config["save location"],
        mot_reload=eval(config["mot reload"]),
        iterations=int(config["iterations"]),
        waveform_sequence=waveform_sequence,
        waveforms=waveforms,
        waveform_stitch_delays=None,
        interleave_waveforms=None,
        awg_configuration=awg_config,
        tdc_configuration=tdc_config,
    )

    return awg_config, photon_production_config


def measure_signal(
    osc_manager: OscilloscopeManager,
    num_measurements=50,
    stokes_channel=4,
    pump_channel=1,
    timebase_range=(-1.5e-6, 1.5e-6),
):
    """Performs measurements using the oscilloscope and returns the mean acquired signal.

    Parameters
    ----------
    osc_manager : OscilloscopeManager
        Connected oscilloscope instance.
    num_measurements : int
        Number of acquisitions to average over.
    stokes_channel : int
        Oscilloscope channel for the Stokes signal.
    pump_channel : int
        Oscilloscope channel for the pump signal.
    timebase_range : tuple[float, float]
        Timebase range as (start, stop) in seconds.
    """
    channels = [pump_channel, stokes_channel]

    # Configure scope for both channels
    data_chs = {ch: {"range": (-0.5, 0.5), "impedance": "50", "coupling": "DC"} for ch in channels}
    osc_manager.configure_scope(data_chs=data_chs, timebase_range=timebase_range)
    osc_manager.configure_trigger(
        trigger_channel=pump_channel, trigger_level=0.1, trigger_slope="+"
    )

    all_stokes = []
    all_pump = []
    for _ in range(num_measurements):
        osc_manager.set_to_digitize(channels=tuple(channels))
        data = osc_manager.read_slow_return_data(channels)
        if data is None:
            raise RuntimeError("Oscilloscope returned no data")

        stokes_col = f"Channel {stokes_channel} Voltage (V)"
        pump_col = f"Channel {pump_channel} Voltage (V)"

        data_stokes = pd.DataFrame(
            {
                "Time (s)": data["Time (s)"],
                "Voltage (V)": data[stokes_col],
            }
        )
        data_pump = pd.DataFrame(
            {
                "Time (s)": data["Time (s)"],
                "Voltage (V)": data[pump_col],
            }
        )

        all_stokes.append(data_stokes)
        all_pump.append(data_pump)
        time.sleep(0.2)

    meas_stokes = pd.DataFrame()
    meas_pump = pd.DataFrame()

    for i, (data_stokes, data_pump) in enumerate(zip(all_stokes, all_pump, strict=True)):
        meas_stokes[f"Time (s) {i}"] = data_stokes["Time (s)"]
        meas_stokes[f"Voltage (V) {i}"] = data_stokes["Voltage (V)"]
        meas_pump[f"Time (s) {i}"] = data_pump["Time (s)"]
        meas_pump[f"Voltage (V) {i}"] = data_pump["Voltage (V)"]

    meas_stokes = meas_stokes[
        (meas_stokes.filter(like="Time (s)").iloc[:, 0] >= 0.822e-6)
        & (meas_stokes.filter(like="Time (s)").iloc[:, 0] <= 1.022e-6)
    ].copy()
    meas_pump = meas_pump[
        (meas_pump.filter(like="Time (s)").iloc[:, 0] >= 0.822e-6)
        & (meas_pump.filter(like="Time (s)").iloc[:, 0] <= 1.022e-6)
    ].copy()
    meas_stokes.loc[:, meas_stokes.filter(like="Time (s)").columns] -= meas_stokes.filter(
        like="Time (s)"
    ).iloc[0, 0]
    meas_pump.loc[:, meas_pump.filter(like="Time (s)").columns] -= meas_pump.filter(
        like="Time (s)"
    ).iloc[0, 0]

    sqrt_volt_stokes = np.sqrt(meas_stokes.filter(like="Voltage (V)").clip(lower=0))
    sqrt_volt_pump = np.sqrt(meas_pump.filter(like="Voltage (V)").clip(lower=0))

    sqrt_volt_pump -= abs(sqrt_volt_pump.min())

    mean_time_stokes = meas_stokes.filter(like="Time (s)").mean(axis=1)
    mean_time_pump = meas_pump.filter(like="Time (s)").mean(axis=1)
    mean_voltage_stokes = sqrt_volt_stokes.mean(axis=1)
    mean_voltage_pump = sqrt_volt_pump.mean(axis=1)
    std_voltage_stokes = sqrt_volt_stokes.std(axis=1)
    std_voltage_pump = sqrt_volt_pump.std(axis=1)

    mean_data_stokes = pd.DataFrame(
        {"Time (s)": mean_time_stokes, "Voltage (V)": mean_voltage_stokes}
    )
    mean_data_pump = pd.DataFrame({"Time (s)": mean_time_pump, "Voltage (V)": mean_voltage_pump})
    std_data_stokes = pd.DataFrame(
        {"Time (s)": mean_time_stokes, "Voltage (V)": std_voltage_stokes}
    )
    std_data_pump = pd.DataFrame({"Time (s)": mean_time_pump, "Voltage (V)": std_voltage_pump})

    return mean_data_stokes, std_data_stokes, mean_data_pump, std_data_pump


##############################################################

file_path = "data/2025-01-31/stokes_150ns_20.csv"
stokes_th = pd.read_csv(file_path, header=None)
stokes_th = stokes_th.T
stokes_th = stokes_th.to_numpy().flatten()

file_path = "data/2025-01-31/pump_150ns_20.csv"
pump_th = pd.read_csv(file_path, header=None)
pump_th = pump_th.T
pump_th = pump_th.to_numpy().flatten()

stokes_th /= stokes_th.max()
pump_th /= pump_th.max()

# we send to the awg the most optimized input versions found previously
config_path = r"c:\Users\apc\Documents\marina\newPhotonProductionConfigNEW"
config = ConfigObj(config_path)

# write here the waveforms optimized
opt_stokes = r"c:\Users\apc\Documents\marina\03_mar\06-03\0.25\stokes\x_optimized_1.csv"
opt_pump = r"c:\Users\apc\Documents\marina\03_mar\06-03\0.1\pump\x_optimized_1.csv"
config["waveforms"]["1"]["filename"] = opt_stokes  # type: ignore
config["waveforms"]["2"]["filename"] = opt_pump  # type: ignore
config.write()
awg_config, photon_production_config = setup_awg(config)

# Upload waveforms to the AWG and arm for triggering
awg = AWGManager()
awg.upload_and_arm(awg_config)

osc_manager = OscilloscopeManager()
stokes, std_stokes, pump, std_pump = measure_signal(
    osc_manager, num_measurements=50, timebase_range=(-1.5e-6, 1.5e-6)
)
t = np.linspace(0, 150e-9, len(stokes))

stokes /= stokes.max()
pump /= pump.max()

overlap_region = np.minimum(stokes, pump)  # we compute overlap taking measures with 1200 points
overlap_area = spi.simpson(overlap_region, x=t)
print(overlap_area)

plt.plot(t, stokes, "r", label="Stokes measured")
plt.plot(t, pump, "g", label="Pump measured")
plt.plot(t[::8], stokes_th, "r", linestyle="--")
plt.plot(t[::8], pump_th, "g", linestyle="--")
plt.show()
