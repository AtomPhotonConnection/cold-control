"""
Unit tests for the Waveform class in classes/experimental_configs.py.

All tests use temporary CSV files — no hardware required.
Run with:  pytest tests/test_waveform.py -v
"""

import pytest
import csv
import math
from pathlib import Path

from classes.experimental_configs import Waveform


@pytest.fixture
def single_row_csv(tmp_path):
    """CSV with a single row of comma-separated values."""
    f = tmp_path / "single_row.csv"
    with open(f, "w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow([0.0, 0.5, 1.0, 0.5, 0.0])
    return f


@pytest.fixture
def single_column_csv(tmp_path):
    """CSV with one value per line."""
    f = tmp_path / "single_col.csv"
    with open(f, "w", newline="") as fp:
        writer = csv.writer(fp)
        for val in [0.0, 0.25, 0.5, 0.75, 1.0]:
            writer.writerow([val])
    return f


@pytest.fixture
def single_value_csv(tmp_path):
    """CSV with a single value."""
    f = tmp_path / "single_val.csv"
    with open(f, "w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow([0.42])
    return f


@pytest.fixture
def empty_csv(tmp_path):
    """Empty CSV file."""
    f = tmp_path / "empty.csv"
    f.write_text("")
    return f


class TestWaveform:
    """Tests for the Waveform class."""

    def test_load_single_row(self, single_row_csv):
        """Loading a single-row CSV stores the values correctly."""
        wf = Waveform(str(single_row_csv), modulated=False)
        assert wf.get_n_samples() == 5
        profile = wf.get_profile()
        assert profile == pytest.approx([0.0, 0.5, 1.0, 0.5, 0.0])

    def test_load_single_column(self, single_column_csv):
        """Loading a single-column CSV stores the values correctly."""
        wf = Waveform(str(single_column_csv), modulated=False)
        assert wf.get_n_samples() == 5
        profile = wf.get_profile()
        assert profile == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])

    def test_load_single_value(self, single_value_csv):
        """Loading a single-value CSV returns a single-element list."""
        wf = Waveform(str(single_value_csv), modulated=False)
        assert wf.get_n_samples() == 1
        assert wf.get_profile() == pytest.approx([0.42])

    def test_empty_csv_raises(self, empty_csv):
        """Empty CSV raises ValueError."""
        with pytest.raises(ValueError):
            Waveform(str(empty_csv), modulated=False)

    def test_get_unmodulated(self, single_row_csv):
        """get() without modulation returns raw envelope."""
        wf = Waveform(str(single_row_csv), modulated=False)
        data = wf.get()
        assert data == pytest.approx([0.0, 0.5, 1.0, 0.5, 0.0])

    def test_get_modulated_requires_sample_rate(self, single_row_csv):
        """get() with modulation raises ValueError if sample_rate is None."""
        wf = Waveform(str(single_row_csv), modulated=True, mod_frequency=1e6)
        with pytest.raises(ValueError):
            wf.get()  # No sample_rate

    def test_get_modulated_with_sample_rate(self, single_row_csv):
        """get() with modulation and sample_rate returns modulated waveform."""
        wf = Waveform(str(single_row_csv), modulated=True, mod_frequency=1e6)
        data = wf.get(sample_rate=10e6)
        assert len(data) == 5
        # Values should be envelope * sin, so different from raw profile
        # The max absolute value should not exceed the max envelope value
        assert max(abs(v) for v in data) <= 1.0 + 1e-10

    def test_get_t_length(self, single_row_csv):
        """get_t_length returns duration in seconds."""
        wf = Waveform(str(single_row_csv), modulated=False)
        # 5 samples at 10 MHz sample rate = 5 / 10e6 = 0.5e-6 seconds
        t_length = wf.get_t_length(10e6)
        assert t_length == pytest.approx(5 / 10e6)

    def test_modulated_inferred_from_frequency(self, single_row_csv):
        """modulated is inferred as True when mod_frequency > 0."""
        wf = Waveform(str(single_row_csv), mod_frequency=1e6)
        assert wf.modulated is True

    def test_modulated_inferred_false_when_no_frequency(self, single_row_csv):
        """modulated is inferred as False when mod_frequency == 0."""
        wf = Waveform(str(single_row_csv))
        assert wf.modulated is False

    def test_set_mod_frequency(self, single_row_csv):
        """set_mod_frequency updates the modulation frequency."""
        wf = Waveform(str(single_row_csv), modulated=False)
        wf.set_mod_frequency(2e6)
        assert wf.mod_frequency == 2e6

    def test_fname_property_reloads(self, single_row_csv, single_column_csv):
        """Assigning fname property reloads data from new file."""
        wf = Waveform(str(single_row_csv), modulated=False)
        assert wf.get_n_samples() == 5
        old_profile = wf.get_profile()

        wf.fname = single_column_csv
        assert wf.get_n_samples() == 5  # Both have 5 values
        new_profile = wf.get_profile()
        # Values should differ
        assert new_profile != old_profile
