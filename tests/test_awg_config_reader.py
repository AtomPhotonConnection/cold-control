"""Tests for the AwgConfigReader class."""

import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Set the config root so resolve_config_path can resolve relative waveform paths
os.environ["COLD_CONTROL_CONFIG_ROOT"] = PROJECT_ROOT

from classes.config_readers import AwgConfigReader
from classes.experimental_configs import AwgConfiguration, Waveform


def test_load_awg_configuration():
    """Test that AwgConfigReader correctly parses feb26_awg_updated.ini."""
    config_path = os.path.join(
        PROJECT_ROOT, "configs", "pulse_shaping_expt", "awg_configs", "feb26_awg_updated.ini"
    )
    reader = AwgConfigReader(config_path)
    awg_config = reader.load_awg_configuration()

    # Check type
    assert isinstance(awg_config, AwgConfiguration), (
        f"Expected AwgConfiguration, got {type(awg_config)}"
    )

    # Check scalar fields
    assert awg_config.sample_rate == 1.25e9, f"sample_rate: {awg_config.sample_rate}"
    assert awg_config.burst_count == 1, f"burst_count: {awg_config.burst_count}"
    assert awg_config.marker_width == 2e-9, f"marker_width: {awg_config.marker_width}"

    # Check output channels parsed from "channel1, channel2, channel3"
    assert awg_config.waveform_output_channels == (1, 2, 3), (
        f"waveform_output_channels: {awg_config.waveform_output_channels}"
    )

    # Check channel lags
    assert awg_config.waveform_output_channel_lags == (0.0, 0.0, 0.0), (
        f"waveform_output_channel_lags: {awg_config.waveform_output_channel_lags}"
    )

    # Check waveform sequence: "[2, 3],[0, 4],[1]" -> ((2,3),(0,4),(1,))
    assert awg_config.waveform_sequence == ((2, 3), (0, 4), (1,)), (
        f"waveform_sequence: {awg_config.waveform_sequence}"
    )

    # Check waveforms count
    assert len(awg_config.waveforms) == 5, f"Expected 5 waveforms, got {len(awg_config.waveforms)}"

    # Check each waveform's modulation frequency
    expected_freqs = [74000000, 54855800, 0, 60855800, 80000000]
    for i, (wf, expected) in enumerate(zip(awg_config.waveforms, expected_freqs)):
        assert isinstance(wf, Waveform), f"Waveform {i} type: {type(wf)}"
        assert wf.mod_frequency == expected, (
            f"Waveform {i} mod_frequency: {wf.mod_frequency}, expected {expected}"
        )

    # Check that phases default to empty list for empty "phases = ,"
    for i, wf in enumerate(awg_config.waveforms):
        assert wf.phases == [], f"Waveform {i} phases should be empty, got {wf.phases}"

    # Check deprecated/optional fields default to None
    assert awg_config.interleave_waveforms is None
    assert awg_config.waveform_stitch_delays is None
    assert awg_config.marked_channels is None

    print("All assertions passed!")


def test_convenience_methods():
    """Test convenience accessors on AwgConfigReader."""
    config_path = os.path.join(
        PROJECT_ROOT, "configs", "pulse_shaping_expt", "awg_configs", "feb26_awg_updated.ini"
    )
    reader = AwgConfigReader(config_path)

    assert reader.get_date() == "26/01/2026"
    assert reader.get_time() == "18:54"
    assert reader.get_sample_rate() == 1.25e9
    assert reader.get_burst_count() == 1
    assert isinstance(reader.get_notes(), str)

    print("Convenience method assertions passed!")


def test_get_awg_config_alias():
    """Test that get_awg_config is an alias for load_awg_configuration."""
    config_path = os.path.join(
        PROJECT_ROOT, "configs", "pulse_shaping_expt", "awg_configs", "feb26_awg_updated.ini"
    )
    reader = AwgConfigReader(config_path)
    config1 = reader.load_awg_configuration()
    config2 = reader.get_awg_config()

    assert config1.sample_rate == config2.sample_rate
    assert config1.burst_count == config2.burst_count
    assert len(config1.waveforms) == len(config2.waveforms)

    print("Alias test passed!")


def test_parse_phases_edge_cases():
    """Test the static _parse_phases method with various inputs."""
    parse = AwgConfigReader._parse_phases

    # Empty list (ConfigObj for "phases = ,") -> ['', '']
    assert parse(["", ""]) == []

    # None
    assert parse(None) == []

    # Empty string
    assert parse("") == []

    # Numeric list
    assert parse(["3.14", "1.57"]) == [(3.14, 0), (1.57, 1)]

    # Single value
    assert parse("3.14") == [(3.14, 0)]

    print("Phase parsing edge cases passed!")


if __name__ == "__main__":
    test_load_awg_configuration()
    test_convenience_methods()
    test_get_awg_config_alias()
    test_parse_phases_edge_cases()
    print("\n=== All tests passed! ===")
