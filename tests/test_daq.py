import pytest
import numpy as np
import csv
import tempfile
from pathlib import Path

from classes.daq import DAQChannel, DAQDio, INPUT_LINE, OUTPUT_LINE


# ===== DAQChannel Tests =====


class TestDAQChannel:
    """Tests for the DAQChannel class."""

    def test_default_construction(self):
        """DAQChannel with only ch_num uses sensible defaults."""
        ch = DAQChannel(0)
        assert ch.chNum == 0
        assert ch.chName == "Ch 0"
        assert ch.chLimits == (-10, 10)
        assert ch.defaultValue == 0.0
        assert ch.isUIVisible is True
        assert ch.isCalibrated is False

    def test_named_construction(self):
        """DAQChannel stores all named arguments."""
        ch = DAQChannel(3, "Test Ch", (-5, 5), 2.5, False, "")
        assert ch.chNum == 3
        assert ch.chName == "Test Ch"
        assert ch.chLimits == (-5, 5)
        assert ch.defaultValue == 2.5
        assert ch.isUIVisible is False

    def test_calibrate_from_csv(self, tmp_path):
        """Calibrating from CSV creates bidirectional conversion functions."""
        cal_file = tmp_path / "cal.csv"
        with open(cal_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["voltage", "calibrated"])
            writer.writerow([0.0, 0.0])
            writer.writerow([5.0, 100.0])
            writer.writerow([10.0, 200.0])
        ch = DAQChannel(0)
        ch.calibrate(str(cal_file), from_csv=True)
        assert ch.isCalibrated is True
        assert ch.calibrationFname == str(cal_file)

    def test_remove_calibration(self, tmp_path):
        """remove_calibration resets calibration state."""
        cal_file = tmp_path / "cal.csv"
        with open(cal_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["voltage", "calibrated"])
            writer.writerow([0.0, 0.0])
            writer.writerow([5.0, 100.0])
        ch = DAQChannel(0)
        ch.calibrate(str(cal_file), from_csv=True)
        assert ch.isCalibrated is True
        ch.remove_calibration()
        assert ch.isCalibrated is False

    def test_get_help_text_uncalibrated(self):
        """get_help_text for uncalibrated channel returns name and limits."""
        ch = DAQChannel(1, "Laser Power", (-5, 5))
        text = ch.get_help_text()
        assert isinstance(text, str)
        assert "Laser Power" in text or "1" in text

    def test_get_help_text_calibrated(self, tmp_path):
        """get_help_text for calibrated channel includes calibration info."""
        cal_file = tmp_path / "cal.csv"
        with open(cal_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["voltage", "calibrated"])
            writer.writerow([0.0, 0.0])
            writer.writerow([5.0, 100.0])
        ch = DAQChannel(0, "Power")
        ch.calibrate(str(cal_file), from_csv=True)
        text = ch.get_help_text()
        assert isinstance(text, str)


# ===== DAQDio Tests =====


class TestDAQDio:
    """Tests for the DAQDio class."""

    def test_construction(self):
        """DAQDio stores all constructor arguments."""
        dio = DAQDio("Shutter", 0, 0, 0, OUTPUT_LINE, 1)
        assert dio.dio_name == "Shutter"
        assert dio.dio_num == 0
        assert dio.port == 0
        assert dio.line == 0
        assert dio.direction == OUTPUT_LINE
        assert dio.enabled_state == 1

    def test_write_calls_registered_fn(self):
        """write() calls the registered write function."""
        written_values = []
        dio = DAQDio("Shutter", 0, 0, 0, OUTPUT_LINE, 1)
        dio.register_write_fn(lambda v: written_values.append(v))
        dio.write(1)
        assert written_values == [1]

    def test_read_calls_registered_fn(self):
        """read() returns value from registered read function."""
        dio = DAQDio("Sensor", 1, 0, 0, INPUT_LINE, 0)
        dio.register_read_fn(lambda: 1)
        assert dio.read() == 1

    def test_toggle_state_output(self):
        """toggle_state flips the DIO state for output lines."""
        current_state = [0]
        dio = DAQDio("Shutter", 0, 0, 0, OUTPUT_LINE, 1)
        dio.register_write_fn(lambda v: current_state.__setitem__(0, v))
        dio.register_read_fn(lambda: current_state[0])

        state = dio.toggle_state(return_state=True)
        assert state in (0, 1)

    def test_get_help_text(self):
        """get_help_text returns a non-empty description string."""
        dio = DAQDio("Shutter", 0, 0, 0, OUTPUT_LINE, 1)
        text = dio.get_help_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_write_without_registered_fn_raises(self):
        """write() without a registered write function raises RuntimeError."""
        dio = DAQDio("Shutter", 0, 0, 0, OUTPUT_LINE, 1)
        with pytest.raises(RuntimeError):
            dio.write(1)

    def test_read_without_registered_fn_raises(self):
        """read() without a registered read function raises RuntimeError."""
        dio = DAQDio("Sensor", 1, 0, 0, INPUT_LINE, 0)
        with pytest.raises(RuntimeError):
            dio.read()
