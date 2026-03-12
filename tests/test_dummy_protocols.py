"""Smoke tests for the dummy instrument drivers.

Verifies that :class:`DummyDAQController`, :class:`DummyOscilloscopeManager`,
and :class:`DummyAWGManager` satisfy the corresponding Protocol interfaces
defined in :mod:`instruments.protocols`.
"""

import numpy as np
import pytest

from classes.daq import DAQChannel
from instruments.dummy import DummyAWGManager, DummyDAQController, DummyOscilloscopeManager
from instruments.protocols import AWGProtocol, DAQControllerProtocol, OscilloscopeProtocol


# ---------------------------------------------------------------------------
#  Protocol compliance
# ---------------------------------------------------------------------------


class TestDummyDAQControllerProtocol:
    @pytest.fixture
    def controller(self):
        channels = [DAQChannel(i) for i in range(4)]
        return DummyDAQController(channels=channels, dios=[], continuous_ouput=False)

    def test_is_protocol_compatible(self, controller):
        """DummyDAQController must structurally match DAQControllerProtocol."""
        assert isinstance(controller, DAQControllerProtocol)

    def test_load(self, controller):
        arr = np.zeros((4, 10))
        controller.load(arr)

    def test_play(self, controller):
        controller.play(t_step=10.0, clear_cards=True)

    def test_clear_cards(self, controller):
        controller.clear_cards()

    def test_write_channel_values(self, controller):
        controller.write_channel_values()

    def test_update_and_get_channel_value(self, controller):
        controller.update_channel_value(0, 3.14)
        vals = controller.get_channel_values()
        assert vals[0, 0] == pytest.approx(3.14)

    def test_get_channels(self, controller):
        chs = controller.get_channels()
        assert len(chs) == 4

    def test_get_dios(self, controller):
        assert controller.get_dios() == []

    def test_toggle_continuous_output(self, controller):
        assert not controller.continuousOutput
        controller.toggle_continuous_output()
        assert controller.continuousOutput

    def test_get_channel_number_name_dict(self, controller):
        d = controller.get_channel_number_name_dict()
        assert isinstance(d, dict)
        assert len(d) == 4

    def test_get_channel_calibration_dict(self, controller):
        d = controller.get_channel_calibration_dict()
        assert isinstance(d, dict)


class TestDummyOscilloscopeProtocol:
    @pytest.fixture
    def scope(self):
        return DummyOscilloscopeManager()

    def test_is_protocol_compatible(self, scope):
        assert isinstance(scope, OscilloscopeProtocol)

    def test_configure_scope(self, scope):
        scope.configure_scope(data_chs={1: "V", 2: "V"})

    def test_configure_trigger(self, scope):
        scope.configure_trigger(trigger_channel=1, trigger_level=0.5)

    def test_arm_scope(self, scope):
        assert scope.arm_scope() is True

    def test_wait_for_acquisition(self, scope):
        assert scope.wait_for_acquisition() is True

    def test_read_slow_return_data(self, scope):
        df = scope.read_slow_return_data(channels=[1, 2])
        assert len(df) > 0
        assert "Time (s)" in df.columns

    def test_quit(self, scope):
        scope.quit()


class TestDummyAWGProtocol:
    @pytest.fixture
    def awg(self):
        return DummyAWGManager()

    def test_is_protocol_compatible(self, awg):
        assert isinstance(awg, AWGProtocol)

    def test_reset(self, awg):
        awg.reset()

    def test_close(self, awg):
        awg.close()

    def test_is_connected(self, awg):
        assert awg.is_connected() is True

    def test_abort_initiate_trigger(self, awg):
        awg.abort()
        awg.initiate()
        awg.trigger()

    def test_channel_operations(self, awg):
        awg.select_channel(1)
        awg.enable_channel(1)
        awg.disable_channel(1)

    def test_set_sample_rate(self, awg):
        awg.set_sample_rate(1e9)

    def test_set_amplitude_offset(self, awg):
        awg.set_amplitude(1, 0.5)
        awg.set_offset(1, 0.1)

    def test_upload_waveform(self, awg):
        data = np.zeros(100)
        result = awg.upload_waveform(data, segment=1, channel=1)
        assert result is True

    def test_configure_marker(self, awg):
        awg.configure_marker(marker=1, position=0, width=4)
