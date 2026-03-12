"""
Dummy instrument classes for development mode.

These classes mirror the public APIs of the real instrument controllers,
but perform no hardware I/O.  Every method prints what it would do and
returns a sensible default value so the rest of the application can run
normally without connected hardware.

Created Feb 2026 for cold-control development mode.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

_log = logging.getLogger(__name__)

__all__ = [
    "DummyDAQController",
    "DummyOscilloscopeManager",
    "DummyAWGManager",
]


# ---------------------------------------------------------------------------
#  DummyDAQController
# ---------------------------------------------------------------------------


class DummyDAQController:
    """Drop-in replacement for :class:`classes.DAQ.DAQ_controller`.

    Stores channel state in memory and prints writes to stdout.
    """

    def __init__(self, channels: list, dios: list | None = None, continuous_output: bool = False):
        """
        Parameters
        ----------
        channels : list[DAQChannel]
            DAQChannel objects (real objects — only their metadata is used).
        dios : list[DAQDio] | None
            DAQDio objects, may be ``None`` or empty.
        continuous_output : bool
            Mirror of the real flag (no effect in dummy mode).
        """
        self._master = None
        self._slaves: list = []
        self.channels = list(channels)
        self.dios = list(dios) if dios else []
        self.continuous_output = continuous_output

        # Build the same channelValues dict as the real controller
        self.channelValues: dict[int, float] = {ch.chNum: ch.defaultValue for ch in self.channels}

        # Register dummy write/read functions on DIOs (like DAQCard.validateAndRegisterDigitalIos)
        self._dio_states: dict[int, bool] = {}
        for dio in self.dios:
            self._dio_states[dio.dio_num] = False
            dio.register_write_fn(lambda state, num=dio.dio_num: self._dummy_dio_write(num, state))
            dio.register_read_fn(lambda num=dio.dio_num: self._dio_states.get(num, False))

        _log.info(
            "[DummyDAQ] Initialised with %d channels, %d DIOs", len(self.channels), len(self.dios)
        )

    # -- properties that mirror real controller --
    @property
    def master(self):
        return self._master

    @master.setter
    def master(self, value):
        self._master = value

    @property
    def slaves(self):
        return self._slaves

    @slaves.setter
    def slaves(self, value):
        self._slaves = list(value)

    # -- channel value management --

    def update_channel_value(self, ch_num: int, new_value: float) -> None:
        self.channelValues[ch_num] = new_value
        _log.debug("[DummyDAQ] Ch %d → %.4f V", ch_num, new_value)

    def write_channel_values(self) -> None:
        _log.info("[DummyDAQ] writeChannelValues: %s", self.channelValues)

    def get_channel_values(self) -> np.ndarray:
        return np.array([[v] for _, v in sorted(self.channelValues.items())])

    def toggle_continuous_output(self) -> None:
        self.continuous_output = not self.continuous_output
        _log.info("[DummyDAQ] continuousOutput → %s", self.continuous_output)

    # -- DIO --

    def _dummy_dio_write(self, dio_num: int, state: bool) -> None:
        self._dio_states[dio_num] = state
        _log.debug("[DummyDAQ] DIO %d write → %s", dio_num, state)

    def update_dio(self, dio_num: int, value: bool) -> None:
        _log.info("[DummyDAQ] DIO %d → %s", dio_num, value)

    # -- sequence load / play --

    def validate_and_correct_control_array(self, control_array: np.ndarray) -> np.ndarray:
        seq_chs, num_samps = control_array.shape
        tot_chs = len(self.channels)
        if seq_chs < tot_chs:
            control_array = np.vstack([control_array, np.zeros([tot_chs - seq_chs, num_samps])])
        return control_array

    def write(self, value_array: np.ndarray) -> None:
        _log.info("[DummyDAQ] write array shape %s", value_array.shape)

    def load(self, sequence_array: np.ndarray) -> None:
        _log.info("[DummyDAQ] load sequence shape %s", sequence_array.shape)

    def play(self, t_step: float = 1.0, clear_cards: bool = True, buffer_id=None) -> None:
        _log.info("[DummyDAQ] play  t_step=%.2f µs  clearCards=%s", t_step, clear_cards)

    def clear_cards(self) -> None:
        _log.info("[DummyDAQ] clearCards")

    def enslave(self, slave) -> None:
        _log.info("[DummyDAQ] enslave (no-op)")

    def emancipate(self, slave) -> None:
        _log.info("[DummyDAQ] emancipate (no-op)")

    def release_all(self) -> None:
        _log.info("[DummyDAQ] release_all")

    # -- queries --

    def get_channels(self, only_visible: bool = False) -> list:
        if only_visible:
            return [ch for ch in self.channels if ch.isUIVisible]
        return list(self.channels)

    def get_dios(self) -> list:
        return list(self.dios)

    def get_channel_number_name_dict(self, only_visible: bool = False) -> dict:
        chs = self.get_channels(only_visible)
        return {ch.chNum: ch.chName for ch in chs}

    def get_channel_calibration_dict(self) -> dict:
        result = {}
        for ch in self.channels:
            if ch.isCalibrated:
                result[ch.chNum] = (
                    ch.calibrationUnits,
                    ch.calibrationToVFunc,
                    ch.calibrationFromVFunc,
                )
        return result


# ---------------------------------------------------------------------------
#  DummyOscilloscopeManager
# ---------------------------------------------------------------------------


class DummyOscilloscopeManager:
    """Drop-in replacement for :class:`instruments.Oscilloscopes.keysight_3104A.OscilloscopeManager`."""

    def __init__(
        self,
        scope_id: str = "DUMMY::SCOPE",
        read_speed: bool = False,
    ):
        self.scope_id = scope_id
        self.read_speed = read_speed
        self._log = logging.getLogger(f"{__name__}.DummyScope")
        self._log.info("[DummyScope] Created (id=%s)", scope_id)

    # -- error / connectivity --

    def clear_error_queue(self) -> list:
        return []

    def is_connected(self) -> bool:
        return True

    def quit(self) -> None:
        self._log.info("[DummyScope] quit")

    # -- static helpers (unchanged — they process local files) --

    @staticmethod
    def save_data(dataframe: pd.DataFrame, filename: str, window) -> str:
        full_name = f"dummy_{filename}_w{window}.csv"
        dataframe.to_csv(full_name, index=False)
        return full_name

    @staticmethod
    def csv_analysis(filename: str) -> None:
        _log.info("[DummyScope] csv_analysis(%s) — skipped", filename)

    @staticmethod
    def process_scope_data(filename: str) -> None:
        _log.info("[DummyScope] process_scope_data(%s) — skipped", filename)

    # -- configuration --

    def configure_scope(
        self,
        data_chs: dict,
        samp_rate: float = 1e10,
        timebase_range: tuple = (-2.5e-3, 2.5e-3),
        high_impedance: bool = True,
    ) -> None:
        self._log.info(
            "[DummyScope] configure_scope chs=%s sr=%.2e", list(data_chs.keys()), samp_rate
        )

    def configure_trigger(
        self,
        trigger_channel: int,
        trigger_level: float,
        trigger_slope: str = "+",
    ) -> None:
        self._log.info(
            "[DummyScope] configure_trigger ch=%d level=%.3f slope=%s",
            trigger_channel,
            trigger_level,
            trigger_slope,
        )

    def configure_from_config(self, scope_config, trigger_slope: str = "+") -> None:
        """Configure from a :class:`ScopeConfiguration` — delegates to existing methods."""
        self.configure_scope(
            scope_config.data_channels,
            samp_rate=scope_config.sample_rate,
            timebase_range=scope_config.time_range,
        )
        self.configure_trigger(
            scope_config.trigger_channel,
            scope_config.trigger_level,
            trigger_slope,
        )

    def set_to_digitize(self, channels: list | None = None) -> bool:
        if channels is None:
            channels = [1, 2]
        self._log.info("[DummyScope] set_to_digitize %s", channels)
        return True

    def set_to_stop(self) -> bool:
        self._log.info("[DummyScope] set_to_stop")
        return True

    def reset_scope(self) -> None:
        self._log.info("[DummyScope] reset_scope")

    def clear_scope(self) -> None:
        self._log.info("[DummyScope] clear_scope")

    # -- acquisition --

    def arm_scope(self, max_acq_wait_sec: float = 10, poll_interval_sec: float = 0.1) -> bool:
        self._log.info("[DummyScope] arm_scope (instant)")
        return True

    def wait_for_acquisition(
        self, max_acq_wait_sec: float = 1, poll_interval_sec: float = 0.01
    ) -> bool:
        self._log.info("[DummyScope] wait_for_acquisition (instant)")
        return True

    def read_slow_return_data(self, channels: list) -> pd.DataFrame:
        """Return a synthetic DataFrame that matches the real scope output format."""
        n_points = 1000
        t = np.linspace(-2.5e-3, 2.5e-3, n_points)
        data = {"Time (s)": t}
        for ch in channels:
            data[f"Channel {ch} Voltage (V)"] = np.zeros(n_points)
        self._log.info(
            "[DummyScope] read_slow_return_data → %d pts x %d chs", n_points, len(channels)
        )
        return pd.DataFrame(data)

    def acquire_slow_save_data(self, channels: list, window: int = 0) -> str:
        df = self.read_slow_return_data(channels)
        fname = self.save_data(df, "dummy_acquisition", window)
        return fname


# ---------------------------------------------------------------------------
#  DummyAWGManager
# ---------------------------------------------------------------------------


class DummyAWGManager:
    """Drop-in replacement for :class:`instruments.WX218x.awg_manager.AWGManager`."""

    def __init__(
        self,
        resource_id: str = "DUMMY::AWG",
        timeout_ms: int = 30_000,
    ) -> None:
        self._log = logging.getLogger(f"{__name__}.DummyAWG")
        self.resource_id = resource_id
        self._sample_rate: float = 1e9
        self._log.info("[DummyAWG] Created (id=%s)", resource_id)

    # -- context manager --

    def __enter__(self) -> DummyAWGManager:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"DummyAWGManager(resource_id={self.resource_id!r})"

    # -- error / connectivity --

    def clear_error_queue(self) -> list:
        return []

    def is_connected(self) -> bool:
        return True

    def check_errors(self) -> bool:
        return True  # no errors

    # -- lifecycle --

    def reset(self) -> None:
        self._log.info("[DummyAWG] reset")

    def reboot(self) -> None:
        self._log.info("[DummyAWG] reboot")

    def close(self) -> None:
        self._log.info("[DummyAWG] close")

    # -- run control --

    def abort(self) -> None:
        self._log.info("[DummyAWG] abort")

    def initiate(self) -> None:
        self._log.info("[DummyAWG] initiate")

    def wait_opc(self, timeout_s: float = 10.0) -> bool:
        return True

    def trigger(self) -> None:
        self._log.info("[DummyAWG] trigger")

    # -- channel selection & output --

    def select_channel(self, channel: int) -> None:
        self._log.info("[DummyAWG] select_channel %d", channel)

    def enable_channel(self, channel: int) -> None:
        self._log.info("[DummyAWG] enable_channel %d", channel)

    def disable_channel(self, channel: int) -> None:
        self._log.info("[DummyAWG] disable_channel %d", channel)

    # -- coupling --

    def enable_coupling(self) -> None:
        self._log.info("[DummyAWG] enable_coupling")

    def disable_coupling(self) -> None:
        self._log.info("[DummyAWG] disable_coupling")

    # -- clock / sample rate --

    def set_sample_rate(self, sample_rate: float, channels: tuple[int, ...] | None = None) -> None:
        self._sample_rate = sample_rate
        self._log.info(
            f"[DummyAWG] set_sample_rate {sample_rate:.2e} on channels {channels or 'all'}"
        )

    def get_sample_rate(self) -> float:
        return self._sample_rate

    # -- output mode --

    def set_output_mode(self, mode: str = "USER", channels: tuple[int, ...] | None = None) -> None:
        self._log.info("[DummyAWG] set_output_mode %s on channels %s", mode, channels or "all")

    # -- run mode --

    def set_continuous(self, on: bool = True) -> None:
        self._log.info("[DummyAWG] set_continuous %s", on)

    def set_trigger_source(self, source: str = "EXT") -> None:
        self._log.info("[DummyAWG] set_trigger_source %s", source)

    def set_trigger_level(self, level: float = 1.6) -> None:
        self._log.info("[DummyAWG] set_trigger_level %.2f", level)

    def set_trigger_slope(self, slope: str = "POS") -> None:
        self._log.info("[DummyAWG] set_trigger_slope %s", slope)

    def set_burst_count(self, count: int = 1) -> None:
        self._log.info("[DummyAWG] set_burst_count %d", count)

    # -- amplitude / offset --

    def set_amplitude(self, channel: int, amplitude: float) -> None:
        self._log.info("[DummyAWG] set_amplitude ch%d %.4f V", channel, amplitude)

    def set_amplitude_all(self, amplitude: float) -> None:
        self._log.info("[DummyAWG] set_amplitude_all %.4f V", amplitude)

    def set_offset(self, channel: int, offset: float) -> None:
        self._log.info("[DummyAWG] set_offset ch%d %.4f V", channel, offset)

    def set_output_coupling(self, mode: str = "DC") -> None:
        self._log.info("[DummyAWG] set_output_coupling %s", mode)

    def play_sine_wave(self, channel: int, frequency: float, amplitude: float = 1.0) -> None:
        self._log.info(
            "[DummyAWG] play_sine_wave ch%d freq=%.2e amp=%.4f", channel, frequency, amplitude
        )

    # -- trace / waveform memory --

    def set_trace_mode(self, mode: str = "SING") -> None:
        self._log.info("[DummyAWG] set_trace_mode %s", mode)

    def define_segment(self, segment: int, length: int) -> None:
        self._log.info("[DummyAWG] define_segment seg=%d len=%d", segment, length)

    def select_segment(self, segment: int) -> None:
        self._log.info("[DummyAWG] select_segment %d", segment)

    def delete_all_segments(self) -> None:
        self._log.info("[DummyAWG] delete_all_segments")

    def delete_segment(self, segment: int) -> None:
        self._log.info("[DummyAWG] delete_segment %d", segment)

    def clear_all(self) -> None:
        self._log.info("[DummyAWG] clear_all")

    # -- waveform upload --

    def upload_waveform(
        self,
        waveform_data: np.ndarray,
        segment: int = 1,
        channel: int | None = None,
    ) -> bool:
        self._log.info(
            "[DummyAWG] upload_waveform seg=%d ch=%s len=%d",
            segment,
            channel,
            len(waveform_data),
        )
        return True

    # -- marker --

    def configure_marker(
        self,
        marker: int = 2,
        position: int = 0,
        width: int = 4,
        delay: float = 0.0,
        channel: int | None = None,
    ) -> None:
        self._log.info("[DummyAWG] configure_marker m=%d pos=%d w=%d", marker, position, width)

    def disable_marker(self, marker: int = 1, channel: int | None = None) -> None:
        self._log.info("[DummyAWG] disable_marker %d", marker)

    # -- sequence --

    def define_sequence_step(self, step: int, segment: int, loops: int = 1, jump: int = 0) -> None:
        self._log.info(
            "[DummyAWG] define_sequence_step step=%d seg=%d loops=%d", step, segment, loops
        )

    def set_sequence_advance(self, mode: str = "AUTO") -> None:
        self._log.info("[DummyAWG] set_sequence_advance %s", mode)

    def set_sequence_length(self, length: int) -> None:
        self._log.info("[DummyAWG] set_sequence_length %d", length)

    def select_sequence(self, seq_num: int) -> None:
        self._log.info("[DummyAWG] select_sequence %d", seq_num)

    def delete_all_sequences(self) -> None:
        self._log.info("[DummyAWG] delete_all_sequences")

    # -- compound / high-level --

    def configure_for_triggered_output(
        self,
        _sample_rate: float,
        _channels: list,
        _burst_count: int,
        _amplitudes: list,
        _offsets: list,
    ) -> None:
        self._log.info(
            "[DummyAWG] configure_for_triggered_output sr=%.2e chs=%s burst=%d",
            _sample_rate,
            _channels,
            _burst_count,
        )

    def upload_and_arm(self, awg_cfg) -> None:
        self._log.info("[DummyAWG] upload_and_arm (config=%s)", type(awg_cfg).__name__)
