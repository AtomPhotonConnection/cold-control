"""Tests for the AwgConfigReader class and the reworked Waveform class."""

import csv
import math
import os
import sys
import tempfile
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set the config root so resolve_config_path can resolve relative waveform paths
os.environ["COLD_CONTROL_CONFIG_ROOT"] = str(PROJECT_ROOT)

from classes.config_readers import AwgConfigReader  # noqa: E402
from classes.experimental_configs import AwgConfiguration, Waveform  # noqa: E402

config_path = str(
    PROJECT_ROOT / "configs" / "pulse_shaping_expt" / "awg_configs" / "feb26_awg_updated.ini"
)


def test_load_awg_configuration():
    """Test that AwgConfigReader correctly parses feb26_awg_updated.ini."""

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
    assert awg_config.waveform_sequence == [[2, 3], [0, 4], [1]], (
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
    for i, wf in awg_config.waveforms.items():
        assert wf.phases == [], f"Waveform {i} phases should be empty, got {wf.phases}"

    # Check that deprecated/optional fields are not stored as attributes
    assert not hasattr(awg_config, "interleave_waveforms")
    assert not hasattr(awg_config, "waveform_stitch_delays")
    assert not hasattr(awg_config, "marked_channels")

    print("All assertions passed!")


def test_convenience_methods():
    """Test convenience accessors on AwgConfigReader."""

    reader = AwgConfigReader(str(config_path))

    # AwgConfigReader exposes its config via reader.config
    assert reader.config["date"] == "26/01/2026"
    assert reader.config["time"] == "18:54"
    assert float(reader.config["sample rate"]) == 1.25e9
    assert int(reader.config["burst count"]) == 1
    assert isinstance(reader.config["notes"], str)

    print("Convenience method assertions passed!")


def test_get_awg_config_alias():
    """Test that get_awg_config is an alias for load_awg_configuration."""

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


def _make_temp_csv(content: str) -> Path:
    """Write content to a temporary CSV file and return its path (caller must delete)."""
    fd, path_name = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    path = Path(path_name)
    with path.open("w", newline="") as f:
        f.write(content)
    return path


def _write_csv_rows(rows) -> Path:
    """Write rows (list of lists) to a temporary CSV file and return its path."""
    fd, path_name = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    path = Path(path_name)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)
    return path


def test_waveform_defaults():
    """Waveform constructor defaults: modulated inferred as False when mod_frequency=0."""
    path = _make_temp_csv("0.1,0.5,1.0,0.5,0.1\n")
    try:
        wf = Waveform(fname=str(path))
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
        path.unlink()
    print("Waveform defaults test passed!")


def test_waveform_inferred_modulated():
    """Waveform with mod_frequency != 0 and no explicit modulated flag infers modulated=True."""
    path = _make_temp_csv(",".join(["1.0"] * 100) + "\n")
    try:
        wf = Waveform(fname=str(path), mod_frequency=1e6)
        assert wf.modulated is True
        result = wf.get(sample_rate=1e9)
        # With modulation, values should vary (not all 1.0)
        assert not all(abs(v - 1.0) < 1e-10 for v in result), "Modulation should change values"
    finally:
        path.unlink()
    print("Waveform inferred modulated test passed!")


def test_waveform_modulated_without_frequency_raises():
    """Waveform(modulated=True, mod_frequency=0) should raise ValueError."""
    path = _make_temp_csv("0.5,0.5\n")
    try:
        Waveform(fname=str(path), modulated=True, mod_frequency=0.0)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "modulated" in str(e).lower()
    finally:
        path.unlink()
    print("Modulated without frequency validation test passed!")


def test_modulated_get_requires_sample_rate():
    """Calling get() on a modulated waveform without sample_rate should raise ValueError."""
    path = _make_temp_csv(",".join(["1.0"] * 10) + "\n")
    try:
        wf = Waveform(fname=str(path), mod_frequency=1e6)
        assert wf.modulated is True
        try:
            wf.get()
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "sample_rate" in str(e).lower()
    finally:
        path.unlink()
    print("Modulated get() requires sample_rate test passed!")


def test_csv_single_row_format():
    """A CSV with one row of many comma-separated values loads correctly."""
    path = _write_csv_rows([[0.1, 0.2, 0.3, 0.4, 0.5]])
    try:
        wf = Waveform(fname=str(path))
        assert wf.data == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert wf.get_n_samples() == 5
    finally:
        path.unlink()
    print("Single-row CSV test passed!")


def test_csv_single_column_format():
    """A CSV with one column and many rows loads correctly."""
    path = _write_csv_rows([[0.1], [0.2], [0.3], [0.4], [0.5]])
    try:
        wf = Waveform(fname=str(path))
        assert wf.data == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert wf.get_n_samples() == 5
    finally:
        path.unlink()
    print("Single-column CSV test passed!")


def test_csv_ambiguous_format_raises():
    """A CSV with multiple rows AND multiple columns should raise ValueError."""
    path = _write_csv_rows([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    try:
        Waveform(fname=str(path))
        raise AssertionError("Should have raised ValueError for ambiguous CSV")
    except ValueError as e:
        assert "ambiguous" in str(e).lower()
    finally:
        path.unlink()
    print("Ambiguous CSV rejection test passed!")


def test_csv_empty_raises():
    """An empty CSV should raise ValueError."""
    path = _make_temp_csv("")
    try:
        Waveform(fname=str(path))
        raise AssertionError("Should have raised ValueError for empty CSV")
    except ValueError as e:
        assert "empty" in str(e).lower()
    finally:
        path.unlink()
    print("Empty CSV rejection test passed!")


def test_get_profile_and_helpers():
    """get_profile(), get_n_samples(), get_t_length() return expected values."""
    path = _make_temp_csv("0.1,0.2,0.3,0.4\n")
    try:
        wf = Waveform(fname=str(path))
        assert wf.get_profile() == [0.1, 0.2, 0.3, 0.4]
        assert wf.get_n_samples() == 4
        assert wf.get_t_length(1e9) == 4 / 1e9
    finally:
        path.unlink()
    print("get_profile / helpers test passed!")


def test_get_returns_copy():
    """get() should return a copy, not a reference to internal data."""
    path = _make_temp_csv("0.5,0.5,0.5\n")
    try:
        wf = Waveform(fname=str(path))
        result = wf.get()
        result[0] = 999.0
        assert wf.data[0] == 0.5, "Internal data should not be mutated"
    finally:
        path.unlink()
    print("get() returns copy test passed!")


def test_explicit_modulated_flag():
    """Passing modulated explicitly should skip inference."""
    path = _make_temp_csv(",".join(["1.0"] * 10) + "\n")
    try:
        # Explicitly unmodulated despite having a mod_frequency
        wf = Waveform(fname=str(path), modulated=False, mod_frequency=0.0)
        assert wf.modulated is False

        # Explicitly modulated with a frequency
        wf2 = Waveform(fname=str(path), modulated=True, mod_frequency=1e6)
        assert wf2.modulated is True
    finally:
        path.unlink()
    print("Explicit modulated flag test passed!")


def test_property_setters():
    """fname setter reloads data; modulated/mod_frequency setters update state."""
    path1 = _make_temp_csv("0.1,0.2,0.3\n")
    path2 = _make_temp_csv("0.9,0.8\n")
    try:
        wf = Waveform(fname=str(path1))
        assert wf.data == [0.1, 0.2, 0.3]

        # Reassigning fname should reload data from the new file
        wf.fname = str(path2)
        assert wf.fname == str(path2)
        assert wf.data == [0.9, 0.8]

        # modulated setter
        wf.modulated = True
        assert wf.modulated is True
        wf.modulated = False
        assert wf.modulated is False

        # mod_frequency setter
        wf.mod_frequency = 5e6
        assert wf.mod_frequency == 5e6

        # set_mod_frequency method
        wf.set_mod_frequency(7e6)
        assert wf.mod_frequency == 7e6
    finally:
        path1.unlink()
        path2.unlink()
    print("Property setters test passed!")


def test_get_marker_data_basic():
    """get_marker_data() returns a marker waveform with correct padding and positions."""
    path = _make_temp_csv("0.1,0.2,0.3,0.4,0.5\n")
    try:
        wf = Waveform(fname=str(path))
        n_samples = wf.get_n_samples()  # 5

        # Default: no markers, no padding -> all zeros
        markers = wf.get_marker_data()
        assert len(markers) == n_samples
        assert all(m == 0 for m in markers)

        # With padding
        markers = wf.get_marker_data(n_pad_left=3, n_pad_right=2)
        assert len(markers) == 3 + n_samples + 2  # 10

        # With a marker position and width
        markers = wf.get_marker_data(
            marker_positions=[2],
            marker_width=2,
            n_pad_left=0,
            n_pad_right=0,
        )
        assert len(markers) == n_samples
        assert markers[0] == 0
        assert markers[1] == 0
        assert markers[2] == 1
        assert markers[3] == 1
        assert markers[4] == 0
    finally:
        path.unlink()
    print("get_marker_data test passed!")


def test_get_marker_data_high_start_fix():
    """get_marker_data forces the first sample low even if a marker starts at index 0."""
    path = _make_temp_csv("0.1,0.2,0.3,0.4,0.5\n")
    try:
        wf = Waveform(fname=str(path))
        markers = wf.get_marker_data(marker_positions=[0], marker_width=3)
        # First sample forced to 0; samples 1-2 should still be 1
        assert markers[0] == 0
        assert markers[1] == 1
        assert markers[2] == 1
    finally:
        path.unlink()
    print("get_marker_data high-start fix test passed!")


def test_modulated_get_with_phases():
    """Phase jumps during modulation produce a different result than no phases."""
    n = 200
    path = _make_temp_csv(",".join(["1.0"] * n) + "\n")
    try:
        freq = 1e6
        sr = 1e9

        wf_no_phase = Waveform(fname=str(path), mod_frequency=freq)
        wf_with_phase = Waveform(fname=str(path), mod_frequency=freq, phases=[(math.pi, 100)])

        result_no = wf_no_phase.get(sample_rate=sr)
        result_with = wf_with_phase.get(sample_rate=sr)

        # Before the phase flip (sample 0-99), results should be identical
        for i in range(100):
            assert abs(result_no[i] - result_with[i]) < 1e-12, f"Sample {i} differs before phase"

        # After the phase flip (sample 100+), results should differ
        diffs = [abs(result_no[i] - result_with[i]) for i in range(100, n)]
        assert max(diffs) > 0.01, "Phase flip should change modulated output"
    finally:
        path.unlink()
    print("Modulated get with phases test passed!")


def test_phases_property():
    """phases property returns the stored phase list."""
    path = _make_temp_csv("0.5,0.5,0.5\n")
    try:
        wf = Waveform(fname=str(path))
        assert wf.phases == []

        wf2 = Waveform(fname=str(path), mod_frequency=1e6, phases=[(3.14, 1), (1.57, 0)])
        # phases should be sorted by sample index
        assert wf2.phases[0] == (1.57, 0)
        assert wf2.phases[1] == (3.14, 1)
    finally:
        path.unlink()
    print("Phases property test passed!")


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
    test_get_profile_and_helpers()
    test_get_returns_copy()
    test_explicit_modulated_flag()
    test_property_setters()
    test_get_marker_data_basic()
    test_get_marker_data_high_start_fix()
    test_modulated_get_with_phases()
    test_phases_property()
    print("\n=== All tests passed! ===")
