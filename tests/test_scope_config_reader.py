"""Tests for the ScopeConfigReader class and ScopeConfiguration object."""

import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set the config root so resolve_config_path can resolve relative paths
os.environ["COLD_CONTROL_CONFIG_ROOT"] = str(PROJECT_ROOT)

from classes.config_readers import ScopeConfigReader  # noqa: E402
from classes.experimental_configs import ScopeConfiguration  # noqa: E402

SCOPE_CONFIG_PATH = str(
    PROJECT_ROOT / "configs" / "pulse_shaping_expt" / "scope" / "keysight_feb26.ini"
)


def test_load_scope_configuration():
    """Test that ScopeConfigReader correctly parses keysight_feb26.ini."""

    reader = ScopeConfigReader(SCOPE_CONFIG_PATH)
    scope_config = reader.load_scope_configuration()

    # Check type
    assert isinstance(scope_config, ScopeConfiguration), (
        f"Expected ScopeConfiguration, got {type(scope_config)}"
    )

    # Check scalar fields
    assert scope_config.trigger_channel == 1, f"trigger_channel: {scope_config.trigger_channel}"
    assert scope_config.trigger_level == 1.0, f"trigger_level: {scope_config.trigger_level}"
    assert scope_config.sample_rate == 50e6, f"sample_rate: {scope_config.sample_rate}"
    assert scope_config.time_range == (-100e-6, 4.1e-3), f"time_range: {scope_config.time_range}"


def test_scope_data_channels():
    """Test that data channels, impedance, and coupling are parsed correctly."""

    reader = ScopeConfigReader(SCOPE_CONFIG_PATH)
    scope_config = reader.load_scope_configuration()

    data_chs = scope_config.data_channels
    assert set(data_chs.keys()) == {1, 2, 3}, (
        f"Expected channels {{1, 2, 3}}, got {set(data_chs.keys())}"
    )

    # Channel 1
    assert data_chs[1]["range"] == (-1.0, 5.0), f"Channel 1 range: {data_chs[1]['range']}"
    assert data_chs[1]["impedance"] == "high", f"Channel 1 impedance: {data_chs[1]['impedance']}"
    assert data_chs[1]["coupling"] == "DC", f"Channel 1 coupling: {data_chs[1]['coupling']}"

    # Channel 2
    assert data_chs[2]["range"] == (-0.1, 0.1), f"Channel 2 range: {data_chs[2]['range']}"
    assert data_chs[2]["impedance"] == "high", f"Channel 2 impedance: {data_chs[2]['impedance']}"
    assert data_chs[2]["coupling"] == "DC", f"Channel 2 coupling: {data_chs[2]['coupling']}"

    # Channel 3
    assert data_chs[3]["range"] == (-0.004, 0.008), f"Channel 3 range: {data_chs[3]['range']}"
    assert data_chs[3]["impedance"] == "high", f"Channel 3 impedance: {data_chs[3]['impedance']}"
    assert data_chs[3]["coupling"] == "DC", f"Channel 3 coupling: {data_chs[3]['coupling']}"


def test_scope_configuration_repr():
    """Test that ScopeConfiguration has a useful repr."""

    reader = ScopeConfigReader(SCOPE_CONFIG_PATH)
    scope_config = reader.load_scope_configuration()

    repr_str = repr(scope_config)
    assert "ScopeConfiguration" in repr_str
    assert "trigger_channel=1" in repr_str
    assert "sample_rate=50000000.0" in repr_str


if __name__ == "__main__":
    test_load_scope_configuration()
    test_scope_data_channels()
    test_scope_configuration_repr()
    print("All ScopeConfigReader tests passed!")
