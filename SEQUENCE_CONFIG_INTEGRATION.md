# Sequence Configuration Integration

## Overview
The configuration system has been updated to include Sequence objects as part of the experiment configuration. Sequences are now loaded directly from the config files and included in the MotFluoresceConfiguration object, rather than being handled separately.

## Changes Made

### 1. MotFluoresceConfiguration (ExperimentalConfigs.py)
- **Added**: `sequence: Sequence` parameter to `__init__` (required)
- **Purpose**: Sequence is now a core part of the experiment configuration
- **Updated docstring**: Documents the sequence as a key attribute
- **Backward compatibility**: Maintained through optional camera, scope, AWG configs

### 2. ExperimentConfigReader (Config.py)
- **Updated**: `get_mot_flourescence_configuration()` method
- **New logic**:
  1. Reads `sequence_path` from the `[configs]` section of the experiment config file
  2. Uses `SequenceReader` to load the sequence from the specified file
  3. Passes the loaded sequence to `MotFluoresceConfiguration` constructor
- **Config file requirement**: Experiment config files must have:
  ```ini
  [configs]
  sequence_path = "path/to/sequence/config.ini"
  ```

### 3. MotFluoresceExperiment (ExperimentalRunner.py)
- **Modified**: Constructor signature changed
- **Before**:
  ```python
  def __init__(self, daq_controller:DAQ_controller, sequence:Sequence,
               mot_fluoresce_configuration:MotFluoresceConfiguration, ...)
  ```
- **After**:
  ```python
  def __init__(self, daq_controller:DAQ_controller,
               mot_fluoresce_configuration:MotFluoresceConfiguration,
               sequence:Sequence = None, ...)
  ```
- **Backward compatibility**: 
  - If `sequence=None`, uses sequence from `mot_fluoresce_configuration.sequence`
  - Can still pass sequence explicitly for backward compatibility with UI code
  - All keyword arguments work as before

### 4. MotFluoresceSweepExperiment (ExperimentalRunner.py)
- **Updated**: Call to `MotFluoresceExperiment` constructor changed to use keyword arguments
- Changed from positional to keyword arguments for clarity and compatibility

## Data Flow

### Old Flow:
```
Experiment Config File
    ↓
ExperimentConfigReader.get_mot_flourescence_configuration()
    ↓
MotFluoresceConfiguration (without sequence)
    ↓
UI (loads sequence separately)
    ↓
MotFluoresceExperiment(daq_controller, sequence, config)
```

### New Flow:
```
Experiment Config File
    ├── [configs] section with sequence_path
    ↓
ExperimentConfigReader.get_mot_flourescence_configuration()
    ├── Loads sequence using SequenceReader
    ↓
MotFluoresceConfiguration (includes sequence)
    ↓
UI (uses config.sequence or provides override)
    ↓
MotFluoresceExperiment(daq_controller, mot_fluoresce_configuration, sequence=None)
    └── Uses config.sequence since sequence=None
```

## Configuration File Update

Experiment config files now must include sequence path in the `[configs]` section:

```ini
experiment_type = "MOT Fluorescence sweep"
save location = "C:\experiment_data"
mot reload = 1000
iterations = 7

use_cam = False
use_scope = True
use_awg = True

[configs]
sequence_path = "configs/experiments/sequence/mysequence.ini"
awg_path = "configs/experiments/awg/myawg.ini"
scope_path = "configs/experiments/scope/myscope.ini"
sweep_path = "configs/experiments/sweeps/mysweep.ini"
```

## Backward Compatibility

✅ **Maintained compatibility with existing code**:
- UI code that passes `sequence` parameter explicitly still works
- MotFluoresceExperiment can receive sequence from either source:
  1. Explicitly passed (old way, still supported)
  2. From config (new way, preferred)
- Keyword arguments throughout ensure flexibility

## Usage Examples

### Loading an experiment configuration (Config.py):
```python
config_reader = ExperimentConfigReader("path/to/experiment.ini")
config = config_reader.get_mot_flourescence_configuration()

# Config now has:
config.sequence  # Loaded from [configs] sequence_path
config.awg_config
config.scope_config
config.cam_config
```

### Creating an experiment (ExperimentalRunner.py):
```python
# Method 1: Use sequence from config (preferred)
experiment = MotFluoresceExperiment(
    daq_controller=daq,
    mot_fluoresce_configuration=config
)

# Method 2: Override with explicit sequence (for backward compatibility)
experiment = MotFluoresceExperiment(
    daq_controller=daq,
    mot_fluoresce_configuration=config,
    sequence=custom_sequence
)
```

## Benefits

1. **Unified Configuration**: All experiment parameters (sequence, AWG, scope, camera) loaded from a single config file hierarchy
2. **Consistency**: Sequence loading follows the same pattern as other configurations
3. **Maintainability**: Cleaner separation between configuration and experiment logic
4. **CONFIG_GUIDE Alignment**: Fully implements the documented configuration hierarchy
5. **Backward Compatibility**: Existing code continues to work without changes

## Testing Recommendations

1. Test loading experiment config files that include `sequence_path`
2. Verify MotFluoresceExperiment creates correctly without explicit sequence parameter
3. Test backward compatibility by passing sequence explicitly
4. Verify sweep experiments still work with new parameter ordering
5. Check that UI-created experiments work correctly

## Files Modified

- `classes/ExperimentalConfigs.py` - Added sequence parameter to MotFluoresceConfiguration
- `classes/Config.py` - Updated get_mot_flourescence_configuration() to load sequence
- `classes/ExperimentalRunner.py` - Updated MotFluoresceExperiment signature and sweep experiment call
- Experiment config files should include sequence_path in [configs] section
