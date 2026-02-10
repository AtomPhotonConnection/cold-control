import os
import sys
from typing import Dict, cast
import pyvisa as visa
import numpy as np



sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) # add parent directory to path

from marina.optimize_awg_pulse_inverted import InvertedOptimizer
from marina.optimize_awg_pulse_forward import ForwardOptimizer
from marina.pulse_optimizer_core import load_signal_from_path, resample_signal

from instruments.Oscilloscopes.agilent_mso9254A import OscilloscopeManager


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Get scope ID
rm = visa.ResourceManager()
scope_ids = rm.list_resources()
print("Available instruments:", scope_ids)

# Connect to Agilent 9000 scope
scope = OscilloscopeManager("USB0::0x2A8D::0x900E::MY53450121::0::INSTR")
assert scope.is_connected(), "Scope not connected!"
print("✓ Scope connected")



config_path = os.path.join(SCRIPT_DIR, 'config_inverted.ini')
optimizer = InvertedOptimizer(config_path)
optimizer.scope = scope  # Reuse the already-connected scope (optimizer won't close it)


try:
    optimizer.run()
finally:
    scope.quit()

# try:
#     # 1. Connect hardware
#     optimizer.connect_scope()

#     optimizer.load_awg_config()
    
#     # 2. Load theoretical signal
#     signal_path: str = optimizer.pulse_paths[optimizer.pulse_type]
    
#     scaled_sig = load_signal_from_path(
#         signal_path,
#         amplitude=optimizer.amplitude
#     )

#     assert optimizer.awg_config_obj is not None, "AWG config not loaded"
#     total_length_s = 1/optimizer.awg_config_obj.sample_rate * len(scaled_sig)

#     time_array = np.linspace(0, total_length_s, len(scaled_sig), endpoint=True)
    
    
#     # 3. Measure theoretical response
#     measured_mean, measured_std = optimizer.measure_scope_response(scaled_sig, "theoretical")
    
#     # Scope returns 'Channel N Voltage (V)' columns
#     voltage_col = [c for c in measured_mean.columns if 'Voltage' in c][0]
#     measured_voltage = measured_mean[voltage_col].values
    
#     # Resample measured to match theoretical length if needed
#     if len(measured_voltage) != len(scaled_sig):
#         measured_voltage = resample_signal(measured_voltage, len(measured_voltage), len(scaled_sig))
    
#     # Plot initial comparison
#     std_col = [c for c in measured_std.columns if 'Voltage' in c]
#     std_values = measured_std[std_col[0]].values[:len(scaled_sig)] if std_col and len(measured_std) > 0 else None
#     optimizer.plotter.plot_signal_comparison(
#         measured_voltage, time_array[:len(scaled_sig)], scaled_sig,
#         std=std_values,
#         title="Measured vs Theoretical Signal (Before Optimization)",
#         filename="01_initial_comparison.png"
#     )
# finally:
#     scope.quit()  # Ensure scope connection is closed after measurement#
#     # close awg connection if open
#     if optimizer.awg is not None:
#         optimizer.awg.close()


