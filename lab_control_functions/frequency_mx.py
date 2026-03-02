import re
import time

import matplotlib.pyplot as plt
import numpy as np
import serial

from instruments.TF930 import tf930_manager

# from sympy.physics.quantum.circuitplot import matplotlib


def frequency_timeseries_mx(t_max, write_to_query_delay=0.1, query_to_read_delay=0.3):
    """Creates a plot for the time fluctuation the frequency output.
    t_max - Maximal time (in s) for which to measure a frequency,
    writeToQueryDelay - How long to wait between writing a new voltage and querying the frequency counter
    queryToReadDelay - How long to wait between querying the frequency counter and reading the output
                       NOTE: the shortest measurement time on the TF930 is 0.3s"""

    try:
        counter = tf930_manager.TF930(port="COM5")
    except serial.SerialException as err:
        print("Calibration failed - frequency counter could not be found")
        raise err

    # record the TF930 output
    t_data, cal_data = [], []
    print("Running through the measurements...")
    for t_step in np.arange(0, t_max, write_to_query_delay + query_to_read_delay):
        # print t_step
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
            t_data.pop(i - n_bad_points)

    print(f"Removed {n_bad_points} bad data points")

    # Just a hack to convert Hz to MHz as it's nicer.
    if units == "Hz":
        parsed_data = map(lambda x: float(x) / 10**6, parsed_data)
        units = "MHz"

    return t_data, parsed_data, units


def save_calibration_plot(fname, x_data, cal_data, units, title):
    fig = plt.figure()

    ax = fig.add_subplot(111)
    fig.subplots_adjust(top=0.85)
    ax.set_title(title)

    ax.set_xlabel("t")
    ax.set_ylabel(units)

    ax.plot(x_data, cal_data)

    plt.savefig(fname)
    print("saved img: ", fname)


if __name__ == "__main__":
    freq_meas = frequency_timeseries_mx(30 * 60)
    save_calibration_plot(
        "vescent_box_frequ_fluctuations2",
        freq_meas[0],
        freq_meas[1],
        freq_meas[2],
        "Vescent box Frequency Fluctuation2",
    )
