import os
import serial
import time
import numpy as np
import matplotlib.pyplot as plt
import re
from instruments.TF930 import TF930
from typing import Tuple, Optional, Union, List
from classes.Config import ConfigReader, DaqReader


PORT = "COM3"

def get_default_calibration_Vstep():
    '''Returns the smallest resolvable voltage step a 4096 bit digital output corresponding to -10 to 10V can make.
    i.e. the voltage resolution of the DAQ-2502 cards.'''
    f = lambda x: np.interp(x, (0,4095), (-10,10))
    return f(1) - f(0)

def calibrate_frequency(daq_controller, chNum_to_calibrate,
                        calibration_V_range: Tuple[float, float] = (0,10),
                        calibration_V_step: float = None,
                        writeToQueryDelay: float = 0.1,
                        queryToReadDelay: float = 0.3) -> Tuple[List[float], List[float], str]:
    '''Creates a calibration file between the voltage and the frequency output.
        daq_controller - a DAQ_controller object to run the DAQ cards.
        chNum_to_calibrate - The channel number which is attached to the input
        calibration_V_range - A voltage range to calibrate between of the form (V_min, V_max).
        calibration_V_step - The voltage step between taking calibration measurements. If None, uses default resolution.
        writeToQueryDelay - How long to wait between writing a new voltage and querying the frequency counter
        queryToReadDelay - How long to wait between querying the frequency counter and reading the output
                           NOTE: the shortest measurement time on the TF930 is 0.3s'''

    if calibration_V_step is None:
        calibration_V_step = get_default_calibration_Vstep()

    try:
        counter = TF930.TF930(port=PORT)
    except serial.serialutil.SerialException as err:
        print('Calibration failed - frequency counter could not be found')
        raise err

    # Run through the voltages and record the TF930 output
    vData: List[float] = []
    calData: List[str] = []
    print('Running through voltages...might take a while...')
    for v in np.arange(calibration_V_range[0],
                       calibration_V_range[1] + calibration_V_step,
                       calibration_V_step):
        daq_controller.updateChannelValue(chNum_to_calibrate, v)
        time.sleep(writeToQueryDelay)
        vData.append(float(v))
        calData.append(counter.query('N?', delay=queryToReadDelay))
    print('...finished!')

    # Parse the output, once for units and once for values
    r = r'([\d|\.|e|\+|\-]+)([a-zA-Z]*)\r\n'  # allow negative sign just in case

    # Find units from first parsable line
    # group 1 is the value, group 2 is the unit
    units = ''
    for s in calData:
        match = re.match(r, s)
        if match:
            units = match.group(2) 
            break

    parsedData: List[float] = []
    nBadPoints = 0
    # iterate with index to remove matching vData entries when a read fails
    # remove the data which is not in the frequency format or cannot be converted to float
    for i in range(0, len(calData)):
        match = re.match(r, calData[i])
        if match:
            # numeric string in group(1) — convert to float now
            try:
                parsedData.append(float(match.group(1)))
            except ValueError:
                # If conversion fails, treat as bad point and remove voltage
                nBadPoints += 1
                vData.pop(i - nBadPoints)
        else:
            # unexpected output -> remove corresponding voltage
            nBadPoints += 1
            vData.pop(i - nBadPoints)

    print('Removed {0} bad data points'.format(nBadPoints))

    # Convert Hz -> MHz for nicer numbers, if needed
    if units == 'Hz':
        parsedData = [x / 10**6 for x in parsedData]
        units = 'MHz'

    # ensure lists are same length and sorted in the same order (voltage order preserved)
    assert len(vData) == len(parsedData), "vData and parsedData lengths differ after parsing."

    return vData, parsedData, units


# --- Helper: find voltage for a target frequency ---
_unit_factors = {
    'hz': 1.0,
    'khz': 1e3,
    'mhz': 1e6,
    'ghz': 1e9
}

def _normalize_unit(u: Optional[str]) -> Optional[str]:
    if u is None:
        return None
    return u.strip().lower()

def _convert_value_between_units(value, from_unit: Optional[str], to_unit: Optional[str]):
    """Convert numeric value or numpy array from from_unit -> to_unit."""
    if from_unit is None or to_unit is None:
        return value
    fu = _normalize_unit(from_unit)
    tu = _normalize_unit(to_unit)
    if fu not in _unit_factors or tu not in _unit_factors:
        raise ValueError(f"Unknown unit(s): {from_unit}, {to_unit}")
    return value * (_unit_factors[fu] / _unit_factors[tu])


def find_voltage_for_frequency(
    vData: List[float],
    parsedData: List[float],
    target_frequency: Union[float, str],
    parsed_units: str = 'MHz',
    target_units: Optional[str] = None
    # method: str = 'interp'
) -> dict:
    """
    Find the voltage that gives a frequency closest to target_frequency.

    Arguments:
      vData            : list/array of voltages from calibrate_frequency (floats)
      parsedData       : list/array of frequency readings (floats)
      target_frequency : numeric or string like '80 MHz' or (80.0)
      parsed_units     : unit string for parsedData (default returned units from calibrate_frequency)
      target_units     : optional unit for target_frequency (if None, will use parsed_units)
      method           : 'interp' (windowed average + global minimum) or 'closest' (choose measured point)

    Returns:
      dict with keys:
        - 'voltage' : suggested voltage (float)
        - 'expected_frequency' : frequency (float) in parsed_units (closest/interpolated/averaged)
        - 'error' : absolute difference (same units)
        - 'method' : method used
        - 'note' : warnings (e.g., extrapolated or fallback)
    """
    # parse target_frequency if a string like "80 MHz"
    if isinstance(target_frequency, str):
        parts = target_frequency.strip().split()
        if len(parts) == 1:
            target_value = float(parts[0])
            target_units_parsed = None
        elif len(parts) == 2:
            target_value = float(parts[0])
            target_units_parsed = parts[1]
        else:
            raise ValueError("target_frequency string must be like '80 MHz' or '80.0'")
    else:
        target_value = float(target_frequency)
        target_units_parsed = None

    # determine final target unit
    if target_units is None:
        target_units = target_units_parsed if target_units_parsed is not None else parsed_units

    # make numpy arrays of floats
    volts = np.array(vData, dtype=float)
    freqs = np.array(parsedData, dtype=float)

    # convert target_value to parsed_units
    target_in_parsed_units = _convert_value_between_units(target_value, target_units, parsed_units)

    note = ''
    # method = method.lower()
    # if method not in ('interp', 'closest'):
    #     raise ValueError("method must be 'interp' or 'closest'")

    # sort by frequency (for freq -> volt interpolation if needed)
    sort_idx = np.argsort(freqs)
    freqs_sorted = freqs[sort_idx]
    volts_sorted = volts[sort_idx]

    # # check if target is outside measured range (informational)
    # f_min = freqs_sorted[0]
    # f_max = freqs_sorted[-1]
    # if target_in_parsed_units < f_min or target_in_parsed_units > f_max:
    #     note += (f"Target {target_in_parsed_units} {parsed_units} is outside measured range "
    #              f"[{f_min}, {f_max}]. Result may require extrapolation (less reliable). ")

    # if method == 'closest':
    #     idx = int(np.argmin(np.abs(freqs - target_in_parsed_units)))
    #     chosen_voltage = float(volts[idx])
    #     achieved_freq = float(freqs[idx])
    #     error = abs(achieved_freq - target_in_parsed_units)
    #     return {
    #         'voltage': chosen_voltage,
    #         'expected_frequency': achieved_freq,
    #         'error': error,
    #         'method': 'closest',
    #         'note': note
    #     }

    # -------------------------
    # NEW: method == 'interp'
    # Use moving-window averaging (5 before + centre + 5 after => window size = 11)
    # -------------------------
    window_half = 5
    window_size = 2 * window_half + 1

    if len(freqs) < window_size:
        # Not enough points for windowed averaging — fallback to original interpolation approach
        note += (f"Not enough samples for {window_size}-point averaging (have {len(freqs)}). "
                 "Falling back to interpolation/nearest behavior. ")
        # Fallback: use the previous interpolation logic (voltage as function of frequency)
        try:
            chosen_voltage = float(np.interp(target_in_parsed_units, freqs_sorted, volts_sorted))
        except Exception:
            # As a last resort pick the closest-measured point
            idx = int(np.argmin(np.abs(freqs - target_in_parsed_units)))
            chosen_voltage = float(volts[idx])

        # predict achieved frequency back at chosen_voltage
        v_sort_idx = np.argsort(volts_sorted)
        volts_for_back = volts_sorted[v_sort_idx]
        freqs_for_back = freqs_sorted[v_sort_idx]
        if np.any(np.diff(volts_for_back) == 0):
            nearest_idx = int(np.argmin(np.abs(volts - chosen_voltage)))
            achieved_freq = float(freqs[nearest_idx])
        else:
            achieved_freq = float(np.interp(chosen_voltage, volts_for_back, freqs_for_back))

        error = abs(achieved_freq - target_in_parsed_units)

        # --- PLOTTING SECTION (fallback case) ---
        try:
            plt.figure(figsize=(8,5))
            plt.plot(volts, freqs, '.', markersize=4, alpha=0.6, label='measured')
            # no full window_avgs available here; just mark the chosen voltage and target
            plt.axhline(target_in_parsed_units, color='k', linestyle='--', label=f'target {target_in_parsed_units} {parsed_units}')
            plt.axvline(chosen_voltage, color='r', linestyle='-.', label=f'chosen V={chosen_voltage:.3f} V')
            plt.scatter([chosen_voltage], [achieved_freq], s=80, edgecolors='r', facecolors='none')
            plt.xlabel('Voltage (V)')
            plt.ylabel(f'Frequency ({parsed_units})')
            plt.title(f'Freq vs Voltage — target {target_in_parsed_units} {parsed_units} (interp_fallback)')
            plt.legend(loc='best')
            plt.grid(True)
            plt.show()
        except Exception:
            pass

        return {
            'voltage': chosen_voltage,
            'expected_frequency': achieved_freq,
            'error': error,
            'method': 'interp_fallback',
            'note': note
        }

    # Compute windowed averages centered at each valid central index
    # Valid centers: indices [window_half, len(freqs)-window_half-1]
    centers = np.arange(window_half, len(freqs) - window_half)
    window_avgs = np.empty(len(centers), dtype=float)
    for j, center in enumerate(centers):
        window = freqs[center - window_half : center + window_half + 1]
        window_avgs[j] = np.mean(window)

    # Compute absolute difference between averaged window and target
    diffs = np.abs(window_avgs - target_in_parsed_units)

    # Find global minimum (not local peaks)
    min_idx_in_centers = int(np.argmin(diffs))
    chosen_center = int(centers[min_idx_in_centers])

    chosen_voltage = float(volts[chosen_center])
    achieved_freq = float(window_avgs[min_idx_in_centers])
    error = abs(achieved_freq - target_in_parsed_units)

    # --- PLOTTING SECTION ---
    try:
        plt.figure(figsize=(9,6))
        # raw measured points
        plt.plot(volts, freqs, '.', markersize=4, alpha=0.5, label='measured')
        # moving-window averages (aligned to center voltages)
        plt.plot(volts[centers], window_avgs, '-', linewidth=2, alpha=0.9, label=f'{window_size}-pt moving avg')
        # mark spikes/outliers by comparing raw to window (optional visual cue)
        residuals = freqs[centers] - window_avgs
        outlier_mask = np.abs(residuals) > (np.std(residuals) * 3)
        if outlier_mask.any():
            plt.plot(volts[centers][outlier_mask], freqs[centers][outlier_mask], 'x', color='red', label='large residuals')

        # horizontal line for the target frequency
        plt.axhline(target_in_parsed_units, color='k', linestyle='--', label=f'target {target_in_parsed_units} {parsed_units}')
        # vertical line and marker for chosen voltage
        plt.axvline(chosen_voltage, color='r', linestyle='-.', label=f'chosen V={chosen_voltage:.3f} V')
        plt.scatter([chosen_voltage], [achieved_freq], s=100, edgecolors='r', facecolors='none', zorder=5)

        # annotate the chosen point with the achieved frequency and error
        plt.annotate(f'{achieved_freq:.4f} {parsed_units}\\nΔ={error:.4f} {parsed_units}',
                     xy=(chosen_voltage, achieved_freq),
                     xytext=(10, 10),
                     textcoords='offset points',
                     bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.8),
                     arrowprops=dict(arrowstyle='->', connectionstyle='arc3'))

        plt.xlabel('Voltage (V)')
        plt.ylabel(f'Frequency ({parsed_units})')
        plt.title(f'Frequency vs Voltage — target {target_in_parsed_units} {parsed_units} (window_avg_{window_size})')
        plt.legend(loc='best')
        plt.grid(True)
        plt.show()
    except Exception:
        # plotting must not break the function if matplotlib fails for any reason
        pass

    return {
        'voltage': chosen_voltage,
        'expected_frequency': achieved_freq,
        'error': error,
        'method': 'window_avg_11',
        'note': note
    }



# -----------------------
# main program (example)
# -----------------------

# TODO: create your DAQ controller here. Example placeholder:
# from my_daq_module import DAQController
# daq_controller = DAQController(config_path="cold-control/configs/daq/daq_config_may25.ini")
#
# The calibrate_frequency function expects an object with a method:
#   updateChannelValue(channel_number, voltage)
#
# Replace the following placeholder with your actual DAQ controller instance:

config_reader = ConfigReader(os.getcwd() + 'configs/daq/daq_config_may25.ini"')
daq_config_fname = config_reader.get_daq_config_fname()
daq_controller = DaqReader(daq_config_fname).load_DAQ_controller()

daq_controller = None  # <-- REPLACE this with your DAQ controller object (see TODO above)

if daq_controller is None:
    raise RuntimeError("Please construct your daq_controller object and assign it to 'daq_controller' before running.")

# Run calibration for channel 21 and -5..+5 V
vData, parsedData, units = calibrate_frequency(
    daq_controller,
    chNum_to_calibrate=21,
    calibration_V_range=(-5, 5)
)

# Example: find the voltage to get closest to 80 MHz
target = "80 MHz"
result = find_voltage_for_frequency(vData, parsedData, target, parsed_units=units, method='interp')
print("Suggested voltage:", result['voltage'])
print("Expected frequency ({}):".format(units), result['expected_frequency'])
print("Error ({}):".format(units), result['error'])
print("Note:", result['note'])



