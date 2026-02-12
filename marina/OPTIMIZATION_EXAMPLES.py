"""
AWG Pulse Optimization - Usage Examples & Tutorial

This file demonstrates how to use the pulse optimization system
with practical code examples.

@author: Refactored documentation
"""

# =========================================================================
# Example 1: Basic Forward Optimization (Recommended for first-time users)
# =========================================================================

"""
Scenario: You want to optimize the STIRAP stokes pulse (channel 1).

Steps:
1. Set up hardware connection
2. Configure optimization parameters
3. Run full optimization
"""

from marina.pulse_optimizer_core import (
    load_theoretical_signal,
    get_theoretical_signal_path,
    ScopeDataAcquisition,
    PositiveNLMS,
    find_optimal_mu,
    compute_error_metrics,
    normalize_signals_to_max,
    SignalPlotter,
)
from instruments.agilent_9000 import OscilloscopeManager
import numpy as np

# Connect to oscilloscope (Agilent 9000 series)
scope_manager = OscilloscopeManager(scope_id="USB0::0x2A8D::0x900E::MY53450121::0::INSTR")

# Load theoretical signal
signal_path = get_theoretical_signal_path('stokes')  # Returns path to CSV
original_sig, theoretical_sig, time_array = load_theoretical_signal(
    csv_path=signal_path,
    amplitude=0.2,          # Normalize to 20% of max
    target_length=6000,     # Interpolate to 6000 samples
    total_length_ns=8000    # Representing 8000 ns of signal
)

print(f"Loaded signal: {len(original_sig)} original → {len(theoretical_sig)} interpolated")

# Configure scope
scope_config = {
    'channel_map': {1: (-0.5, 0.5)},  # Ch1: -0.5 to +0.5 V range
    'samp_rate': 1e9,                  # 1 GHz sampling
    'timebase_range': (-2e-6, 2e-6)    # ±2 microseconds
}

acq = ScopeDataAcquisition(scope_manager, scope_config)
acq.configure_and_arm(trigger_channel=1, trigger_level=0.5)

# Measure response to theoretical signal
mean_response, std_response = acq.acquire_data([1], num_measurements=50)
measured_voltage = mean_response['Voltage (V)'].values

print(f"Measured: {len(measured_voltage)} samples, "
      f"mean={np.mean(measured_voltage):.3f}V, "
      f"std={np.std(measured_voltage):.3f}V")

# Disconnect
scope_manager.quit()


# =========================================================================
# Example 2: Manual Window Optimization with Detailed Inspection
# =========================================================================

"""
Scenario: You want to understand how window size and learning rate affect filtering.

This example shows the inner loop of the optimization.
"""

# Normalize signals for processing
measured_norm, theoretical_norm = normalize_signals_to_max(measured_voltage, theoretical_sig)

# Try a single window size
window_size = 20

# Create input matrix: each row is a window of the measured signal
n_windows = len(measured_voltage) - window_size
X = np.array([measured_norm[i:i + window_size] for i in range(n_windows)])
desired = theoretical_norm[window_size:]

print(f"Window size: {window_size}")
print(f"Input matrix shape: {X.shape}")  # (n_windows, window_size)
print(f"Desired signal length: {len(desired)}")

# Find optimal learning rate via grid search
best_mu, best_error = find_optimal_mu(
    window_size=window_size,
    desired=desired,
    input_data=X,
    mu_range=(0.1, 1.9),
    n_points=15
)

print(f"Best mu: {best_mu:.3f}, Error: {best_error:.4f}")

# Run filter with optimal mu
filt = PositiveNLMS(order=window_size, mu=best_mu)
output, error, weights_history = filt.run(desired, X)

# Compute error metrics
metrics = compute_error_metrics(output, desired)
print(f"MSE: {metrics['mse']:.6f}")
print(f"RMSE: {metrics['rmse']:.6f}")
print(f"MAE: {metrics['mae']:.6f}")

# Plot results
plotter = SignalPlotter('optimization_results')
plotter.plot_filter_adaptation(
    desired, output, error,
    time_array[:len(desired)],
    title=f"NLMS Filter (window={window_size}, mu={best_mu:.3f})"
)


# =========================================================================
# Example 3: Window Size Sweep (Batch Processing)
# =========================================================================

"""
Scenario: You want to find the best window size over a range.

This is what the main optimizer does internally.
"""

# Search over window sizes
window_sizes = range(5, 50, 3)  # Test sizes 5, 8, 11, ..., 47
results = []

for window_size in window_sizes:
    # Skip if window too large
    if window_size > len(measured_norm) // 2:
        print(f"Skipping window {window_size} (too large)")
        continue
    
    # Create windows
    n_windows = len(measured_norm) - window_size
    X = np.array([measured_norm[i:i + window_size] for i in range(n_windows)])
    desired = measured_norm[window_size:]
    
    # Find optimal mu
    best_mu, best_error = find_optimal_mu(window_size, desired, X, n_points=10)
    
    # Run final filter
    filt = PositiveNLMS(order=window_size, mu=best_mu)
    output, error, _ = filt.run(desired, X)
    
    # Compute metrics
    metrics = compute_error_metrics(output, desired)
    
    results.append({
        'window': window_size,
        'mu': best_mu,
        'mse': metrics['mse'],
        'rmse': metrics['rmse'],
        'mae': metrics['mae'],
    })
    
    print(f"Window {window_size:2d}: mu={best_mu:.3f}, MSE={metrics['mse']:.6f}")

# Find best result
best_idx = np.argmin([r['mse'] for r in results])
best_result = results[best_idx]
print(f"\nBest: Window {best_result['window']}, MSE {best_result['mse']:.6f}")


# =========================================================================
# Example 4: Iterative Refinement with Re-measurement
# =========================================================================

"""
Scenario: You want to iteratively improve the signal and measure progress.

This is the full feedback loop.
"""

# Starting point: theoretical signal
current_waveform = theoretical_sig.copy()
iteration = 0
max_iterations = 3

for iteration in range(max_iterations):
    print(f"\n=== Iteration {iteration + 1} ===")
    
    # Send current waveform to AWG
    # awg.upload_waveform(current_waveform)  # Pseudo-code
    
    # Measure response (would trigger scope)
    # measured = acq.acquire_data([1], num_measurements=50)
    # measured_voltage = measured[0].values
    
    # For demo, assume response slightly improved (simulation)
    measured_voltage = measured_voltage * (1 + 0.1 / (iteration + 1))
    
    # Find optimal window (simplified)
    best_window = 25
    best_mu = 0.6
    
    # Compute prediction for next input
    measured_norm, theoretical_norm = normalize_signals_to_max(measured_voltage, theoretical_sig)
    
    n_windows = len(measured_norm) - best_window
    X = np.array([measured_norm[i:i + best_window] for i in range(n_windows)])
    desired = theoretical_norm[best_window:]
    
    filt = PositiveNLMS(order=best_window, mu=best_mu)
    output, error, _ = filt.run(desired, X)
    
    # Resample to AWG length
    optimized_input = np.interp(
        np.linspace(0, 1, len(theoretical_sig)),
        np.linspace(0, 1, len(output)),
        output
    )
    
    current_waveform = optimized_input
    mse = np.mean(error**2)
    
    print(f"MSE: {mse:.6f}")
    print(f"Output range: [{output.min():.3f}, {output.max():.3f}]")
    
    if iteration < max_iterations - 1:
        print("Would send to AWG and re-measure...")


# =========================================================================
# Example 5: Using the Full Optimizer Classes
# =========================================================================

"""
Scenario: Use the high-level optimizer API for complete automation.

This is the recommended approach for production use.
"""

from marina.optimize_awg_pulse_forward import ForwardOptimizer

# Initialize from config file
optimizer = ForwardOptimizer('config_forward.ini')

# Run full optimization
try:
    optimizer.run()
except Exception as e:
    print(f"Error: {e}")


# =========================================================================
# Example 6: Custom Signal Analysis & Comparison
# =========================================================================

"""
Scenario: Compare multiple optimization runs or signals.

This example shows data analysis workflows.
"""

import pandas as pd
import matplotlib.pyplot as plt

# Load results from multiple runs
results_dir = 'optimization_results'

# Read optimization results
results_df = pd.read_csv(f'{results_dir}/optimization_results.csv')

# Analyze
print("Optimization Summary:")
print(f"  Baseline MSE: {results_df[results_df['window'] == 'baseline']['mse'].values[0]:.6f}")
print(f"  Best result: {results_df['mse'].min():.6f}")
print(f"  Improvement: {(1 - results_df['mse'].min() / results_df[results_df['window'] == 'baseline']['mse'].values[0]) * 100:.1f}%")

# Plot error vs window size
optimized = results_df[results_df['window'] != 'baseline']
plt.figure(figsize=(10, 6))
plt.plot(optimized['window'], optimized['mse'], 'o-', linewidth=2, markersize=8)
plt.xlabel('Window Size')
plt.ylabel('Mean Squared Error')
plt.title('Optimization Results')
plt.grid(True, alpha=0.3)
plt.axhline(y=results_df['mse'].min(), color='r', linestyle='--', label='Best')
plt.legend()
plt.tight_layout()
plt.savefig(f'{results_dir}/analysis.png', dpi=150)
plt.show(block=False)


# =========================================================================
# Example 7: Power Calibration (Optional Advanced Feature)
# =========================================================================

"""
Scenario: Convert optimized amplitude to laser power in mW.

Useful for experimenters who need to know the actual laser power.
"""

from marina.pulse_optimizer_core import (
    rabi_to_laserpower,
    laserpower_to_rabi,
    PhysicalConstants
)

# For a stokes pulse (D2 transition)
rabi_freq_mhz = 100  # Example Rabi frequency
beam_waist_um = 20   # Beam waist in micrometers

power_mw = rabi_to_laserpower(
    omega_mhz=rabi_freq_mhz,
    dipole_moment=PhysicalConstants.D_D2,
    cg_coefficient=PhysicalConstants.CG_D2_STOKES,
    beam_waist_um=beam_waist_um
)

print(f"Rabi frequency: {rabi_freq_mhz} MHz → {power_mw:.2f} mW")

# Reverse conversion
rabi_back = laserpower_to_rabi(
    power_mw=power_mw,
    dipole_moment=PhysicalConstants.D_D2,
    cg_coefficient=PhysicalConstants.CG_D2_STOKES,
    beam_waist_um=beam_waist_um
)

print(f"Power: {power_mw:.2f} mW → {rabi_back:.1f} MHz (check: should match input)")


# =========================================================================
# Example 8: Troubleshooting & Debugging
# =========================================================================

"""
Scenario: Debug an optimization that isn't converging well.

This example shows diagnostic plots and checks.
"""

import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

# Check signal characteristics
print("Signal Diagnostics:")
print(f"  Theoretical: min={theoretical_sig.min():.3f}, max={theoretical_sig.max():.3f}, mean={theoretical_sig.mean():.3f}")
print(f"  Measured:    min={measured_voltage.min():.3f}, max={measured_voltage.max():.3f}, mean={measured_voltage.mean():.3f}")
print(f"  SNR estimate: {np.std(measured_voltage) / np.std(measured_voltage - np.mean(measured_voltage)):.1f}")

# Check for aliasing/truncation
print(f"  Signal not saturated: {measured_voltage.max() < 0.9 * 0.5}")  # Assuming ±0.5V range
print(f"  Has structure: {np.std(measured_voltage) > 0.01}")

# Check NLMS convergence behavior
window = 15
n_windows = len(measured_norm) - window
X = np.array([measured_norm[i:i + window] for i in range(n_windows)])
desired = theoretical_norm[window:]

filt = PositiveNLMS(order=window, mu=0.5)
output, error, weights = filt.run(desired, X)

# Plot convergence
fig, axes = plt.subplots(2, 2, figsize=(12, 8))

# Error convergence
error_db = 10 * np.log10(error**2 + 1e-12)
axes[0, 0].plot(error_db[:200])  # First 200 samples
axes[0, 0].set_title('Convergence (first 200 samples)')
axes[0, 0].set_ylabel('Error (dB)')
axes[0, 0].grid(True, alpha=0.3)

# Overall error
axes[0, 1].plot(error_db)
axes[0, 1].set_title('Convergence (all samples)')
axes[0, 1].set_ylabel('Error (dB)')
axes[0, 1].grid(True, alpha=0.3)

# Output vs desired
axes[1, 0].plot(output[:300], label='Output')
axes[1, 0].plot(desired[:300], label='Desired')
axes[1, 0].set_title('Output vs Desired (first 300)')
axes[1, 0].legend()
axes[1, 0].grid(True, alpha=0.3)

# Weight evolution (first filter weight)
first_weights = [w[0] for w in weights]
axes[1, 1].plot(first_weights)
axes[1, 1].set_title('First Filter Coefficient Evolution')
axes[1, 1].set_ylabel('Weight Value')
axes[1, 1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('debugging_analysis.png', dpi=150)
plt.show(block=False)

print("\nDiagnostic plots saved to debugging_analysis.png")
