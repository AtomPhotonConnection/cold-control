# AWG Pulse Optimization System

A refactored and improved system for optimizing AWG (Arbitrary Waveform Generator) output pulses using oscilloscope feedback and NLMS adaptive filtering.

## Overview

This system allows you to optimize the input signal sent to an AWG such that the output signal matches a theoretical/desired target. It uses adaptive filtering techniques to find the optimal waveform and iteratively improves it.

The system supports **Agilent Infiniium 9000 series** oscilloscopes for signal measurement and Keysight WX218x AWG for waveform generation.

### Two Optimization Approaches

1. **Forward Optimization** (`optimize_awg_pulse_forward.py`)
   - Send theoretical signal → measure response → find optimal input
   - Best for: Known theoretical output, need to find input
   - Algorithm: NLMS filter learns mapping from measured to desired output

2. **Inverted Optimization** (`optimize_awg_pulse_inverted.py`)
   - Send theoretical signal → measure response → invert the process
   - Best for: Complex system dynamics, need to understand input requirements
   - Algorithm: NLMS learns which input would produce the measured output

## Installation & Setup

### Dependencies

```bash
pip install numpy scipy pandas matplotlib scikit-learn configobj python-visa
```

### Hardware Requirements

- **Oscilloscope**: Agilent Infiniium 9000 Series with VISA/USB connection
- **AWG**: Keysight WX218x series with VISA/USB connection  
- **MATLAB/Octave**: For real-time waveform visualization (optional)

## Quick Start

### 1. Configure Hardware Connection

Edit `config_forward.ini` or `config_inverted.ini`:

```ini
[Hardware]
scope_id = USB0::0x0957::0x17A0::MY54280441::0::INSTR
awg_id = USB0::0x168C::0x1284::0000215582::0::INSTR

[Channel]
channel = 1  # Select 1-4
pulse_type = stokes  # or pump, P1, P2
```

Find your VISA resource IDs:
```python
import visa
rm = visa.ResourceManager()
print(rm.list_resources())
```

### 2. Set Optimization Parameters

```ini
[Optimization]
amplitude = 0.2
len_awg = 8000  # nanoseconds
window_min = 3
window_max = 50
window_step = 2
mu_min = 0.1
mu_max = 1.9
```

### 3. Configure Oscilloscope

```ini
[Oscilloscope]
trigger_channel = 1
trigger_level = 0.5
samp_rate = 1e9
timebase_start = -2e-6
timebase_stop = 2e-6
```

### 4. Run Optimization

```bash
# Forward approach
python optimize_awg_pulse_forward.py

# Inverted approach  
python optimize_awg_pulse_inverted.py
```

## Architecture

### Module Organization

```
pulse_optimizer_core.py
├── PhysicalConstants (Rabi frequency, laser power conversions)
├── Signal Loading (load_theoretical_signal, get_theoretical_signal_path)
├── ScopeDataAcquisition (oscilloscope control & measurement)
├── PositiveNLMS (adaptive filter implementation)
├── Error Metrics (compute_error_metrics, normalize_signals_to_max)
└── SignalPlotter (visualization & result saving)

optimize_awg_pulse_forward.py
└── ForwardOptimizer (main optimization loop)

optimize_awg_pulse_inverted.py
└── InvertedOptimizer (main optimization loop)
```

### Data Flow

#### Forward Optimization
```
Theoretical Signal
    ↓ [Send to AWG]
    ↓ [Measure with Scope]
Measured Response
    ↓ [Run NLMS filter]
    ↓ [Window size sweep]
Optimal Window Size
    ↓ [Predict Input]
Optimized Input
    ↓ [Send to AWG]
    ↓ [Re-measure]
Better Output
```

#### Inverted Optimization
```
Theoretical Signal
    ↓ [Send to AWG]
    ↓ [Measure with Scope]
Measured Response
    ↓ [Invert NLMS]
    ↓ [Window size sweep]
Optimal Input Estimate
    ↓ [Send to AWG]
    ↓ [Re-measure]
Better Output
```

## Key Classes & Functions

### `pulse_optimizer_core.py`

#### `PositiveNLMS`
Normalized Least Mean Squares filter with optional positive constraint.

```python
filt = PositiveNLMS(order=30, mu=0.5, min_value=0.0)
output, error, weights_history = filt.run(desired_signal, input_array)
```

Parameters:
- `order`: Window size (filter length)
- `mu`: Step size/learning rate (0.1-1.9 typical)
- `min_value`: Force output ≥ this value

#### `ScopeDataAcquisition`
Manages oscilloscope configuration and multi-measurement averaging.

```python
acq = ScopeDataAcquisition(scope_manager, scope_config)
acq.configure_and_arm(trigger_channel=1, trigger_level=0.5)
mean_signal, std_signal = acq.acquire_data([1, 2], num_measurements=50)
```

#### `SignalPlotter`
Creates publication-quality plots of optimization progress.

```python
plotter = SignalPlotter('output_dir')
plotter.plot_signal_comparison(measured, time, theoretical, std=std_array)
plotter.plot_filter_adaptation(desired, output, error, time)
```

### Error Metrics

- **MSE**: Mean Squared Error (normalized by signal power)
- **RMSE**: Root MSE
- **MAE**: Mean Absolute Error
- **Trapz Error**: Integral-based error using trapezoidal rule

## Optimization Process

### Window Size Selection

The NLMS filter order (window size) trades off:
- **Small windows**: Fast adaptation, noisy estimates
- **Large windows**: Smoother estimates, slower convergence

The optimizer searches over a range and selects the window that minimizes error.

### Learning Rate (mu) Optimization

For each window size:
1. Grid search over mu values (typically 0.1 to 1.9)
2. Select mu with lowest MSE
3. Use that mu for final filter run

### Iterative Improvement

1. **Baseline**: Measure response to theoretical signal
2. **Search**: Try all window sizes
3. **Refine**: Use best window for detailed optimization
4. **Validation**: Send optimized signal, re-measure (optional)

## Configuration Details

### Signal Types

Each pulse type corresponds to an AWG channel and has a theoretical CSV:

| Channel | Pulse Type | CSV Path | Description |
|---------|-----------|----------|-------------|
| 1 | stokes | `calibrations/StirapDL_awg/stokes.csv` | STIRAP Eylsa stokes |
| 2 | pump | `calibrations/StirapDL_awg/pump.csv` | STIRAP DLPro pump |
| 3 | P1 | `calibrations/ELYSA_fibre_branch/P1.csv` | Opt Pump Eylsa |
| 4 | P2 | `calibrations/ELYSA_fibre_branch/P2.csv` | Opt Pump DLPro |

### Physical Constants

Rabi frequency ↔ Laser Power conversion uses atomic dipole moments and Clebsch-Gordan coefficients:

```python
# D2 transition (780 nm)
dipole_moment = 2.853e-29  # C*m
cg_coefficient = 0.1441    # depends on specific F → F' transition
beam_waist = 20            # micrometers

power_mw = rabi_to_laserpower(omega_mhz, dipole_moment, cg_coefficient, beam_waist)
```

## Output Files

### Saved During Optimization

```
optimization_results/
├── 01_initial_response.png         # Before optimization
├── awg_theoretical_*.csv           # Theoretical signal sent to AWG
├── awg_optimized_*.csv             # Final optimized signal
└── optimization_results.csv        # Error metrics summary
```

### Results CSV

Columns:
- `window`: Filter order tested (or 'baseline')
- `mu`: Learning rate (if optimized)
- `mse`: Mean squared error
- `rmse`: Root mean squared error
- `mae`: Mean absolute error

## Troubleshooting

### "Oscilloscope did not arm"

Check:
- VISA connection: `visa.list_resources()`
- Trigger level: Set to visible signal amplitude
- Timebase range: Should encompass your signal
- Impedance: 1 MΩ or 50 Ω selected correctly

### Optimization Converges to Poor Solution

Try:
- Increase `window_min` / `window_max` range
- Increase `mu_min` / `mu_max` range
- Increase `num_measurements` for better averaging
- Check signal alignment on scope (may need `trigger_delay`)

### Filter Diverges (Error Grows)

Reduce `mu_max` (learning rate too aggressive):
```ini
mu_max = 0.9  # Instead of 1.9
```

### Measurement Noise Too High

Options:
- Increase `num_measurements` for better averaging
- Improve hardware shielding/grounding
- Select different timebase/sampling parameters
- Enable scope averaging in oscilloscope settings

## Advanced Usage

### Custom Signal Loading

```python
from pulse_optimizer_core import load_theoretical_signal

# Load and interpolate arbitrary CSV
signal, interp_signal, time = load_theoretical_signal(
    csv_path='my_waveform.csv',
    amplitude=0.5,
    target_length=6000,
    total_length_ns=8000
)
```

### Power Calibration

Convert optimized amplitude to laser power:

```python
from pulse_optimizer_core import rabi_to_laserpower

power_mw = rabi_to_laserpower(
    omega_mhz=100,
    dipole_moment=2.853e-29,
    cg_coefficient=0.1441,
    beam_waist_um=20
)
```

### Direct Filter API

```python
from pulse_optimizer_core import PositiveNLMS

# Create and run filter directly
filt = PositiveNLMS(order=20, mu=0.5)
output, error, weights = filt.run(desired_signal, input_matrix)

# Analyze convergence
error_db = 10 * np.log10(error**2 + 1e-12)
plt.plot(error_db)
plt.ylabel('Error (dB)')
plt.show()
```

## Performance Notes

### Typical Optimization Times

- Window search (3-50): ~5-10 minutes
- Per-window mu search (15 points): ~30 seconds each
- Total forward pass: ~10-15 minutes
- Re-measurement validation: ~5-10 minutes

### Memory Usage

- Signal arrays: ~100 MB for 6000-sample signals
- Filter history: ~50 MB per window optimization
- Typical total: <500 MB

## References & Related Work

### NLMS Algorithm
- Based on normalized least mean squares (NLMS) adaptive filtering
- Extended with positivity constraint for physical signals
- Reference: Haykin, S. "Adaptive Filter Theory" (5th ed.)

### Pulse Shaping in Quantum Optics
- Similar optimization techniques used for:
  - STIRAP (Stimulated Raman Adiabatic Passage)
  - Rabi oscillations
  - Composite pulses
  - AWG-based arbitrary waveform generation

## License & Attribution

Refactored from original code by Marina Llano Pinero (master's student).
Updated for current codebase by [Your Name].

## Contact & Support

For issues or feature requests, contact the laser control team or open an issue in the repository.
