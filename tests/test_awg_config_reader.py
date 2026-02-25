"""Tests for the AwgConfigReader class and the reworked Waveform class."""

import csv
import os
import sys
import tempfile
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Set the config root so resolve_config_path can resolve relative waveform paths
os.environ["COLD_CONTROL_CONFIG_ROOT"] = PROJECT_ROOT

from classes.config_readers import AwgConfigReader  # noqa: E402
from classes.experimental_configs import AwgConfiguration, Waveform  # noqa: E402


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
    assert awg_config.marker_width_samps is not None, "marker_width_samps should be set"

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
    expected_modulated = [True, True, False, True, True]
    for i, (wf, expected_f, expected_m) in enumerate(
        zip(awg_config.waveforms, expected_freqs, expected_modulated)
    ):
        assert isinstance(wf, Waveform), f"Waveform {i} type: {type(wf)}"
        assert wf.mod_frequency == expected_f, (
            f"Waveform {i} mod_frequency: {wf.mod_frequency}, expected {expected_f}"
        )
        assert wf.modulated == expected_m, (
            f"Waveform {i} modulated: {wf.modulated}, expected {expected_m}"
        )

    # Check that phases default to empty list for empty "phases = ,"
    for i, wf in enumerate(awg_config.waveforms):
        assert wf.phases == [], f"Waveform {i} phases should be empty, got {wf.phases}"

    # Check that deprecated/optional fields are not stored as attributes
    assert not hasattr(awg_config, "interleave_waveforms")
    assert not hasattr(awg_config, "waveform_stitch_delays")
    assert not hasattr(awg_config, "marked_channels")

    print("All assertions passed!")


def test_convenience_methods():
    """Test convenience accessors on AwgConfigReader."""
    config_path = os.path.join(
        PROJECT_ROOT, "configs", "pulse_shaping_expt", "awg_configs", "feb26_awg_updated.ini"
    )
    reader = AwgConfigReader(config_path)

    # AwgConfigReader exposes its config via reader.config
    assert reader.config["date"] == "26/01/2026"
    assert reader.config["time"] == "18:54"
    assert float(reader.config["sample rate"]) == 1.25e9
    assert int(reader.config["burst count"]) == 1
    assert isinstance(reader.config["notes"], str)

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


# ---------------------------------------------------------------------------
# Waveform class tests
# ---------------------------------------------------------------------------


def _make_temp_csv(content: str) -> str:
    """Write content to a temporary CSV file and return its path (caller must delete)."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="") as f:
        f.write(content)
    return path


def _write_csv_rows(rows) -> str:
    """Write rows (list of lists) to a temporary CSV file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)
    return path


def test_waveform_defaults():
    """Waveform constructor defaults: modulated inferred as False when mod_frequency=0."""
    path = _make_temp_csv("0.1,0.5,1.0,0.5,0.1\n")
    try:
        wf = Waveform(fname=path)
        assert wf.modulated is False
        assert wf.mod_frequency == 0.0
        assert wf.phases == []
        assert wf.data == [0.1, 0.5, 1.0, 0.5, 0.1]
        # get() with modulated=False needs no sample_rate
        result = wf.get()
        assert result == [0.1, 0.5, 1.0, 0.5, 0.1]
        # Also works with sample_rate provided (ignored for unmodulated)
        result2 = wf.get(sample_rate=1e9)
        assert result2 == [0.1, 0.5, 1.0, 0.5, 0.1]
    finally:
        os.unlink(path)
    print("Waveform defaults test passed!")


def test_waveform_inferred_modulated():
    """Waveform with mod_frequency != 0 and no explicit modulated flag infers modulated=True."""
    path = _make_temp_csv(",".join(["1.0"] * 100) + "\n")
    try:
        wf = Waveform(fname=path, mod_frequency=1e6)
        assert wf.modulated is True
        result = wf.get(sample_rate=1e9)
        # With modulation, values should vary (not all 1.0)
        assert not all(abs(v - 1.0) < 1e-10 for v in result), "Modulation should change values"
    finally:
        os.unlink(path)
    print("Waveform inferred modulated test passed!")


def test_waveform_modulated_without_frequency_raises():
    """Waveform(modulated=True, mod_frequency=0) should raise ValueError."""
    path = _make_temp_csv("0.5,0.5\n")
    try:
        Waveform(fname=path, modulated=True, mod_frequency=0.0)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "modulated" in str(e).lower()
    finally:
        os.unlink(path)
    print("Modulated without frequency validation test passed!")


def test_modulated_get_requires_sample_rate():
    """Calling get() on a modulated waveform without sample_rate should raise ValueError."""
    path = _make_temp_csv(",".join(["1.0"] * 10) + "\n")
    try:
        wf = Waveform(fname=path, mod_frequency=1e6)
        assert wf.modulated is True
        try:
            wf.get()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "sample_rate" in str(e).lower()
    finally:
        os.unlink(path)
    print("Modulated get() requires sample_rate test passed!")


def test_csv_single_row_format():
    """A CSV with one row of many comma-separated values loads correctly."""
    path = _write_csv_rows([[0.1, 0.2, 0.3, 0.4, 0.5]])
    try:
        wf = Waveform(fname=path)
        assert wf.data == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert wf.get_n_samples() == 5
    finally:
        os.unlink(path)
    print("Single-row CSV test passed!")


def test_csv_single_column_format():
    """A CSV with one column and many rows loads correctly."""
    path = _write_csv_rows([[0.1], [0.2], [0.3], [0.4], [0.5]])
    try:
        wf = Waveform(fname=path)
        assert wf.data == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert wf.get_n_samples() == 5
    finally:
        os.unlink(path)
    print("Single-column CSV test passed!")


def test_csv_ambiguous_format_raises():
    """A CSV with multiple rows AND multiple columns should raise ValueError."""
    path = _write_csv_rows([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    try:
        Waveform(fname=path)
        assert False, "Should have raised ValueError for ambiguous CSV"
    except ValueError as e:
        assert "ambiguous" in str(e).lower()
    finally:
        os.unlink(path)
    print("Ambiguous CSV rejection test passed!")


def test_csv_empty_raises():
    """An empty CSV should raise ValueError."""
    path = _make_temp_csv("")
    try:
        Waveform(fname=path)
        assert False, "Should have raised ValueError for empty CSV"
    except ValueError as e:
        assert "empty" in str(e).lower()
    finally:
        os.unlink(path)
    print("Empty CSV rejection test passed!")


if __name__ == "__main__":
    test_load_awg_configuration()
    test_convenience_methods()
    test_get_awg_config_alias()
    test_parse_phases_edge_cases()
    test_waveform_defaults()
    test_waveform_inferred_modulated()
    test_waveform_modulated_without_frequency_raises()
    test_modulated_get_requires_sample_rate()
    test_csv_single_row_format()
    test_csv_single_column_format()
    test_csv_ambiguous_format_raises()
    test_csv_empty_raises()
    print("\n=== All tests passed! ===")
