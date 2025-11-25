
"""STIRAP Rabi frequency CSV generator

Change the global variables below to control output. Run this file directly with Python to
generate CSV files in OUTPUT_DIR.

Generated CSV format: time, Omega_P_norm, Omega_S_norm
- Time units are arbitrary (consistent with PULSE_LENGTHS).
- Omega values are normalized so max(Omega_P) = max(Omega_S) = 1 for each file separately.
"""

from pathlib import Path
from typing import Dict
import numpy as np
import pandas as pd
import math
import csv

import scipy.special as sc


# ----------------- GLOBAL VARIABLES (edit these) -----------------
PULSE_LENGTHS = [1.0, 2.0]   # list of pulse durations (T) to generate files for, in us
OUTPUT_DIR = r"C:\Users\LabUser\Documents\cold-control\waveforms\pulse_shaping_exp\stirap"
SAMPLE_RATE = 1000       # points per unit T
PULSE_SHAPE = 'standard'     # "standard" 'gaussian', 'sech', 'sin_cos'
OPTIONS = {
    "tau": 1e-7
}
# STOKES_LEAD_FRACTION = 0.5
# SIGMA_FACTOR = 0.3
# TIME_EXTENT_MULT = 4.0
# -----------------------------------------------------------------


# NOTE: These seem to be wrong?
# def pump(t:float, T:float, tau:float):
#     """
#     Calculates the magnitude of the pump pulse Rabi frequency at a particular time step.
#     t (float): current time
#     T (float): total time for the pulses
#     tau (float): pulse delay between the two pulses
#     """
#     x = np.divide((t-tau/2), T**2)
#     return np.exp(-x)

# def stokes(t:float, T:float, tau:float):
#     """
#     Calculates the magnitude of the Stokes pulse Rabi frequency at a particular time step.
#     t (float): current time
#     T (float): total time for the pulses
#     tau (float): pulse delay between the two pulses
#     """
#     x = np.divide((t+tau/2), T**2)
#     return np.exp(-x)

def stokes2(t, T):
    a=10
    n=4
    c=T/3
    return (np.exp(-((t - (T/2))/c)**(2*n))*np.cos(np.pi/2*(1/(1 + np.exp((-a*(t - T/2))/T)))))


def pump2(t, T):
    a=10
    n=4
    c=T/3
    return (np.exp(-((t - (T/2))/c)**(2*n))*np.sin(np.pi/2*(1/(1 + np.exp((-a*(t - T/2))/T)))))



## NOTE: NOT REALLY SURE WHAT THESE FUNCTIONS ARE, CHATGPT MADE THEM
# def gaussian(t, t0, T, sigma_factor=0.3):
#     sigma = sigma_factor * T
#     return np.exp(-0.5 * ((t - t0)/sigma)**2)

# def sech(t, t0, T):
#     y = T * 0.5
#     x = (t - t0) / y
#     return 1.0 / np.cosh(x)

# def sin_cos_mixing(t, t0_p, t0_s, T):
#     # smooth mixing using error function based theta
#     t_mid = 0.5*(t0_p + t0_s)
#     w = 0.4 * T
#     theta = 0.5 * math.pi * (0.5 * (1 + sc.erf((t - t_mid)/w)))
#     return math.sin(theta), math.cos(theta)




def export_to_csv(array, filepath, filename):
    try:
        full_path = f"{filepath}/{filename}"
        
        rescaled_arr=np.zeros((len(array)))
        for i, el in enumerate(array):
            if abs(el)<10**(-9):
                rescaled_arr[i]=0
            else:
                rescaled_arr[i]=array[i]

        np.savetxt(full_path, rescaled_arr, delimiter=',',newline=',',fmt='%.10f')
        # Remove trailing comma from the file
        with open(full_path, 'r+') as f:
            f.seek(0, 2)  # Move the cursor to the end of the file
            f.seek(f.tell() - 1, 0)  # Move one character back from the end
            if f.read(1) == ',':  # Check if the last character is a comma
                f.seek(f.tell() - 1, 0)  # Move one character back from the end again
                f.truncate()  # Remove the trailing comma
        # Append a newline at the end of the file
        with open(full_path, 'a') as f:
            f.write('\n')

        print(f"Data successfully exported to {full_path}")
    except Exception as e:
        print(f"Error exporting data to {full_path}: {e}")





def generate_rabi(T, shape='standard', sample_rate=1000, output_dir='.',
                  options:Dict = {}):
    
    # time axis
    N = int(T * sample_rate)
    t = np.linspace(0, T, N)

    if shape == "standard":
        Omega_S = stokes2(t, T)
        Omega_P = pump2(t, T)
    # elif shape == 'gaussian':
    #     Omega_S = gaussian(t, options["t_s"], T, options["sigma_factor"])
    #     Omega_P = gaussian(t, options["t_p"], T, options["sigma_factor"])
    # elif shape == 'sech':
    #     Omega_S = sech(t, options["t_s"], T)
    #     Omega_P = sech(t, options["t_p"], T)
    # elif shape == 'sin_cos':
    #     Omega_P = np.zeros_like(t)
    #     Omega_S = np.zeros_like(t)
    #     for i, ti in enumerate(t):
    #         s, c = sin_cos_mixing(ti, options["t_p"], options["t_s"], T)
    #         Omega_P[i] = s
    #         Omega_S[i] = c
    else:
        raise ValueError('Unsupported shape for STIRAP pulses: ' + str(shape))

    # Normalize separately so each has max = 1
    maxP = np.max(np.abs(Omega_P)) if np.max(np.abs(Omega_P)) != 0 else 1.0
    maxS = np.max(np.abs(Omega_S)) if np.max(np.abs(Omega_S)) != 0 else 1.0
    Omega_P_norm = Omega_P / maxP
    Omega_S_norm = Omega_S / maxS

    filename_prefix = f"{shape}_{T*1000:.0f}ns"


    export_to_csv(Omega_P_norm, output_dir, filename_prefix + '_pump.csv')
    export_to_csv(Omega_S_norm, output_dir, filename_prefix + '_stokes.csv')

    
    return str(filename_prefix)


def main():
    files = []
    for T in PULSE_LENGTHS:
        fname = generate_rabi(T, shape=PULSE_SHAPE, sample_rate=SAMPLE_RATE, output_dir=OUTPUT_DIR,\
                              options=OPTIONS)
        files.append(fname)
    print("Done. Generated files:\n" + "\n".join(files))

if __name__ == '__main__':
    main()
