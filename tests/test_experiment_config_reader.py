"""Tests for the ExperimentConfigReader with both old and new config formats."""

import os
import shutil
import sys
import tempfile
import warnings
from pathlib import Path
from unittest.mock import patch

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set the config root so resolve_config_path can resolve relative paths
os.environ["COLD_CONTROL_CONFIG_ROOT"] = str(PROJECT_ROOT)

from classes.config_readers import ExperimentConfigReader  # noqa: E402
from classes.experimental_configs import (  # noqa: E402
    AwgConfiguration,
    MotFluoresceConfiguration,
    MotFluoresceConfigurationSweep,
    ScopeConfiguration,
)

NEW_FORMAT_CONFIG = str(
    PROJECT_ROOT / "configs" / "pulse_shaping_expt" / "single_shot" / "expt_config_feb26.ini"
)
NEW_FORMAT_SWEEP = str(
    PROJECT_ROOT / "configs" / "pulse_shaping_expt" / "sweeps" / "feb26_sweep_level.ini"
)


# ---------------------------------------------------------------------------
# New-format experiment config tests
# ---------------------------------------------------------------------------


def test_new_format_loads_mot_fluorescence():
    """New-format experiment config returns a MotFluoresceConfiguration."""
    reader = ExperimentConfigReader(NEW_FORMAT_CONFIG)
    config = reader.get_correct_config()

    assert isinstance(config, MotFluoresceConfiguration), (
        f"Expected MotFluoresceConfiguration, got {type(config)}"
    )


def test_new_format_has_scope_config():
    """New-format config produces a ScopeConfiguration (not a dict)."""
    reader = ExperimentConfigReader(NEW_FORMAT_CONFIG)
    config = reader.get_correct_config()

    assert isinstance(config, MotFluoresceConfiguration)
    assert config.use_scope is True, "use_scope should be True (scope_config key present)"
    assert isinstance(config.scope_config, ScopeConfiguration), (
        f"Expected ScopeConfiguration, got {type(config.scope_config)}"
    )
    assert config.scope_config.trigger_channel == 1
    assert config.scope_config.sample_rate == 50e6


def test_new_format_has_awg_config():
    """New-format config produces an AwgConfiguration (not a dict)."""
    reader = ExperimentConfigReader(NEW_FORMAT_CONFIG)
    config = reader.get_correct_config()

    assert isinstance(config, MotFluoresceConfiguration)
    assert config.use_awg is True, "use_awg should be True (awg_config key present)"
    assert isinstance(config.awg_config, AwgConfiguration), (
        f"Expected AwgConfiguration, got {type(config.awg_config)}"
    )
    assert config.awg_config.sample_rate > 0


def test_new_format_no_camera():
    """New-format config with no camera_settings has use_cam=False."""
    reader = ExperimentConfigReader(NEW_FORMAT_CONFIG)
    config = reader.get_correct_config()

    assert isinstance(config, MotFluoresceConfiguration)
    assert config.use_cam is False


def test_new_format_sequence_config_path():
    """New-format config stores the sequence_config_path."""
    reader = ExperimentConfigReader(NEW_FORMAT_CONFIG)
    config = reader.get_correct_config()

    assert isinstance(config, MotFluoresceConfiguration)
    assert config.sequence_config_path is not None
    assert "readout_with_MOTC" in config.sequence_config_path


def test_new_format_backward_compat_properties():
    """Backward-compatible property aliases on MotFluoresceConfiguration work."""
    reader = ExperimentConfigReader(NEW_FORMAT_CONFIG)
    config = reader.get_correct_config()

    assert isinstance(config, MotFluoresceConfiguration)
    assert config.scope_config is not None
    # These properties delegate to scope_config.*
    assert config.scope_trigger_channel == config.scope_config.trigger_channel
    assert config.scope_trigger_level == config.scope_config.trigger_level
    assert config.scope_sample_rate == config.scope_config.sample_rate
    assert config.scope_time_range == config.scope_config.time_range
    assert config.scope_data_channels == config.scope_config.data_channels


def test_get_sequence_from_experiment_config():
    """ExperimentConfigReader.get_sequence() loads a Sequence from the experiment config."""
    reader = ExperimentConfigReader(NEW_FORMAT_CONFIG)
    sequence = reader.get_sequence()

    # Sequence should have been loaded successfully
    assert sequence is not None
    assert hasattr(sequence, "n_samples")
    assert hasattr(sequence, "t_step")


# ---------------------------------------------------------------------------
# New-format sweep config tests
# ---------------------------------------------------------------------------


def _mock_rescale_csv(self, rabi, csv_in, csv_out, normalised=True):
    """Mock rescale_csv that just copies the input CSV to the output path."""
    Path(csv_out).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(csv_in, csv_out)


@patch("classes.rabi_voltage_converter.RabiFreqVoltageConverter.rescale_csv", _mock_rescale_csv)
@patch(
    "classes.rabi_voltage_converter.RabiFreqVoltageConverter.__init__", lambda self, *a, **kw: None
)
def test_new_format_sweep_loads():
    """New self-contained sweep config returns a MotFluoresceConfigurationSweep."""
    reader = ExperimentConfigReader(NEW_FORMAT_SWEEP)
    config = reader.get_correct_config()

    assert isinstance(config, MotFluoresceConfigurationSweep), (
        f"Expected MotFluoresceConfigurationSweep, got {type(config)}"
    )


@patch("classes.rabi_voltage_converter.RabiFreqVoltageConverter.rescale_csv", _mock_rescale_csv)
@patch(
    "classes.rabi_voltage_converter.RabiFreqVoltageConverter.__init__", lambda self, *a, **kw: None
)
def test_new_format_sweep_has_base_config():
    """Sweep config's base_config is a valid MotFluoresceConfiguration."""
    reader = ExperimentConfigReader(NEW_FORMAT_SWEEP)
    config = reader.get_correct_config()

    assert isinstance(config, MotFluoresceConfigurationSweep)
    assert isinstance(config.base_config, MotFluoresceConfiguration)
    assert config.base_config.use_scope is True
    assert config.base_config.use_awg is True


@patch("classes.rabi_voltage_converter.RabiFreqVoltageConverter.rescale_csv", _mock_rescale_csv)
@patch(
    "classes.rabi_voltage_converter.RabiFreqVoltageConverter.__init__", lambda self, *a, **kw: None
)
def test_new_format_sweep_has_sequence():
    """Sweep config's base_sequence is a loaded Sequence object."""
    reader = ExperimentConfigReader(NEW_FORMAT_SWEEP)
    config = reader.get_correct_config()

    assert isinstance(config, MotFluoresceConfigurationSweep)
    assert config.base_sequence is not None
    assert hasattr(config.base_sequence, "n_samples")


@patch("classes.rabi_voltage_converter.RabiFreqVoltageConverter.rescale_csv", _mock_rescale_csv)
@patch(
    "classes.rabi_voltage_converter.RabiFreqVoltageConverter.__init__", lambda self, *a, **kw: None
)
def test_new_format_sweep_params():
    """Sweep config has correct sweep parameters."""
    reader = ExperimentConfigReader(NEW_FORMAT_SWEEP)
    config = reader.get_correct_config()

    assert isinstance(config, MotFluoresceConfigurationSweep)
    assert config.sweep_type == "awg_sequence"
    assert config.num_shots == 1
    assert len(config.configs) > 0, "Should have generated configs for each sweep point"


# ---------------------------------------------------------------------------
# Old-format backward compatibility tests
# ---------------------------------------------------------------------------


def test_old_format_emits_deprecation_warning():
    """Old-format config with inline [scope_settings] emits DeprecationWarning."""
    # Create a temporary old-format config file
    old_config_content = """
date = 01/01/2026
time = 12:00

save location = "C:\\\\test_data"
mot reload = 1000
iterations = 1

use_cam = False
use_scope = True
use_awg = False

[scope_settings]
trigger_channel = 1
trigger_level = 1.0
sample_rate = 50e6
time_range = -100e-6, 4.1e-3
[[data_channels]]
1 = -1.0, 5.0
[[data_channel_impedance]]
1 = high
[[data_channel_coupling]]
1 = DC

[metadata]
config_type = experiment
experiment_type = "MOT Fluorescence"
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ini", delete=False, dir=str(PROJECT_ROOT)
    ) as f:
        f.write(old_config_content)
        tmp_path = f.name

    try:
        reader = ExperimentConfigReader(tmp_path)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = reader.get_mot_flourescence_configuration()

            # Should have emitted a deprecation warning about inline scope settings
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) > 0, (
                "Expected a DeprecationWarning for inline [scope_settings]"
            )

        # Config should still work correctly
        assert isinstance(config, MotFluoresceConfiguration)
        assert config.use_scope is True
        assert isinstance(config.scope_config, ScopeConfiguration)
        assert config.scope_config.trigger_channel == 1
    finally:
        Path(tmp_path).unlink()


if __name__ == "__main__":
    test_new_format_loads_mot_fluorescence()
    test_new_format_has_scope_config()
    test_new_format_has_awg_config()
    test_new_format_no_camera()
    test_new_format_sequence_config_path()
    test_new_format_backward_compat_properties()
    test_get_sequence_from_experiment_config()
    test_new_format_sweep_loads()
    test_new_format_sweep_has_base_config()
    test_new_format_sweep_has_sequence()
    test_new_format_sweep_params()
    test_old_format_emits_deprecation_warning()
    print("All ExperimentConfigReader tests passed!")
