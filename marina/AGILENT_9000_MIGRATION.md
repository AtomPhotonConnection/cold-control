# AWG Pulse Optimization - Agilent 9000 Series Migration Guide

This document describes the changes made to migrate the pulse optimization system
from Keysight 3000T oscilloscope to Agilent Infiniium 9000 series oscilloscope.

**Date:** February 6, 2026  
**Status:** Complete and tested with Agilent 9000 (Resource ID: `USB0::0x2A8D::0x900E::MY53450121::0::INSTR`)

---

## Overview of Changes

The pulse optimization system has been refactored to use the Agilent Infiniium 9000 
series oscilloscope instead of the Keysight 3000T (3104A). The core optimization 
algorithms remain unchanged; only the oscilloscope communication layer has been updated.

### Hardware Change

| Aspect | Old | New |
|--------|-----|-----|
| **Oscilloscope** | Keysight 3104A (InfiniiVision 3000T) | Agilent Infiniium 9000 Series |
| **Driver/API** | `keysight_3104A.OscilloscopeManager` | `agilent_9000.OscilloscopeManager` |
| **Vendor/Product IDs** | `0x0957::0x17A0` | `0x2A8D::0x900E` |
| **Example Resource ID** | `USB0::0x0957::0x17A0::MY54280441::0::INSTR` | `USB0::0x2A8D::0x900E::MY53450121::0::INSTR` |
| **AWG** | Keysight WX218x (unchanged) | Keysight WX218x (unchanged) |

---

## Files Changed

### Direct Imports Updated

The following files have been updated to import from `agilent_9000` instead of `keysight_3104A`:

1. **pulse_optimizer_core.py**
   - Updated docstrings to reference agilent_9000
   - No functional code changes

2. **optimize_awg_pulse_forward.py**
   - Changed: `from instruments.keysight_3104A import OscilloscopeManager`
   - To: `from instruments.agilent_9000 import OscilloscopeManager`
   - Updated docstring in `connect_scope()` method

3. **optimize_awg_pulse_inverted.py**
   - Same changes as forward optimizer

4. **OPTIMIZATION_EXAMPLES.py**
   - Updated all example code to use correct Agilent 9000 resource ID format

5. **verify_setup.py**
   - Updated import and diagnostics to reference agilent_9000

### Configuration Files Updated

6. **config_forward.ini**
   - Updated `scope_id = USB0::0x2A8D::0x900E::MY53450121::0::INSTR`
   - Added note about resource ID format

7. **config_inverted.ini**
   - Same scope_id update as config_forward.ini

### Documentation Updated

8. **PULSE_OPTIMIZER_README.md**
   - Hardware requirements section updated
   - References Agilent Infiniium 9000 Series

9. **REFACTORING_SUMMARY.md**
   - Updated API references to agilent_9000

10. **FILE_LISTING.md**
    - Updated dependency references

11. **QUICKSTART.py**
    - Updated imports and example resource IDs

---

## API Compatibility

### Good News: No Interface Changes Required

The Agilent 9000 `OscilloscopeManager` class has the same public interface as the 
Keysight 3104A version, so **no changes to user code are needed** beyond updating imports.

### Key Methods (Same Interface)

```python
# Connection
scope = OscilloscopeManager(scope_id="USB0::0x2A8D::0x900E::MY53450121::0::INSTR")
scope.is_connected()  # Returns bool
scope.quit()  # Cleanup

# Configuration
scope.configure_scope(data_chs, samp_rate, timebase_range, high_impedance)
scope.configure_trigger(trigger_channel, trigger_level, trigger_slope)

# Acquisition
scope.set_to_digitize(channels)
scope.arm_scope(max_acq_wait_sec)
scope.wait_for_acquisition(max_acq_wait_sec)
scope.read_slow_return_data(channels)

# Data Management
data = scope.save_data(dataframe, filename, window)
scope.csv_analysis(filename)
```

All method signatures match between the two implementations.

---

## Hardware Identification

### Finding Your Agilent 9000 Oscilloscope

#### Step 1: List Available VISA Devices

```python
import visa
rm = visa.ResourceManager()
devices = rm.list_resources()
print(devices)
```

#### Step 2: Identify the Agilent 9000

Agilent Infiniium 9000 series devices appear with resource ID format:
```
USB0::0x2A8D::0x900E::<SERIAL>::0::INSTR
```

The key identifiers are:
- **Vendor ID:** `0x2A8D`
- **Product ID:** `0x900E`
- **Serial:** Your specific scope's serial number

Example from actual system:
```
USB0::0x2A8D::0x900E::MY53450121::0::INSTR
```

#### Step 3: Update Your Configuration

Edit `config_forward.ini` or `config_inverted.ini`:

```ini
[Hardware]
scope_id = USB0::0x2A8D::0x900E::MY53450121::0::INSTR   # Replace MY53450121 with your serial
```

#### Verification

Run the setup verification script:
```bash
python marina/verify_setup.py config_forward.ini
```

This will confirm the Agilent 9000 is connected and accessible.

---

## Agilent 9000 Specific Features

### Hardware Averaging (New)

The Agilent 9000 `OscilloscopeManager` includes a new method for hardware-based averaging:

```python
scope.read_slow_return_data_avgd(channels=[1, 2], averages=16)
```

This is more efficient than collecting multiple measurements and averaging in software,
because the oscilloscope performs the averaging on waveforms matching the acquisition mode.

**Benefit:** Reduced noise with fewer scope triggers.

### Improved Timebase Control

Agilent 9000 has better precision for timebase configuration:

```python
# Set timebase range (start, stop) in seconds
scope.configure_scope(
    data_chs={1: (-0.5, 0.5)},
    timebase_range=(-2e-6, 2e-6),  # ±2 microseconds
    samp_rate=1e9
)
```

---

## Differences from Keysight 3000T

### SCPI Command Changes

| Aspect | Keysight 3000T | Agilent 9000 |
|--------|---|---|
| Acquisition mode | `:ACQuire:TYPE HRESOLUTION` | `:ACQuire:MODE RTIMe` + `:ACQuire:HRESolution ON` |
| Digitize command | `:DIGitize;*OPC?` | `:DIGitize CHANnel1,CHANnel2;*OPC?` |
| Trigger source | `:TRIGGER:EDGE:SOURCE CHANNEL` | `:TRIGger:EDGE:SOURce CHANnel` |
| Impedance options | `1meg`, `50ohm` | `ONEMeg`, `FIFTy` |

**Impact:** These differences are abstracted in the OscilloscopeManager classes, 
so end-user code remains the same.

### Command Timing

Agilent 9000 may require slightly longer processing time for some operations:
- Default COMMAND_DELAY_SEC set to 0.05 seconds
- Still much faster than human-scale operations

**Impact:** No changes needed; the delay is handled internally.

---

## Troubleshooting

### "Oscilloscope did not arm"

**Cause:** Agilent 9000 wasn't found or wasn't ready.

**Fix:**
1. Verify connection: `python -c "import visa; print(visa.ResourceManager().list_resources())"`
2. Check resource ID matches your device (should contain `0x2A8D::0x900E`)
3. Update `config_forward.ini` with correct resource ID (including your serial number)
4. Run: `python marina/verify_setup.py config_forward.ini`

### "Trigger level out of range"

**Cause:** Trigger level set outside the configured channel voltage range.

**Fix:**
```ini
# In config_forward.ini:
[Oscilloscope]
trigger_level = 0.2  # Must be within ±0.5V if channel range is (-0.5, 0.5)
```

### "No data collected from channel"

**Cause:** Channel might be disabled or not properly triggered.

**Fix:**
1. Verify signal is visible on scope before running
2. Check trigger is in Auto or Normal mode
3. Ensure `trigger_slope` matches signal direction (+ for rising, - for falling)

### "Acquisition timeout"

**Cause:** Digitize command took longer than expected.

**Fix:**
```python
# Increase timeouts
scope.set_to_digitize(channels)  # Default waits ~5 seconds
scope.wait_for_acquisition(max_acq_wait_sec=20)  # Increase from default
```

---

## Backward Compatibility

### Old Keysight System Still Available

The original `keysight_3104A.py` file remains in the repository for backward compatibility:

```python
# Old code still works (deprecated but functional)
from instruments.keysight_3104A import OscilloscopeManager
scope = OscilloscopeManager("USB0::0x0957::0x17A0::...")
```

**Recommendation:** Update to use `agilent_9000` for new projects.

### Migration Path for Existing Code

If you have existing scripts using keysight_3104A:

```python
# Old
from instruments import keysight_3104A as osc
scope = osc.OscilloscopeManager(...)

# New
from instruments.agilent_9000 import OscilloscopeManager
scope = OscilloscopeManager(...)
```

The method calls are identical, so only import and initialization need updating.

---

## Testing the Migration

### Quick Test

```bash
# Verify setup
python marina/verify_setup.py marina/config_forward.ini

# Should see:
#   ✓ Oscilloscope connection: OK
#   ✓ Calibration Files: (all files present)
```

### Full Optimization Test

```bash
# Run optimization with verbose output
import logging
logging.basicConfig(level=logging.DEBUG)

from marina.optimize_awg_pulse_forward import ForwardOptimizer
optimizer = ForwardOptimizer('marina/config_forward.ini')
optimizer.run()
```

### Agilent 9000 Specific Test

```python
# Test hardware averaging feature
from instruments.agilent_9000 import OscilloscopeManager

scope = OscilloscopeManager("USB0::0x2A8D::0x900E::MY53450121::0::INSTR")

# Configure for averaging
scope.configure_scope({1: (-0.5, 0.5)})
scope.configure_trigger(1, 0.2)
scope.arm_scope()

# Acquire with averaging (16 scope triggers)
data = scope.read_slow_return_data_avgd(channels=[1], averages=16)
print(f"Acquired {len(data)} samples with hardware averaging")
```

---

## Summary of Changes

### What Changed
- ✓ Oscilloscope driver: `keysight_3104A` → `agilent_9000`
- ✓ Vendor/Product IDs: `0x0957::0x17A0` → `0x2A8D::0x900E`
- ✓ Resource ID examples updated throughout
- ✓ Configuration templates updated
- ✓ Documentation updated
- ✓ Example code updated

### What Stayed the Same
- ✓ Optimization algorithms
- ✓ Configuration file format (.ini)
- ✓ AWG control (WX218x)
- ✓ Command-line interface
- ✓ Output format and plots
- ✓ Public API interfaces

### Migration Effort
- **For new setups:** ~5 minutes (copy config, update serial number, run verify)
- **For existing code conversion:** ~15 minutes (change imports, update resource ID)
- **Testing:** ~10 minutes (run verify_setup.py + sample optimization)

---

## Contact & Support

For issues with the Agilent 9000 migration:

1. **Check scope connection:** Run `verify_setup.py`
2. **Review hardware IDs:** 
   ```bash
   python -c "import visa; print(visa.ResourceManager().list_resources())"
   ```
3. **Check configuration:** Verify scope_id in `config_forward.ini` matches your device (should contain your serial)
4. **Enable debug logging:** Add `logging.basicConfig(level=logging.DEBUG)` to see detailed SCPI commands
5. **Verify correct format:** Your resource ID should be `USB0::0x2A8D::0x900E::<YOUR_SERIAL>::0::INSTR`

---

**Last updated:** February 6, 2026  
**System version:** 2.0 (Agilent 9000 compatible)  
**Status:** Fully tested with Agilent Infiniium 9000 Series  
**Tested Resource ID:** `USB0::0x2A8D::0x900E::MY53450121::0::INSTR`
