"""
Unit tests for DAQ analogue input reading.

All tests run without real hardware — DLL calls are mocked using
unittest.mock so the test suite works on any machine.
"""

import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from classes.daq import (
    AI_DEFAULT_AD_RANGE,
    AD_B_10_V,
    AI_RSE,
    DAQInputChannel,
    DAQController,
    DAQCard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_card(card_num: int = 0, ai_channel_nums: list[int] | None = None):
    """Return a MagicMock that behaves like a DAQCard for AI purposes."""
    card = MagicMock(spec=DAQCard)
    card.numChs = 8
    if ai_channel_nums is None:
        ai_channel_nums = []
    card.ai_channels = [DAQInputChannel(n, f"AI Ch {n}") for n in ai_channel_nums]

    def _read_ai_voltage(ch_num: int) -> float:
        # Return a predictable value: ch_num * 0.1
        return ch_num * 0.1

    card.read_ai_voltage.side_effect = _read_ai_voltage

    def _read_ai_channels(ch_nums=None):
        if ch_nums is None:
            ch_nums = [ch.chNum for ch in card.ai_channels]
        return {n: _read_ai_voltage(n) for n in ch_nums}

    card.read_ai_channels.side_effect = _read_ai_channels
    return card


def _make_controller(master_ai_chs=None, slave_ai_chs=None):
    """Build a DAQController whose cards are MagicMocks."""
    master = _make_mock_card(0, master_ai_chs or [])
    master.channels = []
    master.dios = []

    slaves = []
    if slave_ai_chs:
        slave = _make_mock_card(1, slave_ai_chs)
        slave.channels = []
        slave.dios = []
        slaves.append(slave)

    ctrl = DAQController.__new__(DAQController)
    ctrl._DAQController__master = master
    ctrl._DAQController__slaves = slaves
    ctrl.continuous_output = False
    ctrl.channelValues = {}
    return ctrl


# ---------------------------------------------------------------------------
# DAQInputChannel
# ---------------------------------------------------------------------------


class TestDAQInputChannel:
    """Tests for the DAQInputChannel metadata class."""

    def test_default_construction(self):
        ch = DAQInputChannel(0)
        assert ch.chNum == 0
        assert ch.chName == "AI Ch 0"
        assert ch.ad_range == AI_DEFAULT_AD_RANGE
        assert ch.input_mode == AI_RSE
        assert ch.isUIVisible is True
        assert ch.isCalibrated is False
        assert ch.calibrationUnits == "V"

    def test_named_construction(self):
        ch = DAQInputChannel(3, "Pressure", AD_B_10_V, AI_RSE, False)
        assert ch.chNum == 3
        assert ch.chName == "Pressure"
        assert ch.isUIVisible is False

    def test_empty_name_gets_default(self):
        ch = DAQInputChannel(5, "  ")
        assert ch.chName == "AI Ch 5"

    def test_get_display_value_uncalibrated(self):
        ch = DAQInputChannel(0)
        val, units = ch.get_display_value(3.14)
        assert val == pytest.approx(3.14)
        assert units == "V"

    def test_get_display_value_calibrated(self, tmp_path):
        cal_file = tmp_path / "cal.csv"
        with cal_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Voltage (V)", "Temperature (degC)"])
            writer.writerow([0.0, 0.0])
            writer.writerow([5.0, 100.0])
            writer.writerow([10.0, 200.0])
        ch = DAQInputChannel(0)
        ch.calibrate(str(cal_file))
        assert ch.isCalibrated is True
        assert ch.calibrationUnits == "degC"
        val, units = ch.get_display_value(5.0)
        assert val == pytest.approx(100.0)
        assert units == "degC"

    def test_remove_calibration(self, tmp_path):
        cal_file = tmp_path / "cal.csv"
        with cal_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Voltage (V)", "Temperature (degC)"])
            writer.writerow([0.0, 0.0])
            writer.writerow([5.0, 100.0])
        ch = DAQInputChannel(0)
        ch.calibrate(str(cal_file))
        assert ch.isCalibrated is True
        ch.remove_calibration()
        assert ch.isCalibrated is False
        assert ch.calibrationUnits == "V"
        assert getattr(ch, "calibration", None) is None

    def test_calibrate_missing_file_logs_error(self, caplog):
        import logging

        ch = DAQInputChannel(0)
        with caplog.at_level(logging.ERROR):
            ch.calibrate("/nonexistent/path/cal.csv")
        assert ch.isCalibrated is False

    def test_get_help_text_uncalibrated(self):
        ch = DAQInputChannel(2, "Test")
        text = ch.get_help_text()
        assert "2" in text
        assert "Test" in text
        assert "RSE" in text
        assert "No calibration" in text

    def test_get_help_text_calibrated(self, tmp_path):
        cal_file = tmp_path / "cal.csv"
        with cal_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Voltage (V)", "Pressure (mbar)"])
            writer.writerow([0.0, 0.0])
            writer.writerow([10.0, 100.0])
        ch = DAQInputChannel(0, "Pressure sensor")
        ch.calibrate(str(cal_file))
        text = ch.get_help_text()
        assert "mbar" in text


# ---------------------------------------------------------------------------
# DAQController AI routing
# ---------------------------------------------------------------------------


class TestDAQControllerAI:
    """Tests for the AI methods on DAQController (using mock cards)."""

    def test_get_ai_channels_from_master(self):
        ctrl = _make_controller(master_ai_chs=[0, 1, 2])
        chs = ctrl.get_ai_channels()
        assert len(chs) == 3
        assert {ch.chNum for ch in chs} == {0, 1, 2}

    def test_get_ai_channels_across_master_and_slave(self):
        ctrl = _make_controller(master_ai_chs=[0, 1], slave_ai_chs=[2, 3])
        chs = ctrl.get_ai_channels()
        assert len(chs) == 4

    def test_get_ai_channels_only_visible(self):
        ctrl = _make_controller(master_ai_chs=[0, 1, 2])
        ctrl.master.ai_channels[1].isUIVisible = False
        chs = ctrl.get_ai_channels(only_visible=True)
        assert len(chs) == 2

    def test_read_ai_channel_routes_to_master(self):
        ctrl = _make_controller(master_ai_chs=[0, 1])
        voltage = ctrl.read_ai_channel(0)
        assert voltage == pytest.approx(0.0)
        voltage = ctrl.read_ai_channel(1)
        assert voltage == pytest.approx(0.1)

    def test_read_ai_channel_routes_to_slave(self):
        ctrl = _make_controller(master_ai_chs=[0], slave_ai_chs=[2])
        voltage = ctrl.read_ai_channel(2)
        assert voltage == pytest.approx(0.2)

    def test_read_ai_channel_raises_for_unknown(self):
        ctrl = _make_controller(master_ai_chs=[0])
        with pytest.raises(ValueError, match="No AI channel"):
            ctrl.read_ai_channel(99)

    def test_read_ai_channels_all(self):
        ctrl = _make_controller(master_ai_chs=[0, 1, 2])
        result = ctrl.read_ai_channels()
        assert set(result.keys()) == {0, 1, 2}
        assert result[1] == pytest.approx(0.1)

    def test_read_ai_channels_subset(self):
        ctrl = _make_controller(master_ai_chs=[0, 1, 2])
        result = ctrl.read_ai_channels([0, 2])
        assert set(result.keys()) == {0, 2}
        assert 1 not in result

    def test_read_ai_channels_empty_returns_empty(self):
        ctrl = _make_controller()
        result = ctrl.read_ai_channels()
        assert result == {}


# ---------------------------------------------------------------------------
# DAQ2502.read_ai_voltage (DLL mocked at import time)
# ---------------------------------------------------------------------------


@pytest.fixture
def daq_dll_module():
    """Import daq_dll with WinDLL mocked so the DLL file isn't needed."""
    import sys
    import ctypes
    from unittest.mock import MagicMock, patch

    # Build a mock WinDLL instance that returns 0 for every function call
    mock_win_dll = MagicMock()
    mock_win_dll.return_value = 0

    # Patch WinDLL at the ctypes level before daq_dll is imported
    with patch("ctypes.WinDLL", return_value=mock_win_dll):
        # Remove any cached import so it re-runs the module body
        sys.modules.pop("classes.daq_dll", None)
        import classes.daq_dll as mod

        yield mod

    # Restore original module (removes the mock-based one)
    sys.modules.pop("classes.daq_dll", None)


class TestDAQ2502ReadAiVoltage:
    """Tests for the low-level DLL AI read methods using a mocked DLL."""

    def _make_obj(self, dll_module):
        """Create a bare DAQ2502 instance bypassing __init__."""
        obj = dll_module.DAQ2502.__new__(dll_module.DAQ2502)
        obj._DAQ2502__card = 0
        obj._DAQ2502__n_samples = {}
        return obj

    def test_read_ai_voltage_calls_dll_functions(self, daq_dll_module):
        """read_ai_voltage calls CH_Config then VReadChannel."""
        mod = daq_dll_module
        obj = self._make_obj(mod)

        mod.dll.D2K_AI_CH_Config.return_value = 0

        def fake_v_read(card, ch, ptr):
            ptr.contents.value = 2.5
            return 0

        mod.dll.D2K_AI_VReadChannel.side_effect = fake_v_read

        v = obj.read_ai_voltage(0, mod.AD_B_10_V)
        mod.dll.D2K_AI_CH_Config.assert_called_with(0, 0, mod.AD_B_10_V)
        assert v == pytest.approx(2.5)

    def test_read_ai_voltage_raises_on_config_error(self, daq_dll_module):
        """read_ai_voltage raises Daq2502Error when D2K_AI_CH_Config fails."""
        mod = daq_dll_module
        obj = self._make_obj(mod)
        mod.dll.D2K_AI_CH_Config.return_value = -7  # ErrorInvalidAdRange
        with pytest.raises(mod.Daq2502Error):
            obj.read_ai_voltage(0)

    def test_read_ai_voltage_raises_on_read_error(self, daq_dll_module):
        """read_ai_voltage raises Daq2502Error when D2K_AI_VReadChannel fails."""
        mod = daq_dll_module
        obj = self._make_obj(mod)
        mod.dll.D2K_AI_CH_Config.return_value = 0
        mod.dll.D2K_AI_VReadChannel.return_value = -24  # ErrorAdTimeOut
        with pytest.raises(mod.Daq2502Error):
            obj.read_ai_voltage(0)

    def test_read_ai_channels_delegates(self, daq_dll_module):
        """read_ai_channels calls read_ai_voltage for each requested channel."""
        mod = daq_dll_module
        obj = self._make_obj(mod)
        mod.dll.D2K_AI_CH_Config.return_value = 0

        def fake_v_read(card, ch, ptr):
            ptr.contents.value = float(ch) * 0.5
            return 0

        mod.dll.D2K_AI_VReadChannel.side_effect = fake_v_read

        result = obj.read_ai_channels([0, 1, 2], mod.AD_B_10_V)
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(0.5)
        assert result[2] == pytest.approx(1.0)
