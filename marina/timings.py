'''
Checks that the selected optimized pulses are correct.

Refactored 09/12/2024

@author: Marina Llano
'''

import time

import matplotlib.pylab as plt
import numpy as np
import oscilloscope_manager as osc
import pandas as pd
import pyvisa as visa
import scipy.integrate as spi
from cold_control_files.awg_control_functions import run_awg
from configobj import ConfigObj

from classes.ExperimentalConfigs import (
    AwgConfiguration,
    PhotonProductionConfiguration,
    TdcConfiguration,
    Waveform,
)


def to_bool(string):
    return string.lower() in ['true', 't', 'yes', 'y']

def setup_awg(config):
    """ Configures the AWG. """
    awg_config = AwgConfiguration(sample_rate = float(config['AWG']['sample rate']),
                                    burst_count = int(config['AWG']['burst count']),
                                    waveform_output_channels = list(config['AWG']['waveform output channels']),
                                    waveform_output_channel_lags = map(float, config['AWG']['waveform output channel lags']),
                                    marked_channels = list(config['AWG']['marked channels']),
                                    marker_width = eval(config['AWG']['marker width']),
                                    waveform_aom_calibrations_locations = list(config['AWG']['waveform aom calibrations locations']))

    tdc_config = TdcConfiguration(counter_channels = map(eval, config['TDC']['counter channels']),
                                    marker_channel = int(config['TDC']['marker channel']),
                                    timestamp_buffer_size = int(config['TDC']['timestamp buffer size']))

    waveforms = []
    for x,v in config['waveforms'].items():
        waveforms.append(Waveform(fname = v['filename'],
                                    mod_frequency= float(v['modulation frequency']),
                                    phases=map(float, v['phases'])))

    photon_production_config = PhotonProductionConfiguration(save_location = config['save location'],
                                                                mot_reload  = eval(config['mot reload']),
                                                                iterations = int(config['iterations']),
                                                                waveform_sequence = list(eval(config['waveform sequence'])),
                                                                waveforms = waveforms,
                                                                waveform_stitch_delays = list(eval(config['waveform stitch delays'])),
                                                                interleave_waveforms = to_bool(config['interleave waveforms']),
                                                                awg_configuration = awg_config,
                                                                tdc_configuration = tdc_config)

    return awg_config, photon_production_config

def measure_signal(osc_manager, num_measurements=50, samp_rate=1e9, timebase_range=3e-6):
    """ Performs measurements using the oscilloscope and returns the mean acquired signal. """
    all_stokes = []
    all_pump = []
    for _ in range(num_measurements):

        data_stokes = osc_manager.acquire_with_trigger(4, samp_rate=samp_rate, timebase_range=timebase_range)
        data_pump = osc_manager.acquire_with_trigger(1, samp_rate=samp_rate, timebase_range=timebase_range)

        all_stokes.append(data_stokes)
        all_pump.append(data_pump)
        time.sleep(0.2)

    meas_stokes= pd.DataFrame()
    meas_pump= pd.DataFrame()

    for i, (data_stokes, data_pump) in enumerate(zip(all_stokes, all_pump)):
        meas_stokes[f'Time (s) {i}'] = data_stokes['Time (s)']
        meas_stokes[f'Voltage (V) {i}'] = data_stokes['Voltage (V)']
        meas_pump[f'Time (s) {i}'] = data_pump['Time (s)']
        meas_pump[f'Voltage (V) {i}'] = data_pump['Voltage (V)']

    meas_stokes = meas_stokes [(meas_stokes.filter(like='Time (s)').iloc[:, 0] >= 0.822e-6) & (meas_stokes.filter(like='Time (s)').iloc[:, 0] <= 1.022e-6)].copy()
    meas_pump = meas_stokes [(meas_stokes .filter(like='Time (s)').iloc[:, 0] >= 0.822e-6) & (meas_stokes.filter(like='Time (s)').iloc[:, 0] <= 1.022e-6)].copy()
    meas_stokes.loc[:, meas_stokes .filter(like='Time (s)').columns] -= meas_stokes.filter(like='Time (s)').iloc[0, 0]
    meas_pump.loc[:, meas_pump.filter(like='Time (s)').columns] -= meas_pump.filter(like='Time (s)').iloc[0, 0]

    sqrt_volt_stokes = np.sqrt(meas_stokes.filter(like='Voltage (V)').clip(lower=0))
    sqrt_volt_pump = np.sqrt(meas_pump.filter(like='Voltage (V)').clip(lower=0))

    sqrt_volt_pump -= abs(sqrt_volt_pump.min())

    mean_time_stokes = meas_stokes.filter(like='Time (s)').mean(axis=1)
    mean_time_pump = meas_pump .filter(like='Time (s)').mean(axis=1)
    mean_voltage_stokes = sqrt_volt_stokes.mean(axis=1)
    mean_voltage_pump = sqrt_volt_pump .mean(axis=1)
    std_voltage_stokes = sqrt_volt_stokes.std(axis=1)
    std_voltage_pump = sqrt_volt_pump .std(axis=1)

    mean_data_stokes  = pd.DataFrame({'Time (s)': mean_time_stokes ,'Voltage (V)': mean_voltage_stokes })
    mean_data_pump  = pd.DataFrame({'Time (s)': mean_time_pump ,'Voltage (V)': mean_voltage_pump })
    std_data_stokes  = pd.DataFrame({'Time (s)': mean_time_stokes , 'Voltage (V)': std_voltage_stokes })
    std_data_pump  = pd.DataFrame({'Time (s)': mean_time_pump , 'Voltage (V)': std_voltage_pump })

    return mean_data_stokes, std_data_stokes, mean_data_pump , std_data_pump


##############################################################

file_path = 'data/2025-01-31/stokes_150ns_20.csv'
stokes_th = pd.read_csv(file_path, header=None)
stokes_th= stokes_th.T
stokes_th=stokes_th.to_numpy().flatten()

file_path = 'data/2025-01-31/pump_150ns_20.csv'
pump_th = pd.read_csv(file_path, header=None)
pump_th= pump_th.T
pump_th=pump_th.to_numpy().flatten()

stokes_th/=stokes_th.max()
pump_th/=pump_th.max()

# we send to the awg the most optimized input versions found previously
config_path = r'c:\Users\apc\Documents\marina\newPhotonProductionConfigNEW'
config = ConfigObj(config_path)

# write here the waveforms optimized
opt_stokes = r'c:\Users\apc\Documents\marina\03_mar\06-03\0.25\stokes\x_optimized_1.csv'
opt_pump = r'c:\Users\apc\Documents\marina\03_mar\06-03\0.1\pump\x_optimized_1.csv'
waveform_stokes = pd.read_csv(opt_stokes, header=None)
waveform_pump = pd.read_csv(opt_pump, header=None)
config['waveforms']['1']['filename'] = waveform_stokes
config['waveforms']['2']['filename'] = waveform_pump
config.write()
awg_config, photon_production_config = setup_awg(config)
awg_test=run_awg(awg_config, photon_production_config)

rm = visa.ResourceManager('@py')
osc_manager = osc.oscilloscope_manager()
stokes, std_stokes, pump , std_pump= measure_signal(osc_manager, num_measurements=50, samp_rate=1e9, timebase_range=3e-6)
t=np.linspace(0, 150e-9, len(stokes))

stokes/=stokes.max()
pump/=pump.max()

overlap_region = np.minimum(stokes, pump)  # we compute overlap taking measures with 1200 points
overlap_area = spi.simpson(overlap_region, t)
print(overlap_area)

plt.plot(t,stokes, 'r', label='Stokes measured')
plt.plot(t,pump, 'g', label='Pump measured')
plt.plot(t[::8],stokes_th, 'r', linestyle='--')
plt.plot(t[::8],pump_th, 'g', linestyle='--')
plt.show()

