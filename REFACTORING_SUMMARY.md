# Configuration System Refactoring Summary

## Overview
The configuration system has been restructured to align with the CONFIG_GUIDE.md specification. Configuration files are now read as separate, modular objects that are composed into experiment configurations.

## Key Changes

### 1. New Configuration Classes (ExperimentalConfigs.py)

#### CameraConfiguration
- **Purpose**: Encapsulates camera-specific settings
- **Properties**: cam_exposure, cam_gain, camera_trigger_channel, camera_trigger_level, camera_pulse_width, save_images
- **Usage**: Instantiated for MOT fluorescence experiments with `use_cam=True`

#### ScopeConfiguration
- **Purpose**: Encapsulates oscilloscope settings
- **Properties**: trigger_channel, trigger_level, sample_rate, time_range, data_channels
- **Usage**: Instantiated for MOT fluorescence experiments with `use_scope=True`

#### SweepConfiguration
- **Purpose**: Encapsulates sweep parameters
- **Properties**: sweep_type (str), num_shots (int), sweep_parameters (dict)
- **Supports**: Two sweep types: "awg_sequence" and "mot_imaging"

### 2. Refactored MotFluoresceConfiguration

**Before**: Used embedded dictionaries for camera, scope, and AWG settings:
```python
MotFluoresceConfiguration(..., cam_dict={...}, scope_dict={...}, awg_dict={...})
```

**After**: Uses structured configuration objects:
```python
MotFluoresceConfiguration(..., 
    cam_config=CameraConfiguration(...),
    scope_config=ScopeConfiguration(...),
    awg_config=AwgConfiguration(...)
)
```

#### Backward Compatibility
Properties added to maintain compatibility with existing code:
- `cam_exposure`, `cam_gain`, `camera_trigger_channel`, `camera_trigger_level`, `camera_pulse_width`, `save_images` → access CameraConfiguration
- `scope_trigger_channel`, `scope_trigger_level`, `scope_sample_rate`, `scope_time_range`, `scope_data_channels` → access ScopeConfiguration
- `awg_config_single` → returns None (deprecated feature)
- `default_sweep_config_path` → backward compatibility property

### 3. Updated ExperimentConfigReader (Config.py)

#### get_mot_flourescence_configuration()
**Changes**:
- Now instantiates CameraConfiguration, ScopeConfiguration objects instead of creating dictionaries
- Passes these objects directly to MotFluoresceConfiguration constructor
- Cleaner, more maintainable code with better separation of concerns

#### get_mot_flourescence_configuration_sweep()
**Changes**:
- Previously returned: `(sweep_type, num_shots, sweep_dict)`
- Now returns: `SweepConfiguration` object
- Clients access sweep parameters via `.sweep_type`, `.num_shots`, `.sweep_parameters`

### 4. Updated UI Code (Experimental_UI.py)

**Line 342-352**: Updated to work with new SweepConfiguration object
```python
# Old: parameter_list = (..., parameter_list[0], parameter_list[1], parameter_list[2])
# New: sweep_config_obj.sweep_type, sweep_config_obj.num_shots, sweep_config_obj.sweep_parameters
```

### 5. Deprecated Classes

The following classes are marked as deprecated but retained for backward compatibility:
- `SingleExperimentConfig` - use MotFluoresceConfiguration instead
- `AWGSequenceConfiguration` - use AwgConfiguration instead

Both include deprecation warnings when instantiated.

## Benefits

1. **Better Organization**: Each configuration concern is in its own class
2. **Type Safety**: IDE autocomplete and type checking now work better
3. **Maintainability**: Changes to one configuration type don't affect others
4. **Scalability**: Easy to extend with new configuration types (e.g., TDC configurations)
5. **CONFIG_GUIDE Alignment**: Directly matches the documented configuration hierarchy

## Migration Guide for Existing Code

### If you're creating a MotFluoresceConfiguration:

**Before**:
```python
config = MotFluoresceConfiguration(
    save_location="...",
    mot_reload=1000,
    iterations=10,
    use_cam=True,
    use_scope=True,
    use_awg=True,
    cam_dict={"cam_exposure": 100, "cam_gain": 50, ...},
    scope_dict={"trigger_channel": 1, "trigger_level": 2.5, ...},
    awg_dict={"config_path_full": "...", "awg_config": ...}
)
```

**After**:
```python
cam_config = CameraConfiguration(cam_exposure=100, cam_gain=50, ...)
scope_config = ScopeConfiguration(trigger_channel=1, trigger_level=2.5, ...)
awg_config = AwgConfiguration(...)

config = MotFluoresceConfiguration(
    save_location="...",
    mot_reload=1000,
    iterations=10,
    use_cam=True,
    use_scope=True,
    use_awg=True,
    cam_config=cam_config,
    scope_config=scope_config,
    awg_config=awg_config
)
```

### If you're reading sweep configurations:

**Before**:
```python
sweep_type, num_shots, sweep_dict = ExperimentConfigReader(fname).get_mot_flourescence_configuration_sweep()
```

**After**:
```python
sweep_config = ExperimentConfigReader(fname).get_mot_flourescence_configuration_sweep()
# Access via:
sweep_config.sweep_type
sweep_config.num_shots
sweep_config.sweep_parameters
```

## Files Modified

- `classes/ExperimentalConfigs.py` - New classes and refactored existing ones
- `classes/Config.py` - Updated imports and reader methods
- `UI_classes/Experimental_UI.py` - Updated to use new SweepConfiguration
- (ExperimentalRunner.py) - No changes needed due to backward compatibility

## Testing

To verify the refactoring:
1. Run: `python3 -m py_compile classes/ExperimentalConfigs.py classes/Config.py UI_classes/Experimental_UI.py`
2. Load a MOT fluorescence experiment config file through the UI
3. Run a sweep experiment to verify SweepConfiguration is working correctly
4. Check that backward compatibility properties work for existing code

## Next Steps

1. Update any custom experiment configuration readers to create objects instead of dictionaries
2. Remove usage of deprecated classes (SingleExperimentConfig, AWGSequenceConfiguration)
3. Consider extending with additional configuration types (DaqConfiguration, SequenceConfiguration wrappers)
