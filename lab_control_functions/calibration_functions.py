"""
File containing functions to generate calibration data for driving AOMs with DAQ cards and the AWG.

Refactored 09/12/2024

@author: Matt King, Marina
"""

import re
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import serial

from classes.daq import DAQController
from instruments.TF930 import tf930_manager
from instruments.ThorlabsPM100 import ThorlabsPM100
from instruments.WX218x import awg_manager
from lab_control_functions.calibration_helper_functions import (
    configure_power_meter,
    create_file,
    default_v_step,
    get_power_meter,
    save_plot,
)

base_path = Path(__file__).resolve().parent.parent
CALIB_CSV = base_path / "calibrations" / "miscellaneous" / "flip_mirror_calib.csv"


def daq_driven_aom_response(
    daq_controller: DAQController,
    frequency_channel: int,
    amp_channel: int,
    frequency_voltage_pairs: dict,
    v_range,
    v_step=None,
    delay=0.1,
    repeats=3,
    save_folder="unfiled_data",
):
    """
    Creates a calibration file between the voltage given to an AOM and absolute power output.

    Inputs:
        daq_controller (DaqReader) - a DAQ_controller object to un the DAQ cards.
        frequency_channel (int) - DAQ channel number corresponding to AOM frequency
        amp_channel (int) - The channel number which is corresponds to the AOM amplitude
        frequency_voltage_pairs (dict) - dictionary with keys corresponding to AOM frequencies and values corresponding
                                         to the voltages required to drive the AOM at those frequencies
        v_range (tuple) - A voltage range to calibrate between of the form (V_min, V_max).
        v_step (float) - The voltage step over between taking calibration measurements. The default is calculated to be
                          equivilent to increasing the digital output on a 4096-bit channel with a -10 to 10V output range.
        delay (float) - How long to wait between writing a new voltage and querying the frequency counter.
        repeats (int)  - How many measurements to take and average over when reading a value from the power meter
                          (note 1 measurement is about 3ms).
    """

    if v_step is None:
        v_step = default_v_step()

    file_path = Path.cwd() / "calibrations" / save_folder

    # Find and configure a power meter connected to the computer
    inst, power_meter = get_power_meter()
    power_meter: ThorlabsPM100 = power_meter  # declare the type for easier editing
    configure_power_meter(power_meter, n_measurement_counts=repeats)

    # loop through the different frequencies (and their associated voltages)
    for freq, v in frequency_voltage_pairs.items():
        calib_name = f"amp_at_{freq}MHz"
        daq_controller.update_channel_value(frequency_channel, v)
        time.sleep(3)

        # apply a range of voltages to the daq card and measure the output amplitudes
        voltage_data = np.arange(v_range[0], v_range[1] + v_step, v_step)
        amp_data = np.empty(len(voltage_data))
        print("Running through voltages...might take a while...")
        for i in range(len(voltage_data)):
            print(voltage_data[i])
            daq_controller.update_channel_value(amp_channel, voltage_data[i])
            time.sleep(delay)
            amp_data[i] = float(power_meter.read)  # pyright: ignore[reportArgumentType]
        print("...finished!")

        units = str(power_meter.sense.power.dc.unit.split("\n")[0])  # pyright: ignore[reportAttributeAccessIssue]
        # print(type(units), repr(units))
        # Just a hack to convert W to uW as it's nicer.
        if units == "W":
            amp_data = amp_data * 10**6
            units = "uW"

        # save the data and the plot
        create_file(file_path / calib_name, voltage_data, amp_data, units)
        save_plot(
            file_path / f"{calib_name}_plot.png",
            voltage_data,
            amp_data,
            units,
            f"freq = {freq}MHz",
        )
    if inst is not None:
        inst.close()


def awg_driven_aom_response(
    freqs,
    name,
    awg_channel,
    n_steps=20,
    repeats=3,
    delay=0.2,
    calibration_lims=(0, 1),
    save_folder="unfiled_data",
):
    """Creates a calibration file detailing the dependence of the power through the aom depending on the
    voltage level of the awg waveform.

    Inputs:
        freqs (list) - frequencies at which the awg should drive the aom
        name (str) - name of the laser producing the beam
        awg_channel (int) - awg channel that drives the aom
        n_steps (int) -
        repeats (int) - How many measurements to take and average over when reading a value from the power meter
                          (note 1 measurement is about 3ms).
        delay (float) - How long to wait between writing a new voltage and querying the frequency counter
        calibration_lims (tuple) - limits of the calibration
        save_folder (str) - name of the folder to save the calibration results in (under /calibrations)
    """

    # get complete path to folder to save data in
    save_location = Path.cwd() / "calibrations" / save_folder

    # Open and configure the AWG
    sample_rate = 1.25 * 10**9
    print("Creating AWG instance")
    awg = awg_manager.AWGManager()
    print("Connecting...")

    for ch in [1, 2, 3, 4]:
        awg.disable_channel(ch)

    awg.set_sample_rate(sample_rate, (1, 2, 3, 4))

    awg.set_continuous(True)

    inst, power_meter = get_power_meter()
    power_meter: ThorlabsPM100 = power_meter  # declare the type for easier editing
    configure_power_meter(power_meter, n_measurement_counts=repeats)

    for freq in freqs:
        # Run through the voltages and record the TF930 output
        level_data = np.linspace(calibration_lims[0], calibration_lims[1], n_steps)
        cal_data = np.empty(n_steps)
        print("Running through awg levels...might take a while...")

        for i, level in enumerate(level_data):
            print("Level:", level)

            awg.play_sine_wave(awg_channel, frequency=freq, amplitude=level)

            awg.enable_channel(awg_channel)
            time.sleep(delay)
            cal_data[i] = power_meter.read

            print(cal_data[i])

            awg.disable_channel(awg_channel)

        print("...finished taking data")

        save_plot_location = save_location / "plots"
        save_plot_location.mkdir(parents=True, exist_ok=True)

        # save microWatts
        cal_data = cal_data * 10**6  # [x*10**6 for x in calData]
        save_plot(
            save_plot_location / f"{freq}MHz_abs_power.png",
            level_data,
            cal_data,
            "uW",
            f"{freq}MHz: Power vs level",
        )
        create_file(
            save_location / f"{name}_{awg_channel}_{freq}MHz_abs",
            level_data,
            cal_data,
            "uW",
            level_units="level",
        )

        end_on_max = False
        while not end_on_max:
            #         indexMin, indexMax = calData.index(min(calData)), calData.index(max(calData))
            index_min = min(
                range(len(cal_data)),
                key=lambda i: abs(
                    cal_data[i] - (min(cal_data) + calibration_lims[0] * max(cal_data))
                ),
            )
            index_max = min(
                range(len(cal_data)),
                key=lambda i: abs(cal_data[i] - (max(cal_data) * calibration_lims[1])),
            )

            level_data, cal_data = (
                level_data[index_min : index_max + 1],
                cal_data[index_min : index_max + 1],
            )

            if np.argmax(cal_data) != len(cal_data) - 1:
                calibration_lims = (calibration_lims[0], calibration_lims[1] - 0.1)
            else:
                end_on_max = True

        print(
            f"Calibration limits set to {calibration_lims} to avoid a maximum in the middle of the calibration range."
        )

        def normalise(values):
            mi, ma = np.min(values), np.max(values)
            return (values - mi) / (ma - mi)

        cal_data = 100 * normalise(cal_data)

        save_plot(
            save_location / f"{name}_{awg_channel}_{freq}MHz_rel_power_plot.png",
            level_data,
            cal_data,
            "%",
            f"{freq}MHz: Rel Power vs level",
        )
        create_file(
            save_location / f"{name}_{awg_channel}_{freq}MHz_rel",
            level_data,
            cal_data,
            "%",
            level_units="level",
        )

    print(
        "Resetting awg...",
    )
    awg.reset()
    print("calibration finished.")
    awg.close()

    if inst is not None:
        inst.close()


def calibrate_frequency(
    daq_controller,
    ch_num_to_calibrate,
    calibration_v_range=(0, 10),
    calibration_v_step=None,
    write_to_query_delay=0.1,
    query_to_read_delay=0.3,
):
    """
    NOT YET FIXED

    Creates a calibration file between the voltage given to an AOM and the frequency output.
        daq_controller - a DAQ_controller object to un the DAQ cards.
        chNum_to_calibrate - The channel number which is attached to the AOM input
        calibration_V_range - A voltage range to calibrate between of the form (V_min, V_max).
        calibration_V_step - The voltage step over between taking calibration measurements. The default is calculated to be
                             equivalent to increasing the digital output on a 4096-bit channel with a -10 to 10V output range.
        writeToQueryDelay - How long to wait between writing a new voltage and querying the frequency counter
        queryToReadDelay - How long to wait between querying the frequency counter and reading the output
                           NOTE: the shortest measurement time on the TF930 is 0.3s
    """

    if calibration_v_step is None:
        calibration_v_step = default_v_step()

    try:
        counter = tf930_manager.TF930(port="COM5")
    except serial.SerialException as err:
        print("Calibration failed - frequency counter could not be found")
        raise err

    # Run through the voltages and record the TF930 output
    v_data, cal_data = [], []
    print("Running through voltages...might take a while...")
    for v in np.arange(
        calibration_v_range[0], calibration_v_range[1] + calibration_v_step, calibration_v_step
    ):
        daq_controller.update_channel_value(ch_num_to_calibrate, v)
        time.sleep(write_to_query_delay)
        v_data.append(v)
        cal_data.append(counter.query("N?", delay=query_to_read_delay))
    print("...finished!")
    # Parse the output, once for units and once for values
    r = r"([\d|\.|e|\+]+)([a-zA-Z]*)\r\n"

    units = ""
    while units == "":
        for i in range(0, len(cal_data)):
            match = re.match(r, cal_data[i])
            if match:
                units = match.group(2)
                break

    parsed_data = []
    n_bad_points = 0
    for i in range(0, len(cal_data)):
        match = re.match(r, cal_data[i])
        if match:
            parsed_data.append(match.group(1))
        else:
            # If there was unexpected output (e.g. when the delays before reading are wrong)
            # then remove the corresponding data point from vData
            n_bad_points += 1
            v_data.pop(i - n_bad_points)

    print(f"Removed {n_bad_points} bad data points")

    # Just a hack to convert Hz to MHz as it's nicer.
    if units == "Hz":
        parsed_data = map(lambda x: float(x) / 10**6, parsed_data)
        units = "MHz"

    return v_data, parsed_data, units


def frequency_timeseries_mx(t_max, write_to_query_delay=0.1, query_to_read_delay=0.3):
    """
    NOT YET FIXED

    Creates a calibration file between the voltage given to an AOM and the frequency output.

    Inputs:
        t_max - Maximal time (in s) for which to measure a frequency,
        writeToQueryDelay - How long to wait between writing a new voltage and querying the frequency counter
        queryToReadDelay - How long to wait between querying the frequency counter and reading the output
                           NOTE: the shortest measurement time on the TF930 is 0.3s
    """

    try:
        counter = tf930_manager.TF930(port="COM5")
    except serial.SerialException as err:
        print("Calibration failed - frequency counter could not be found")
        raise err

    # record the TF930 output
    t_data, cal_data = [], []
    print("Running through the measurements...")
    for t_step in np.arange(0, t_max, write_to_query_delay + query_to_read_delay):
        print(t_step)
        time.sleep(write_to_query_delay)
        t_data.append(t_step)
        cal_data.append(counter.query("N?", delay=query_to_read_delay))
    print("...finished!")
    # Parse the output, once for units and once for values
    r = r"([\d|\.|e|\+]+)([a-zA-Z]*)\r\n"

    units = ""
    while units == "":
        for i in range(0, len(cal_data)):
            match = re.match(r, cal_data[i])
            if match:
                units = match.group(2)
                break

    parsed_data = cal_data
    # parsedData = []
    # nBadPoints = 0
    # for i in range(0, len(calData)):
    #    match = re.match(r, calData[i])
    #    if match:
    #        parsedData.append(match.group(1))
    #    else:
    # If there was unexpected output (e.g. when the delays before reading are wrong)
    # then remove the corresponding data point from vData
    #        nBadPoints += 1
    #        vData.pop(i - nBadPoints)

    # print ('Removed {0} bad data points'.format(nBadPoints))

    # Just a hack to convert Hz to MHz as it's nicer.
    if units == "Hz":
        parsed_data = map(lambda x: float(x) / 10**6, parsed_data)
        units = "MHz"

    return t_data, parsed_data, units


def percentage_power(
    daq_controller,
    ch_num_to_calibrate,
    calibration_v_range=(0, 7),
    calibration_perc_lims=(0, 0.9),
    calibration_v_step=None,
    write_to_query_delay=0.1,
    n_measurement_counts=3,
):
    """
    NOT YET FIXED

    Creates a calibration file between the voltage given to an AOM and percentage of the maximum power output.
    Note that for this to work you will want to check that the maximum power output from the AOM is given at a
    voltage within the calibration_V_range!
    Inputs:
    daq_controller      - a DAQ_controller object to un the DAQ cards.
    chNum_to_calibrate  - The channel number which is attached to the AOM input
    calibration_V_range - A voltage range to calibrate between of the form (V_min, V_max).
    calibration_perc_lims - The percentage power range to allow calibration between.
                            i.e. (0,90) will only give the user access to 0 to 90% of the power.
                            This can be more stable if the calibation if very sensitive at the extreme ranges.
    calibration_V_step  - The voltage step over between taking calibration measurements. The default is calculated to be
                          equivilent to increasing the digital output on a 4096-bit channel with a -10 to 10V output range.
    writeToQueryDelay   - How long to wait between writing a new voltage and querying the frequency counter.
    nMeasurementCounts  - How many measurements to take and average over when reading a value from the power meter
                          (note 1 measurement is about 3ms).
    """
    if calibration_v_step is None:
        calibration_v_step = default_v_step()

    # Find and configure a power meter connected to the computer
    inst, power_meter = get_power_meter()
    configure_power_meter(power_meter, n_measurement_counts=n_measurement_counts)

    # Run through the voltages and record the TF930 output
    v_data, cal_data = [], []
    print("Running through voltages...might take a while...")
    for v in np.arange(
        calibration_v_range[0], calibration_v_range[1] + calibration_v_step, calibration_v_step
    ):
        print(v)
        daq_controller.update_channel_value(ch_num_to_calibrate, v)
        time.sleep(write_to_query_delay)
        v_data.append(v)
        cal_data.append(power_meter.read)
    print("...finished!")

    _, abs_max_index = cal_data.index(min(cal_data)), cal_data.index(max(cal_data))

    cal_data = cal_data[: abs_max_index + 1]

    index_min = min(
        range(len(cal_data)),
        key=lambda i: abs(cal_data[i] - (min(cal_data) + calibration_perc_lims[0] * max(cal_data))),
    )
    index_max = min(
        range(len(cal_data)),
        key=lambda i: abs(cal_data[i] - (max(cal_data) * calibration_perc_lims[1])),
    )

    v_data, cal_data = v_data[index_min : index_max + 1], cal_data[index_min : index_max + 1]

    def normalise(values):
        mi, ma = min(values), max(values)
        ran = ma - mi
        return [(v - mi) / ran for v in values]

    cal_data = [100 * x for x in normalise(cal_data)]

    units = "%"

    if inst is not None:
        inst.close()

    return v_data, cal_data, units


def test_stirap_aom_freq_response(
    level=0.5,
    freqs=None,
    awg_channel=1,
    repeats=3,
    delay=0.2,
):
    """
    Measures the AOM power response as a function of the AWG drive frequency
    at a fixed amplitude level.

    Inputs:
        level (float) - AWG output amplitude in volts.
        freqs (iterable) - Drive frequencies in MHz to sweep over.
        awg_channel (int) - AWG channel that drives the AOM (1-4).
        repeats (int) - How many measurements to average per power meter reading.
        delay (float) - Seconds to wait after enabling the channel before reading.
    """
    if freqs is None:
        freqs = range(60, 90, 1)

    # Convert MHz values to Hz for the AWG
    freqs_hz = [f * 10**6 for f in freqs]

    sample_rate = 1.25 * 10**9

    print("Creating AWG instance")
    awg = awg_manager.AWGManager()
    print("Connecting...")

    for ch in [1, 2, 3, 4]:
        awg.disable_channel(ch)

    awg.set_sample_rate(sample_rate, (1, 2, 3, 4))
    awg.set_continuous(True)

    inst, power_meter = get_power_meter()
    power_meter: ThorlabsPM100 = power_meter
    configure_power_meter(power_meter, n_measurement_counts=repeats)

    cal_data = []

    for freq_mhz, freq_hz in zip(freqs, freqs_hz, strict=True):
        print("freq:", freq_mhz, "MHz")

        awg.play_sine_wave(awg_channel, frequency=freq_hz, amplitude=level)
        awg.enable_channel(awg_channel)
        time.sleep(delay)

        reading = float(power_meter.read)  # type: ignore
        cal_data.append(reading)
        print(f"  power = {reading}")

        awg.disable_channel(awg_channel)

    print("Resetting awg...")
    awg.reset()
    awg.close()

    if inst is not None:
        inst.close()

    fig = plt.figure()
    ax = fig.add_subplot(111)
    fig.subplots_adjust(top=0.85)
    ax.set_title("STIRAP AOM frequency response")
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Power (W)")
    ax.plot(list(freqs), cal_data)
    plt.show()


def finding_amplitude_from_power(
    freqs,
    target_power,
    awg_channel,
    n_steps=20,
    repeats=3,
    delay=0.2,
    calibration_lims=(0, 1),
    save_all=False,
    results_dict=None,
    flip_mirror=True,
):
    """Provides with the value of the voltage amplitude we have to send to the AWG if we want an output
    of the aom with a specific power value.

    Inputs:
        freqs (list) - frequencies at which the awg should drive the aom
        target_power (float) - target power value to achieve
        awg_channel (Channel) - awg channel that drives the aom
        n_steps (int) - number of steps to divide the voltage range into
        repeats (int) - How many measurements to take and average over when reading a value from the power meter
                          (note 1 measurement is about 3ms).
        delay (float) - How long to wait between writing a new voltage and querying the frequency counter
        calibration_lims (tuple) - limits of the calibration
    """
    if flip_mirror:

        def compensate_for_flip(power):
            """Compensate for the power measurement located after the flip mirror rather than
            at the target."""
            df = pd.read_csv(CALIB_CSV)
            if "power_flip" not in df.columns or "power_target" not in df.columns:
                raise ValueError(
                    f"Calibration CSV {CALIB_CSV} does not have the required columns 'power_flip' and 'power_target'."
                )

            x = np.asarray(df["power_flip"].values.astype(float))
            y = np.asarray(df["power_target"].values.astype(float))

            a, b = np.polyfit(x, y, 1)
            # print("Compensating for flip mirror: ", a, b)

            return a * power + b
    else:

        def compensate_for_flip(power):
            return power

    sample_rate = 1.25 * 10**9
    print("Creating AWG instance")
    awg = awg_manager.AWGManager()
    print("Connecting...")
    for i in [1, 2, 3, 4]:
        awg.disable_channel(i)

    awg.set_sample_rate(sample_rate, (1, 2, 3, 4))

    inst, power_meter = get_power_meter()
    power_meter: ThorlabsPM100 = power_meter  # declare the type for easier editing
    configure_power_meter(power_meter, n_measurement_counts=repeats)

    closest_level = None
    closest_diff = float("inf")

    if save_all and results_dict is not None:
        results_dict["level"] = []
        results_dict["read_value"] = []
        results_dict["rabi"] = []

    for freq in freqs:
        level_data = np.linspace(calibration_lims[0], calibration_lims[1], n_steps)
        cal_data = np.empty(n_steps)
        print("Running through awg levels...might take a while...")

        for i, level in enumerate(level_data):
            awg.play_sine_wave(awg_channel, frequency=freq, amplitude=level)
            awg.set_continuous(True)
            awg.enable_channel(awg_channel)
            awg.wait_opc()

            time.sleep(delay)
            raw_value = float(power_meter.read)  # type: ignore
            value = compensate_for_flip(raw_value) if flip_mirror else raw_value
            print(f"{level}V, {value * 1e3}mW (raw value: {raw_value * 1e3}mW)")

            cal_data[i] = value

            awg.disable_channel(awg_channel)

            diff = abs(value - target_power)
            if diff < closest_diff:
                closest_diff = diff
                closest_level = level

            if save_all and results_dict is not None:
                results_dict["level"].append(level)
                results_dict["read_value"].append(value)

        print("...finished taking data")

    print("Resetting awg...")
    awg.reset()
    print("Calibration finished.")
    awg.close()

    if inst is not None:
        inst.close()
    print(f"Closest level found: {closest_level}V with difference: {closest_diff * 10**3}mW")
    return (
        closest_level,
        closest_diff,
        results_dict,
    )  # Return the closest level found if the target power is not achieved
