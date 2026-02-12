'''
Optimization of the input signal using NLMS adaptive filter in an inverted approach.
Also includes at the end the power calibration (optional).

@author: Marina Llano
'''

import os
import time
import datetime
import ast
from instruments.WX218x.WX218x_awg import Channel
import lab_control_functions.calibration_functions as calibrate
import numpy as np
from scipy.constants import c, epsilon_0, hbar
import padasip as pa
import numpy as np
import pandas as pd
import matplotlib.pylab as plt
from scipy.interpolate import interp1d
import csv
import pyvisa as visa
import oscilloscope_manager as osc
from classes.ExperimentalConfigs import PhotonProductionConfiguration, AwgConfiguration, TdcConfiguration, Waveform
from cold_control_files.awg_control_functions import run_awg
from cold_control_files.awg_control_functions_single import run_awg_single
from configobj import ConfigObj        
from sklearn.metrics import mean_squared_error

plt.rcParams.update({
    'text.usetex': True,
    'text.latex.preamble': r'\usepackage{amsmath}',
    'font.family': 'serif',
    'font.size': 12,
    'axes.labelsize': 14,
    'axes.titlesize': 15,
    'legend.fontsize': 12,
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'axes.linewidth': 1.1,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'xtick.major.size': 5,
    'ytick.major.size': 5,
})


# general coefficients
gamma_d1 = 5.746*np.pi
gamma_d2= 6*np.pi
typical_waist_size=20 #mu m
d_d1 = 2.537 * 10**(-29)
d_d2= 2.853 * 10**(-29) 

# V-STIRAP re-preparation coefficients
cg_d2_stokes = np.sqrt(1/30)
cg_d2_pump = -np.sqrt(5/24)
rabi_stirap_d1 = 41*2*np.pi 
rabi_stirap_d2 = 49*2*np.pi 

# OPT PUMPING coefficients
cg_d2_p1 = np.sqrt(1/24)
cg_d2_p2 = np.sqrt(1/8)
rabi_p1_d1 = 34*2*np.pi 
rabi_p1_d2 = 57.5*2*np.pi 
rabi_p2_d1 = 24*2*np.pi 
rabi_p2_d2 = 25.5*2*np.pi 

today = datetime.datetime.now().strftime("%d-%m")

def rabi_to_laserpower(omega, d, cg, beam_waist):
    """
    Convert Rabi frequency to laser power
    Input agrs:
    omega: Rabi frequency in MHz
    d: dipole moment in C*m
    cg: angular CG dependence
    beam_waist: beam waist in micron"""

    efield=(hbar*(omega*10**6))/(d*cg)
    intensity=(efield**2*epsilon_0*c)/(2)
    return (intensity*np.pi*(beam_waist*10**(-6))**2)*10**(3) # in mW

def laserpower_to_rabi(power, d, cg, beam_waist):
    """
    Convert laser power to Rabi frequency
    Input agrs:
    power: power in mW
    d: dipole moment in C*m
    cg: angular CG dependence
    beam_waist: beam waist in micron"""

    intensity=power/(np.pi*(beam_waist*10**(-6))**2*10**3)
    efield=np.sqrt((2*intensity)/(epsilon_0*c))
    omega=(d*cg*efield)/(hbar*10**6)
    return omega #in MHz

class PositiveNLMS(pa.filters.FilterNLMS):
    def run(self, d, X):
        """ Ejecuta el filtro NLMS con restricción de valores positivos. """
        n = len(d)
        y = np.zeros(n)
        e = np.zeros(n)
        w = np.zeros((n, self.n))
        for k in range(n):

            y[k] = np.dot(self.w, X[k])
            e[k] = d[k] - y[k]
            self.w += self.mu * e[k] * X[k] / (self.eps + np.dot(X[k], X[k]))
            # self.w = np.abs(self.w) # negative values turn positive
            self.w = np.maximum(self.w, 0) # negative values go to 0
            w[k] = self.w
        return y, e, w
    
def plot_checking(measured_signal, std, teor_signal, len_awg, window, amplitude, pulse): 
    """Plots the mean signal measured on the scope with respect to the theoretical signal.
       Use to check if they are well alligned/progress in the optimization. """

    max_value = min(measured_signal['Voltage (V)'].max(), teor_signal.max())
    measured_signal['Voltage (V)'] = measured_signal['Voltage (V)'] / measured_signal['Voltage (V)'].max() * max_value
    teor_signal = teor_signal / teor_signal.max() * max_value
    # no cal normalitzar la std pq estem agafant el minim crec ns mirarho

    plt.figure(figsize=(10, 6))
    plt.plot(measured_signal['Time (s)'], measured_signal['Voltage (V)'], linewidth=1.5, label='Mean Amplitude', color='blue')
    plt.fill_between(
        measured_signal['Time (s)'], 
        measured_signal['Voltage (V)'] - std['Voltage (V)'],  # mean - std
        measured_signal['Voltage (V)'] + std['Voltage (V)'],  # mean + std
        color='blue',  
        alpha=0.3,  
        label='Standard Deviation'  
    )
    plt.plot(np.linspace(0, len_awg * 1e-9, len(teor_signal)), teor_signal, linewidth=1.5, linestyle='--', color='red', label='Theoretical Signal')
    plt.xlabel(r'Time (s)')
    plt.ylabel(r'Amplitude (a.u)')
    plt.title(f'Mean Amplitude (Window {window})', fontsize=15)
    plt.legend(loc='best')
    plt.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)
    

    output_dir = f'c:\\Users\\apc\\Documents\\marina\\05_may\\{today}\\{amplitude}\\{pulse}'
    os.makedirs(output_dir, exist_ok=True)
    plot_filename = os.path.join(output_dir, f'mean_voltage_window_{window}.png')
    plt.savefig(plot_filename)
    print(f'Plot saved as {plot_filename}')

    plt.show(block=False)
    plt.pause(2)
    plt.close()
    # plt.show()
    # plt.close()

def filter_plots(len_awg, d, x, d_adjusted, y, e, window, y_pred_optimized, pulse, output_dir, savefig = False):
    plt.figure(figsize=(10, 6))
    plt.plot(np.linspace(0, len_awg * 1e-9, len(d), endpoint=False), d, "b", label="Theoretical Signal Sent")
    plt.plot(np.linspace(0, len_awg * 1e-9, len(x), endpoint=False), x, "g", label="Data Scope Mean Amplitude")
    plt.xlabel(r"Time (s)")
    plt.ylabel(r"Amplitude (a.u)")
    plt.title("Mean Signal Measured vs Desired Signal")
    plt.legend(loc="best")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    if savefig:
        plot_filename = os.path.join(output_dir, f"mean_vs_desired_window_{window}.png")
        plt.savefig(plot_filename, dpi=300, bbox_inches="tight")
        print(f"Plot saved as {plot_filename}")
    # plt.show()
    # plt.close()
    plt.show(block=False)
    plt.pause(1)
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.subplot(211)
    plt.title(f"Adaptation {pulse}, Window {window}")
    plt.xlabel(r"Time (s)")
    plt.ylabel(r"Amplitude (a.u)")
    plt.plot(np.linspace(0, len_awg * 1e-9, len(d_adjusted), endpoint=False), d_adjusted, "b", label="d - Target")
    plt.plot(np.linspace(0, len_awg * 1e-9, len(y), endpoint=False), y, "g", label="y - Output")
    plt.legend(loc="best")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

    plt.subplot(212)
    plt.title("Filter Error")
    plt.xlabel("Samples - k")
    plt.ylabel("Error (dB)")
    plt.plot(10 * np.log10(e**2), "r", label="e - Error [dB]")
    plt.legend(loc="best")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    plt.tight_layout()
    if savefig:
        plot_filename = os.path.join(output_dir, f"adaptation_window_{window}.png")
        plt.savefig(plot_filename, dpi=300, bbox_inches="tight")
        print(f"Plot saved as {plot_filename}")
    # plt.show()
    # plt.close()
    plt.show(block=False)
    plt.pause(1)
    plt.close()


    plt.figure(figsize=(10, 6))
    plt.subplot(211)
    plt.title(f"Prediction {pulse}, Window {window}")
    plt.xlabel(r"Time (s)")
    plt.ylabel(r"Amplitude (a.u)")
    plt.plot(np.linspace(0, len_awg * 1e-9, len(d_adjusted), endpoint=False), d_adjusted, "b", label="Theoretical Output")
    plt.plot(np.linspace(0, len_awg * 1e-9, len(y_pred_optimized), endpoint=False), y_pred_optimized, "g", label="x Optimized - Input to Obtain Theoretical")
    plt.legend(loc="best")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

    plt.subplot(212)
    plt.title("Filter Error")
    plt.xlabel("Samples - k")
    plt.ylabel("Error (dB)")
    plt.plot(10 * np.log10(e**2), "r", label="e - Error [dB]")
    plt.legend(loc="best")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    plt.tight_layout()
    if savefig:
        plot_filename = os.path.join(output_dir, f"prediction_window_{window}.png")
        plt.savefig(plot_filename, dpi=300, bbox_inches="tight")
        print(f"Plot saved as {plot_filename}")
    # plt.show()
    # plt.close()
    plt.show(block=False)
    plt.pause(1)
    plt.close()


def theor_signal(amplitude, pulse, len_signal, len_awg):
    """ Recovers the theoretical signal. Interpolation so we can compare with the mean signal measured. """

    if pulse == 'stokes':

        file_path = r'c:\Users\apc\Documents\marina\stokes_150ns_20.csv'   # PULSE 1

        # file_path = r'c:\Users\apc\Documents\marina\04_apr\PULSES 2\stokes\stokes_125ns_0.2.csv'  # PULSE 2

        # file_path = r'c:\Users\apc\Documents\marina\04_apr\PULSES 3\stokes\stokes_125ns_0.2.csv'  # PULSE 3
        # file_path = r'c:\Users\apc\Documents\marina\random_wf\random1.csv' # Random 


    elif pulse == 'pump':

        file_path = f'data/2025-01-31/pump_150ns_20.csv'  # PULSE 1

        # file_path = r'c:\Users\apc\Documents\marina\04_apr\PULSES 2\pump\pump_125ns_0.2.csv'  # PULSE 2

        # file_path = r'c:\Users\apc\Documents\marina\04_apr\PULSES 3\pump\pump_125ns_0.1.csv'  # PULSE 3

        # file_path = r'c:\Users\apc\Documents\marina\random_wf\random4.csv' # Random 

    elif pulse == 'P1': 
        file_path = r'c:\Users\apc\Documents\marina\flatg_20_ch3_3000.csv'

    elif pulse == 'P2': 
        file_path = r'c:\Users\apc\Documents\marina\flatg_20_ch4_3000.csv'


    d = pd.read_csv(file_path, header=None)
    d = d.T.to_numpy().flatten()

    # re-normalize to the amplitude we want
    d = d/d.max()*amplitude  # 1ns resolution, to send to the awg
    
    t_original = np.linspace(0, len_awg*10**(-9), len(d), endpoint=True)
    t_interpolated = np.linspace(0, len_awg*10**(-9), len_signal, endpoint=True)  
    interpolator = interp1d(t_original, d, kind='cubic', fill_value="extrapolate")
    d_interpolated = interpolator(t_interpolated)
    d_interpolated = d_interpolated.T.flatten()  # to compute error between th and data

    return d, d_interpolated, t_interpolated 


def find_best_mu(window, d_adjusted, X):
    """ Finds the best value of mu of the NLMS filter. """
    mu_values = np.linspace(0.1, 1.9, 20)  
    best_mu = mu_values[0]
    best_error = float('inf')
    
    for mu in mu_values:
        filt = pa.filters.FilterNLMS(window, mu=mu)
        y, e, w = filt.run(d_adjusted, X)
        error = mean_squared_error(d_adjusted, y)
        
        if error < best_error:
            best_error = error
            best_mu = mu
    
    return best_mu, best_error

def to_bool(string):
    return string.lower() in ['true', 't', 'yes', 'y']

def setup_awg(config, config_single):
    """ Configures the AWG. """
    awg_config = AwgConfiguration(sample_rate = float(config['AWG']['sample rate']),
                                    burst_count = int(config['AWG']['burst count']),
                                    waveform_output_channels = list(config['AWG']['waveform output channels']),
                                    waveform_output_channel_lags = map(float, config['AWG']['waveform output channel lags']),  # Retrasos asociados a los canales de salida.
                                    marked_channels = list(config['AWG']['marked channels']),
                                    marker_width = eval(config['AWG']['marker width']),
                                    waveform_aom_calibrations_locations = list(config['AWG']['waveform aom calibrations locations']))
    
    # Same as above but for the tdc
    tdc_config = TdcConfiguration(counter_channels = map(eval, config['TDC']['counter channels']),
                                    marker_channel = int(config['TDC']['marker channel']),
                                    timestamp_buffer_size = int(config['TDC']['timestamp buffer size'])) # Tamaño del búfer para almacenar marcas de tiempo.
    
    # Reads the waveforms from the config object, and creates a list of Waveforms with those properties
    waveforms = []
    for x,v in config['waveforms'].items():
        if v['phases']: 
            if isinstance(v['phases'], list):
                phases_str = ', '.join([str(phase) for phase in v['phases']])
            else:
                phases_str = v['phases']
            
            phases = ast.literal_eval(phases_str)
        else:
            phases = []
        # Channel 1 is Double Pass
        if int(x) == 1:
            phases = [(phase[0] / 2, phase[1]) for phase in phases]  
            
        waveforms.append(Waveform(fname = v['filename'],
                                    mod_frequency= float(v['modulation frequency']),
                                    phases = phases)) # map(float, v['phases']))) 
        

    # Sets the general settings for the whole process as a photon production configuration
    photon_production_config = PhotonProductionConfiguration(save_location = config['save location'],
                                                                mot_reload  = eval(config['mot reload']),
                                                                iterations = int(config['iterations']),
                                                                waveform_sequence = list(eval(config['waveform sequence'])),
                                                                waveforms = waveforms,
                                                                waveform_stitch_delays = list(eval(config['waveform stitch delays'])), #  Retrasos entre formas de onda.
                                                                interleave_waveforms = to_bool(config['interleave waveforms']),  # Indica si las formas de onda deben intercalarse.
                                                                awg_configuration = awg_config,
                                                                tdc_configuration = tdc_config)
    

    # Calls the configure_awg function with the values extracted from the config object
    # This function used to be called "configure_awg"
     

    awg_config_single = AwgConfiguration(sample_rate = float(config_single['AWG']['sample rate']),
                                         burst_count = int(config_single['AWG']['burst count']),
                                         waveform_output_channels = list(config_single['AWG']['waveform output channels']),
                                         waveform_output_channel_lags = map(float, config_single['AWG']['waveform output channel lags']),
                                         marked_channels = list(config_single['AWG']['marked channels']),
                                         marker_width = eval(config_single['AWG']['marker width']),
                                         waveform_aom_calibrations_locations = list(config_single['AWG']['waveform aom calibrations locations']))

    tdc_config_single = TdcConfiguration(counter_channels = map(eval, config_single['TDC']['counter channels']),
                                         marker_channel = int(config_single['TDC']['marker channel']),
                                         timestamp_buffer_size = int(config_single['TDC']['timestamp buffer size']))

    waveforms_single = []
    for x,v in config_single['waveforms'].items():
        waveforms_single.append(Waveform(fname = v['filename'],
                                         mod_frequency= float(v['modulation frequency']),
                                         phases=map(float, v['phases'])))

    photon_production_config_single = PhotonProductionConfiguration(save_location = config_single['save location'],
                                                                    mot_reload  = eval(config_single['mot reload']),
                                                                    iterations = int(config_single['iterations']),
                                                                    waveform_sequence = list(eval(config_single['waveform sequence'])),
                                                                    waveforms = waveforms_single,
                                                                    waveform_stitch_delays = list(eval(config_single['waveform stitch delays'])),
                                                                    interleave_waveforms = to_bool(config_single['interleave waveforms']),
                                                                    awg_configuration = awg_config_single,
                                                                    tdc_configuration = tdc_config_single)

    return awg_config, photon_production_config, awg_config_single, photon_production_config_single

def measure_signal(osc_manager, d, t_interpolated, channel_osc, channel, len, num_measurements=50, samp_rate=1e9, timebase_range=4e-6, window=0, delay=0, cut=0e-9, save_file=False, centered_0=False):
    """ Performs measurements using the oscilloscope and returns the mean acquired signal. 
    Cuts measured signal by aligning its peak with the theoretical peak (if the theoretical signal is more complex this can be unaccurate, you can use detect_signal_start).
    
    - delay (float) : time in s to delay detected signal start if it is not accurate
    - window (string/float) : name of the file being saved
    - cut (float) : cutting time to focus on the pulse, doesn't have to be accurate
    - len (float) : in ns, the length of the signal 
    - d and t_interpolated : theoretical signal to compare to
    - centered_0 (bool) : center measurements on 0 (if we want negative time values)

    """
    all_measurements = [] 
    for _ in range(num_measurements):

        data = osc_manager.acquire_with_trigger(channel_osc, samp_rate=samp_rate, timebase_range=timebase_range, window=window, save_file=save_file, centered_0=centered_0)        
        all_measurements.append(data)
        time.sleep(0.2) 
    
    measurements = pd.DataFrame()

    for i, data in enumerate(all_measurements):
        measurements[f'Time (s) {i}'] = data['Time (s)']
        measurements[f'Voltage (V) {i}'] = data['Voltage (V)']

    voltages = measurements.filter(like='Voltage (V)')
    voltages -= voltages.min().min()     
    sqrt_volt = np.sqrt(voltages.clip(lower=0))
 
    if channel == 1 or channel == 2:  
        # First cut to focus on the peak we are analysing (doesn't have to be exact or 150ns long)                                                              
        measurements = measurements[(measurements.filter(like='Time (s)').iloc[:, 0] >= cut)].copy()
        sqrt_volt = sqrt_volt.loc[measurements.index]   

        min_value = sqrt_volt.mean(axis=1).max()
        d = d / d.max() * min_value     

        # We allign the theoretical and measured peaks 
        index_peak_theoretical = np.argmax(d)
        index_peak_measured = np.argmax(sqrt_volt.mean(axis=1))
        time_shift = measurements.filter(like='Time (s)').iloc[index_peak_measured, 0] - t_interpolated[index_peak_theoretical]

        measurements.loc[:, measurements.filter(like='Time (s)').columns] -= time_shift

        index_start_theoretical = np.where(d> 0)[0][0] 
        start_time_theoretical = t_interpolated[index_start_theoretical]
        
        start_time_measured = start_time_theoretical + delay
        end_time_measured = start_time_measured + len*1e-9   
        
        measurements = measurements[(measurements.filter(like='Time (s)').iloc[:, 0] >= start_time_measured) &
                                    (measurements.filter(like='Time (s)').iloc[:, 0] <= end_time_measured)].copy()
        sqrt_volt = sqrt_volt.loc[measurements.index] 
        sqrt_volt -= sqrt_volt.iloc[0]   
        
        measurements.loc[:, measurements.filter(like='Time (s)').columns] -= start_time_measured

    elif channel == 3 or channel == 4:                                                               
            measurements = measurements[(measurements.filter(like='Time (s)').iloc[:, 0] >= 0.2e-6) & (measurements.filter(like='Time (s)').iloc[:, 0] <= 3.5e-6)].copy()
            sqrt_volt = sqrt_volt.loc[measurements.index]  

    mean_time = measurements.filter(like='Time (s)').mean(axis=1)
    mean_voltage = sqrt_volt.mean(axis=1)
    std_voltage =sqrt_volt.std(axis=1)

    mean_data = pd.DataFrame({'Time (s)': mean_time,'Voltage (V)': mean_voltage})
    std_data = pd.DataFrame({'Time (s)': mean_time, 'Voltage (V)': std_voltage}) 

 
    if channel == 3 or channel == 4:
        start_time, start_index = detect_signal_start(mean_data['Time (s)'], mean_data['Voltage (V)'], threshold=0.01, min_duration=0.01e-6, start_point=0.2e-6)
        mean_data['Time (s)'] -= start_time - 30e-9   
        mean_data = mean_data[(mean_data['Time (s)'] >= 0) & (mean_data['Time (s)'] <= 3120e-9)].copy()
        std_data = std_data.loc[mean_data.index] 

    return mean_data, std_data

def detect_signal_start(time, voltage, min_duration=0.1e-6, start_point=0, smooth=True, window_size=40):
    """Detects the start of a signal based on continuous growth of amplitude over a minimum duration."""
    def smooth_signal(voltage, window_size):
            """Applies a moving average filter to smooth the signal."""
            return np.convolve(voltage, np.ones(window_size) / window_size, mode='same')
       
    valid_indices = time >= start_point
    time = time[valid_indices].reset_index(drop=True)
    voltage = voltage[valid_indices].reset_index(drop=True)

    if smooth:
        voltage = smooth_signal(voltage, window_size=window_size)

    for start_index in range(len(voltage)):
        end_index = start_index
        while end_index < len(voltage) - 1 and voltage[end_index + 1] > voltage[end_index]:
            end_index += 1

        duration = time[end_index] - time[start_index]
        if duration >= min_duration:
            start_time = time[start_index]
            return start_time, start_index

    raise ValueError("No start point detected with the given criteria.")

def plot_3(measured_signal, mean_signal, std, std0, teor_signal, len_awg, window, amplitude, pulse): 

    max_value = min(measured_signal['Voltage (V)'].max(), teor_signal.max())
    measured_signal['Voltage (V)'] = measured_signal['Voltage (V)'] / measured_signal['Voltage (V)'].max() * max_value
    teor_signal = teor_signal / teor_signal.max() * max_value

    plt.figure(figsize=(10, 6))

    plt.plot(measured_signal['Time (s)'], measured_signal['Voltage (V)'], linewidth=1.5, label='Optimized signal', color='blue')
    plt.fill_between(
        measured_signal['Time (s)'], 
        measured_signal['Voltage (V)'] - std['Voltage (V)'],  # mean - std
        measured_signal['Voltage (V)'] + std['Voltage (V)'],  # mean + std
        color='blue',  
        alpha=0.1,  
    )
    plt.plot(mean_signal['Time (s)'], mean_signal['Voltage (V)'], linewidth=1.5, label='Non-Optimized signal', color='green')
    plt.fill_between(
        mean_signal['Time (s)'], 
        mean_signal['Voltage (V)'] - std0['Voltage (V)'],  # mean - std
        mean_signal['Voltage (V)'] + std0['Voltage (V)'],  # mean + std
        color='green',  
        alpha=0.1,  
    )
    plt.plot(np.linspace(0, len_awg * 1e-9, len(teor_signal)), teor_signal, linewidth=1.5, linestyle='--', color='red', label='Theoretical Signal')

    plt.xlabel(r'Time (s)')
    plt.ylabel(r'Amplitude (a.u)')
    plt.title(f'Mean Amplitude (Window {window})', fontsize=15)
    plt.legend(loc='best')
    plt.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

    output_dir = f'c:\\Users\\apc\\Documents\\marina\\05_may\\{today}\\{amplitude}\\{pulse}'
    os.makedirs(output_dir, exist_ok=True)
    plot_filename = os.path.join(output_dir, f'three_ampl_window_{window}.png')
    plt.savefig(plot_filename)
    print(f'Plot saved as {plot_filename}')

    plt.show(block=False)
    plt.pause(2)
    plt.close()


#######################################################################################################
'''
    Things to check before starting code:
    - AWG channel and pulse are correct (channel, pulse)
    - SCOPE channel is correct (channel_osc)
    - Trigger is set on the scope (to whatever channel you want, you can use awg marker)
    - Check that the theoretical shape used is correct (function theor_signal)
    - len_awg is correct (has to correspond to the signal's length in ns)
    - Check measure_signal function inputs (timebase_range, samp_rate, centered_0, delay, cut)
    - output_dir
'''
#######################################################################################################

# AWG channel we are working with:
# 1: Stirap Eylsa, stokes laser 
# 2: Stirap DLPro, pump laser
# 3: Opt Pumping Eylsa, P1 laser
# 4: Opt Pumping DLPro, P2 laser
channel = 2

# Pulse shape we are working with: 'stokes', 'pump' (useful for naming files)
if channel == 1 :
    pulse = 'stokes'
if channel == 2 : 
    pulse = 'pump'
if channel == 3 :
    pulse = 'P1'
if channel == 4 :
    pulse = 'P2'


amplitude = 0.2

# Finding the input needed to have optimal output
path_to_config = r'c:\Users\apc\Documents\marina\awg_tests\newPhotonProductionConfignewexp' 
path_to_config_single = r'c:\Users\apc\Documents\marina\awg_tests\newPhotonProductionConfigCH4newexp'
config = ConfigObj(path_to_config)
config_single = ConfigObj(path_to_config_single)  
rm = visa.ResourceManager('@py')
osc_manager = osc.oscilloscope_manager()


# We start by sending the theoretical signal to the awg
# we change the waveform in config
output_dir = f'c:\\Users\\apc\\Documents\\marina\\05_may\\{today}'
os.makedirs(output_dir, exist_ok=True)

if pulse == 'stokes' or pulse == 'pump' :
    # number of points we want to send to the awg. resolution is 1 ns so len_awg = length signal in ns 
    len_awg = 150  # PULSE 1
    # len_awg = 125  # PULSE 2 and 3
    # len_awg = 200  # Random
    waveform_filename = os.path.join(output_dir, f'{pulse}_{len_awg}ns_{amplitude}.csv')
elif pulse == 'P1':
    waveform_filename = os.path.join(output_dir, f'{pulse}_10000ns_{amplitude}.csv')
    len_awg = 10000
elif pulse == 'P2':
    waveform_filename = os.path.join(output_dir, f'{pulse}_3000ns_{amplitude}.csv')
    len_awg = 3120 

d, d_interpolated, t_interpolated = theor_signal(amplitude, pulse, 6000, len_awg) 

with open(waveform_filename, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(d)

config['waveforms'][f'{channel}']['filename'] = waveform_filename   
config.write()
rmm = visa.ResourceManager()
awg = rmm.open_resource("USB0::0x168C::0x1284::0000215582::0::INSTR")   
awg.write(":SYSTem:REBoot") 
awg.close()

# Measuring the mean amplitude resulting from sending the theoretical shape
awg_config, photon_production_config, awg_config_single, photon_production_config_single = setup_awg(config, config_single) 
awg_test=run_awg_single(awg_config_single, photon_production_config_single)
awg_test=run_awg(awg_config, photon_production_config) 

mean_signal, std0 = measure_signal(osc_manager, d_interpolated, t_interpolated, channel_osc=3, channel=channel, len=len_awg, num_measurements=50, samp_rate=1e9, timebase_range=700e-9, cut= 230e-9, centered_0=False, delay=0)

d, d_interpolated, t_interpolated = theor_signal(amplitude, pulse, len(mean_signal['Voltage (V)']), len_awg)
plot_checking(mean_signal, std0, d_interpolated, len_awg, window=0, amplitude=amplitude, pulse=pulse)
if len(mean_signal) < len(d_interpolated):
    mean_signal['Voltage (V)'] = np.pad(mean_signal['Voltage (V)'], (len_awg - len(mean_signal['Voltage (V)']), 0), 'constant')
    mean_signal['Time (s)'] = np.pad(mean_signal['Time (s)'], (len_awg - len(mean_signal['Time (s)']), 0), 'constant')

# original errors
results=[]
error_area = np.trapz(np.abs(mean_signal['Voltage (V)'] - d_interpolated), mean_signal['Time (s)'])/ np.trapz(np.abs(d_interpolated), mean_signal['Time (s)'])
error = mean_squared_error(mean_signal['Voltage (V)'], d_interpolated)/ np.mean(d_interpolated ** 2)
results.append({'window': 'original', 'error_area': error_area, 'error': error})


# Finding optimal input with NLMS filter (only for stokes and pump pulses)
if channel == 1 or channel == 2:
    # config_path = r'c:\Users\apc\Documents\marina\newPhotonProductionConfigNEW'
    config_path = r'c:\Users\apc\Documents\marina\awg_tests\newPhotonProductionConfigfreqtest' 
    config = ConfigObj(config_path)

    d, d_interpolated, t_interpolated = theor_signal(amplitude, pulse, len(mean_signal['Voltage (V)']), len_awg)

    window_values= list(range(1,100,10)) # you can change this range depending on the results 
    # window_values = [30, 33, 46]
    for window in window_values:
        x = mean_signal['Voltage (V)']
        N = len(x) - window
        
        max_value = min(d_interpolated.max(), x.max())
        d = d_interpolated / d_interpolated.max() * max_value
        x = x / x.max() * max_value

        print('1', window, N, len(x), len(d))

        X = np.array([x[i : i + window] for i in range(N)])
        d_window = d[window:]
        print(('2',len(d_window),len(d_window), X.shape))

        best_mu, best_error = find_best_mu(window, d_window, X)
        print(f'Best mu for window {window}: {best_mu} with error: {best_error}')

        filt = pa.filters.FilterNLMS(window, mu=best_mu)
        # filt = PositiveNLMS(window, mu=best_mu) # this avoids having negative amplitude values as a result
        y, e, w = filt.run(d_window, X)

        X_optimized = np.array([d[i : i + window] for i in range(N)])
        y_pred_optimized = np.array([np.dot(X_optimized[i], w[i-1]) if i > 0 else 0 for i in range(len(X_optimized))])
        print('3',X_optimized.shape, len(y_pred_optimized))

        factor = round((len(y_pred_optimized ))/len_awg)                     
        y_pred_optimized = y_pred_optimized [::factor] 
        print('4', factor, len(y_pred_optimized))

        # y_pred_optimized is what we want to send to the awg as the optimized input, so it has to be len_awg long exactly
        if len(y_pred_optimized) < len_awg:
            y_pred_optimized = np.pad(y_pred_optimized, (len_awg - len(y_pred_optimized), 0), 'constant')
            print('5',len(y_pred_optimized))

        if len(y_pred_optimized) > len_awg:
            y_pred_optimized = y_pred_optimized[:len_awg]
            print('5',len(y_pred_optimized))

        output_dir = f'c:\\Users\\apc\\Documents\\marina\\05_may\\{today}\\{amplitude}\\{pulse}'
        os.makedirs(output_dir, exist_ok=True)
        filter_plots(len_awg, d, x, d_window, y, e, window, y_pred_optimized, channel, output_dir, savefig = True) 

        y_pred_optimized = y_pred_optimized / y_pred_optimized.max() * amplitude

        # saving optimized input 
        output_dir = f'c:\\Users\\apc\\Documents\\marina\\05_may\\{today}\\{amplitude}\\{pulse}'
        os.makedirs(output_dir, exist_ok=True)
        waveform_filename = os.path.join(output_dir, f'x_optimized_{window}.csv')
        with open(waveform_filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(y_pred_optimized)

        # Changing waveform to the optimized version obtained with the filter
        config['waveforms'][f'{channel}']['filename'] = waveform_filename  
        config.write()
        
        # Executing AWG with this new configuration 
        awg_config, photon_production_config, awg_config_single, photon_production_config_single = setup_awg(config, config_single)        
        awg_test=run_awg_single(awg_config_single, photon_production_config_single)  # CH4 configuration doesn't have to change
        awg_test=run_awg(awg_config, photon_production_config) 
        
        # Oscilloscope measurement
        measured_signal, std = measure_signal(osc_manager, d_interpolated, t_interpolated, channel_osc=3, channel=channel, len=len_awg, num_measurements=50, samp_rate=1e9, timebase_range=700e-9, cut= 230e-9, centered_0=False, delay=0)
        plot_checking(measured_signal, std, d, len_awg, window=window, amplitude=amplitude, pulse=pulse)

        # plot original + optimized + theoretical
        plot_3(measured_signal, mean_signal, std, std0, d, len_awg, window=window, amplitude=amplitude, pulse=pulse)
        
        # new errors
        d, d_interpolated, t_interpolated = theor_signal(amplitude, pulse, len(measured_signal['Voltage (V)']), len_awg)
        error_area = np.trapz(np.abs(measured_signal['Voltage (V)'] - d_interpolated), measured_signal['Time (s)'])/ np.trapz(np.abs(d_interpolated), measured_signal['Time (s)'])
        mse = mean_squared_error(measured_signal['Voltage (V)'], d_interpolated)/ np.mean(d_interpolated ** 2)

        results.append({'window': window, 'error_area': error_area, 'error': mse})

    # comparison of all errors (for all window values tested)
    results_df = pd.DataFrame(results)
    output_dir = f'c:\\Users\\apc\\Documents\\marina\\05_may\\{today}\\{amplitude}\\{pulse}'
    os.makedirs(output_dir, exist_ok=True)
    results_file = os.path.join(output_dir, 'results_loop.csv')
    results_df.to_csv(results_file, index=False)
    print(results_df)
    print("Process completed.")


    selected_window = input('Input window value you want to work with (if you want original put 0): ')
    while not selected_window.isdigit() or int(selected_window) not in window_values + [0]:
        selected_window = input('Not a valid window value, input again: ')

    selected_window = int(selected_window)

    # Collecting the best data and changing config to the selected window
    if selected_window != 0: 
        file_path = f'c:\\Users\\apc\\Documents\\marina\\05_may\\{today}\\{amplitude}\\{pulse}\\x_optimized_{selected_window}.csv'
    else: # the theoretical input is better than the optimized
        file_path = f'c:\\Users\\apc\\Documents\\marina\\05_may\\{today}\\{pulse}_{len_awg}ns_{amplitude}.csv'
    
    config['waveforms'][f'{channel}']['filename'] = file_path  
    config.write()


# Optional, can be done separately with cal_power.py
# Power we need given the transition coefficients
amplitude_cal = 0.001
diff = 1
while abs(amplitude_cal/amplitude -1) > 0.1 and diff > 1e-7:
# Pause to change the fiber/ the power distrubution
    input('Press Enter to continue')

    cg_d2_map = {'stokes': cg_d2_stokes,'pump': cg_d2_pump, 'P1': cg_d2_p1, 'P2': cg_d2_p1}
    rabi_d2_map = {'stokes': rabi_stirap_d2,'pump': rabi_stirap_d2, 'P1': rabi_p1_d2, 'P2': rabi_p2_d2}

    target_power_d2 = rabi_to_laserpower(rabi_d2_map[pulse], d_d2, cg_d2_map[pulse] , typical_waist_size) # in mW
    target_power_d2 *= 10**(-3) # to W
    print(f'Target Power for desired Rabi Freq: {target_power_d2}')

    # Finding the voltage amplitude that corresponds to this power
    awg_chan_freqs_map = {1: [107], 2: [78.5], 3: [62.35], 4: [82.5]}

    awg_channels_dict = {1:Channel.CHANNEL_1, 2:Channel.CHANNEL_2, 3:Channel.CHANNEL_3, 4:Channel.CHANNEL_4}
    amplitude_cal, diff = calibrate.finding_amplitude_from_power(awg_chan_freqs_map[channel], target_power_d2, awg_channels_dict[channel], n_steps = 100, repeats=3, delay=0.3,\
                                calibration_lims = (0,1))

# Pause to change the fiber
input('Press Enter to continue')

if channel == 1 or channel == 2:
    # We renormalize the optimized input to the amplitude we really want to work with                         
    opt_input = pd.read_csv(file_path, header=None)
    opt_input = opt_input.T.to_numpy().flatten()
    opt_input = opt_input/opt_input.max()*amplitude_cal

    output_dir = f'c:\\Users\\apc\\Documents\\marina\\05_may\\{today}\\{amplitude}\\{pulse}\\opt_from_{amplitude}_to_{amplitude_cal}'
    os.makedirs(output_dir, exist_ok=True)
    waveform_filename = os.path.join(output_dir, f'x_optimized_{selected_window}.csv')
    with open(waveform_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(opt_input)


