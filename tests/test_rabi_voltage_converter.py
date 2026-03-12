import pytest
import csv
import math
import numpy as np
from pathlib import Path

from classes.rabi_voltage_converter import RabiFreqVoltageConverter


@pytest.fixture
def calibration_csv(tmp_path):
    """Create a simple calibration CSV file for testing."""
    cal_file = tmp_path / "calibration.csv"
    # Simple monotonically increasing data
    # amplitude_cal (V), rabi_measured_no_ang (MHz), waist_size, cg_ang
    with open(cal_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["amplitude_cal", "rabi_measured_no_ang", "waist_size", "cg_ang"])
        for v in np.linspace(0.1, 1.0, 10):
            rabi = v * 10.0  # Simple linear: rabi = 10 * voltage
            writer.writerow([v, rabi, 25, 1.0])
    return cal_file


@pytest.fixture
def converter(calibration_csv):
    """Create a RabiFreqVoltageConverter with the test calibration file."""
    return RabiFreqVoltageConverter(calibration_csv)


class TestRabiFreqVoltageConverter:
    """Tests for the RabiFreqVoltageConverter class."""

    def test_construction(self, converter):
        """Constructor loads calibration data and creates interpolators."""
        assert converter.min_voltage > 0
        assert converter.max_voltage > converter.min_voltage
        assert converter.min_rabi >= 0
        assert converter.max_rabi > converter.min_rabi

    def test_voltage_to_rabi_in_range(self, converter):
        """voltage_to_rabi returns a float for valid voltages."""
        mid_v = (converter.min_voltage + converter.max_voltage) / 2
        result = converter.voltage_to_rabi(mid_v)
        assert isinstance(result, float)
        assert result > 0

    def test_voltage_to_rabi_out_of_range(self, converter):
        """voltage_to_rabi raises ValueError for out-of-range voltages."""
        with pytest.raises(ValueError):
            converter.voltage_to_rabi(converter.max_voltage + 100)

    def test_rabi_to_voltage_in_range(self, converter):
        """rabi_to_voltage returns a float for valid rabi frequencies."""
        mid_rabi = (converter.min_rabi + converter.max_rabi) / 2
        result = converter.rabi_to_voltage(mid_rabi)
        assert isinstance(result, float)
        assert result > 0

    def test_rabi_to_voltage_out_of_range(self, converter):
        """rabi_to_voltage raises ValueError for out-of-range rabi frequencies."""
        with pytest.raises(ValueError):
            converter.rabi_to_voltage(converter.max_rabi + 100)

    def test_roundtrip_voltage(self, converter):
        """voltage -> rabi -> voltage roundtrip should be approximately identity."""
        mid_v = (converter.min_voltage + converter.max_voltage) / 2
        rabi = converter.voltage_to_rabi(mid_v)
        v_back = converter.rabi_to_voltage(rabi)
        assert v_back == pytest.approx(mid_v, rel=0.01)

    def test_roundtrip_rabi(self, converter):
        """rabi -> voltage -> rabi roundtrip should be approximately identity."""
        mid_rabi = (converter.min_rabi + converter.max_rabi) / 2
        voltage = converter.rabi_to_voltage(mid_rabi)
        rabi_back = converter.voltage_to_rabi(voltage)
        assert rabi_back == pytest.approx(mid_rabi, rel=0.01)

    def test_get_rabi_limits(self, converter):
        """get_rabi_limits returns (max, min) tuple."""
        limits = converter.get_rabi_limits(print_info=False)
        assert len(limits) == 2
        max_rabi, min_rabi = limits
        assert max_rabi >= min_rabi

    def test_rescale_csv(self, converter, tmp_path):
        """rescale_csv writes a scaled waveform."""
        csv_in = tmp_path / "waveform_in.csv"
        csv_out = tmp_path / "waveform_out.csv"
        with open(csv_in, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([0.0, 0.5, 1.0, 0.5, 0.0])

        mid_rabi = (converter.min_rabi + converter.max_rabi) / 2
        converter.rescale_csv(mid_rabi, str(csv_in), str(csv_out), normalised=True)

        assert csv_out.exists()
        with open(csv_out) as f:
            reader = csv.reader(f)
            row = next(reader)
            values = [float(x) for x in row]
            assert len(values) == 5
            # Peak (index 2 where input=1.0) should be non-zero
            assert values[2] > 0
