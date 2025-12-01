# AWG Control Functions Guide (v2)

## Overview

This document describes the new `awg_control_functions_psh_v2.py` module, which provides a clean, well-structured replacement for the legacy `awg_control_functions_psh.py`.

### Key Improvements

- **Config-driven design**: Uses `AwgConfiguration` objects directly from `ExperimentalConfigs.py`
- **Clear separation of concerns**: Each function has a single responsibility
- **Better error handling**: Explicit error messages and validation
- **Improved documentation**: Comprehensive docstrings for all functions
- **Development mode support**: Can test logic without hardware
- **Type hints**: Full type annotations for clarity

---

## Main Entry Point

### `run_awg(awg_config, dev_mode=False)`

The primary function to configure and control the AWG.

**Usage:**

```python
from classes.ExperimentalConfigs import AwgConfiguration
from classes.Config import ExperimentConfigReader
from lab_control_functions.awg_control_functions_psh_v2 import run_awg

# Load configuration from file
config_reader = ExperimentConfigReader('configs/pulse_shaping_expt/awg_configs/ch1_2_config.ini')
awg_config = config_reader.get_awg_configuration()

# Run AWG configuration and control
awg = run_awg(awg_config, dev_mode=False)

# ... run your experiment ...

# Clean up
if awg:
    from lab_control_functions.awg_control_functions_psh_v2 import disconnect_awg
    disconnect_awg(awg)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `awg_config` | `AwgConfiguration` | - | Configuration object with all AWG settings |
| `dev_mode` | `bool` | `False` | If `True`, skip hardware communication (for testing) |

**Returns:**

- `WX218x_awg` object (if not in dev_mode)
- `None` (if in dev_mode)

---

## Configuration Object Structure

The `AwgConfiguration` object should contain:

| Attribute | Type | Description |
|-----------|------|-------------|
| `sample_rate` | `float` | Sample rate in Hz (e.g., `1e9` for 1 GHz) |
| `burst_count` | `int` | Number of bursts per trigger |
| `waveform_output_channels` | `List[str]` | Channels to output on (e.g., `['channel1', 'channel2']`) |
| `waveform_output_channel_lags` | `List[float]` | Timing lags in microseconds (e.g., `[0.015, 0, 0]`) |
| `marked_channels` | `List[str]` | Channels with markers enabled |
| `marker_width` | `float` | Marker pulse width in microseconds |
| `waveform_sequence` | `List[List[int]]` | Indices of waveforms for each channel (e.g., `[[0, 1], [2, 3]]`) |
| `waveforms` | `List[Waveform]` | Waveform objects to play |
| `interleave_waveforms` | `bool` | Whether to interleave waveforms (reserved for future use) |
| `waveform_stitch_delays` | `List[List[any]]` | Stitch delay configuration |

---

## Low-Level Functions

These functions can be used independently for more granular control:

### Connection Management

#### `connect_awg(reset=False)`

Connect to the AWG and initialize it.

```python
from lab_control_functions.awg_control_functions_psh_v2 import connect_awg

awg = connect_awg(reset=False)
print(f"Connected to: {awg.name}")
```

#### `disconnect_awg(awg)`

Safely disconnect from the AWG.

```python
from lab_control_functions.awg_control_functions_psh_v2 import disconnect_awg

disconnect_awg(awg)
```

---

### Configuration Functions

#### `configure_awg_general(awg, awg_config)`

Configure basic AWG settings (sample rate, output mode, coupling).

```python
configure_awg_general(awg, awg_config)
```

#### `configure_triggers(awg, awg_config)`

Set up trigger inputs and burst counts for all channels.

```python
configure_triggers(awg, awg_config)
```

---

### Offset Calculation

#### `calculate_channel_offsets(channel_lags, sample_rate)`

Convert timing lags to AWG sample offsets.

**Example:**

```python
from lab_control_functions.awg_control_functions_psh_v2 import calculate_channel_offsets

channel_lags = [0.015, 0.0, 0.0]  # in microseconds
sample_rate = 1e9  # 1 GHz
abs_offsets, rel_offsets = calculate_channel_offsets(channel_lags, sample_rate)

print(f"Absolute offsets: {abs_offsets}")  # e.g., [15000, 0, 0]
print(f"Relative offsets: {rel_offsets}")  # e.g., [0, 15000, 15000]
```

---

### Waveform Processing

#### `get_waveform_data(waveform, sample_rate, calibration_function=None, ...)`

Extract processed waveform data.

```python
from lab_control_functions.awg_control_functions_psh_v2 import get_waveform_data

wf_data = get_waveform_data(
    waveform=my_waveform,
    sample_rate=1e9,
    calibration_function=lambda x: x,  # identity
    constant_voltage=False,
    double_pass=True
)
print(f"Waveform samples: {len(wf_data)}")
```

#### `stitch_waveforms_for_channel(channel_waveforms, sample_rate, stitch_delays, ...)`

Concatenate multiple waveforms for a single channel.

```python
from lab_control_functions.awg_control_functions_psh_v2 import stitch_waveforms_for_channel
import numpy as np

channel_wfs = [wf1, wf2, wf3]
stitched = stitch_waveforms_for_channel(
    channel_waveforms=channel_wfs,
    sample_rate=1e9,
    stitch_delays=[],
    pad_length=100  # Add 100 sample padding
)
print(f"Stitched waveform length: {len(stitched)} samples")
```

#### `create_marker_waveform(waveform_length, marker_positions, ...)`

Generate a marker waveform.

```python
from lab_control_functions.awg_control_functions_psh_v2 import create_marker_waveform

marker = create_marker_waveform(
    waveform_length=10000,
    marker_positions=[1000, 5000],  # Start positions
    marker_levels=(0.0, 1.2),
    marker_width=50,
    n_pad_left=100,
    n_pad_right=100
)
print(f"Marker waveform: {len(marker)} samples")
```

---

### Data Alignment

#### `ensure_alignment(waveform_data, marker_data, align_to=16)`

Pad all waveforms to aligned length (multiple of `align_to` samples).

```python
from lab_control_functions.awg_control_functions_psh_v2 import ensure_alignment

wf_data = [channel1_wf, channel2_wf, channel3_wf]
marker_data = [0, 0, 1, 1, 0, ...]

aligned_wf, aligned_marker = ensure_alignment(wf_data, marker_data, align_to=16)
```

---

### Writing to Hardware

#### `write_waveforms_to_awg(awg, channels, waveform_data, relative_offsets)`

Send waveforms to AWG channels with time-domain offsets.

```python
from lab_control_functions.awg_control_functions_psh_v2 import write_waveforms_to_awg

write_waveforms_to_awg(
    awg=awg,
    channels=['channel1', 'channel2', 'channel3'],
    waveform_data=[ch1_data, ch2_data, ch3_data],
    relative_offsets=[0, 15000, 15000]
)
```

#### `write_markers_to_awg(awg, marked_channels, marker_data, marker_width)`

Configure markers on specified channels.

```python
from lab_control_functions.awg_control_functions_psh_v2 import write_markers_to_awg

write_markers_to_awg(
    awg=awg,
    marked_channels=['channel1', 'channel2'],
    marker_data=marker_waveform,
    marker_width=0.1  # microseconds
)
```

#### `enable_awg_outputs(awg, channels, gain=2.0)`

Enable output and set gain on all channels.

```python
from lab_control_functions.awg_control_functions_psh_v2 import enable_awg_outputs

enable_awg_outputs(
    awg=awg,
    channels=['channel1', 'channel2', 'channel3'],
    gain=2.0
)
```

---

## Configuration File Format

The `ch1_2_config.ini` file should follow this structure:

```ini
[metadata]
date = 05/05/25
time = 18:37

[general]
sample rate = 1000000000.0
burst count = 1
waveform output channels = channel1, channel2, channel3
waveform output channel lags = 0.015, 0, 0
marked channels = channel1, channel2, channel3
marker width = 0.1

[waveforms sequence]
waveform sequence = "[0, 1],[2, 3], [4]"
waveform stitch delays = "[-1,[]],[-1,[]], [-1,[]]"
interleave waveforms = True

[waveforms]
[[0]]
modulation frequency = 0
phases = ,
filename = waveforms/marina/zeros/zero_1.csv

[[1]]
modulation frequency = 126000000
phases = ,
filename = waveforms/marina/zeros/zero_1.csv

# ... more waveforms ...
```

---

## Examples

### Example 1: Basic AWG Setup and Run

```python
from classes.ExperimentalConfigs import AwgConfiguration, Waveform
from lab_control_functions.awg_control_functions_psh_v2 import run_awg, disconnect_awg

# Create configuration (normally loaded from file)
waveforms = [
    Waveform('path/to/wf1.csv', 1e6, []),
    Waveform('path/to/wf2.csv', 2e6, []),
]

awg_config = AwgConfiguration(
    waveform_sequence=[[0], [1]],
    waveforms=waveforms,
    interleave_waveforms=False,
    waveform_stitch_delays=[],
    sample_rate=1e9,
    burst_count=1,
    waveform_output_channels=['channel1', 'channel2'],
    waveform_output_channel_lags=[0.0, 0.0],
    marked_channels=['channel1', 'channel2'],
    marker_width=0.1
)

# Run configuration
awg = run_awg(awg_config, dev_mode=False)

# Do your experiment...

# Cleanup
if awg:
    disconnect_awg(awg)
```

### Example 2: Development Mode Testing

Test your configuration without hardware:

```python
from lab_control_functions.awg_control_functions_psh_v2 import run_awg

# Same setup as Example 1...

# Test without hardware
run_awg(awg_config, dev_mode=True)
print("Configuration validated successfully!")
```

### Example 3: Manual Waveform Processing

Process waveforms step-by-step:

```python
from lab_control_functions.awg_control_functions_psh_v2 import (
    calculate_channel_offsets,
    stitch_waveforms_for_channel,
    create_marker_waveform,
    ensure_alignment
)

# Calculate offsets
abs_offsets, rel_offsets = calculate_channel_offsets(
    [0.015, 0.0, 0.0],
    1e9
)

# Process waveforms
wf_data = []
for ch_wfs in awg_config.waveform_sequence:
    channel_waveforms = [awg_config.waveforms[i] for i in ch_wfs]
    stitched = stitch_waveforms_for_channel(
        channel_waveforms,
        awg_config.sample_rate
    )
    wf_data.append(stitched)

# Create markers
marker = create_marker_waveform(
    len(wf_data[0]),
    [1000, 5000],
    marker_width=50
)

# Align data
wf_aligned, marker_aligned = ensure_alignment(wf_data, marker, align_to=16)
```

---

## Migration from Old Code

If you're migrating from `awg_control_functions_psh.py`:

### Old Way
```python
from lab_control_functions.awg_control_functions_psh import run_awg

run_awg(
    awg_config=config,
    dev_mode=dev_mode
)
```

### New Way (Same interface!)
```python
from lab_control_functions.awg_control_functions_psh_v2 import run_awg

awg = run_awg(
    awg_config=config,
    dev_mode=dev_mode
)
```

The primary entry point remains the same, so migration is straightforward.

---

## Constants

Common constants defined in the module:

| Constant | Value | Description |
|----------|-------|-------------|
| `MARKER_LOW` | `0.0` | Low level for marker output |
| `MARKER_HIGH` | `1.2` | High level for marker output |
| `MARKER_WF_LOW` | `0.0` | Low level for marker waveform data |
| `MARKER_WF_HIGH` | `1.0` | High level for marker waveform data |
| `US_TO_S` | `1e-6` | Conversion factor: microseconds to seconds |

---

## Error Handling

The module provides clear error messages for common issues:

```python
try:
    awg = run_awg(awg_config, dev_mode=False)
except Exception as e:
    print(f"AWG configuration failed: {e}")
    # Handle error...
```

---

## Tips and Best Practices

1. **Always use `dev_mode=True` for initial testing** to validate your configuration without hardware.

2. **Check console output** for detailed debug information about offsets, waveforms, and marker positions.

3. **Ensure alignment** is properly handled before writing to hardware (done automatically in `run_awg`).

4. **Verify channel lags** are in microseconds and represent realistic timing delays.

5. **Use the configuration file** for all parameters rather than hardcoding values.

6. **Clean up resources** by calling `disconnect_awg()` when finished.

---

## Troubleshooting

### Issue: "No AWG instrument can be found"
- Check that AWG is powered on and connected via GPIB/USB
- Verify VISA resource manager can detect it: `pyvisa-info`

### Issue: "Channel count mismatch"
- Ensure `waveform_output_channels` has same length as `waveform_data`
- Check `waveform_sequence` indices are valid

### Issue: "Alignment failed"
- All waveforms must be aligned to multiples of 16 (done automatically)
- Check for empty waveforms

### Issue: "More markers required than supported"
- AWG only supports 2 markers; if >2 requested, first 2 are used

---

## API Reference Summary

**Connection:**
- `connect_awg(reset)`
- `disconnect_awg(awg)`

**Configuration:**
- `configure_awg_general(awg, awg_config)`
- `configure_triggers(awg, awg_config)`

**Processing:**
- `calculate_channel_offsets(channel_lags, sample_rate)`
- `get_waveform_data(waveform, sample_rate, ...)`
- `stitch_waveforms_for_channel(channel_waveforms, sample_rate, ...)`
- `create_marker_waveform(waveform_length, marker_positions, ...)`
- `find_marker_positions(marker_data)`

**Writing:**
- `write_waveforms_to_awg(awg, channels, waveform_data, relative_offsets)`
- `write_markers_to_awg(awg, marked_channels, marker_data, marker_width)`
- `enable_awg_outputs(awg, channels, gain)`

**Utility:**
- `ensure_alignment(waveform_data, marker_data, align_to)`

**Main Entry Point:**
- `run_awg(awg_config, dev_mode)`

---

## See Also

- `ExperimentalConfigs.py` - Configuration object definitions
- `WX218x_awg.py` - Low-level AWG driver
- Configuration files: `configs/pulse_shaping_expt/awg_configs/`
