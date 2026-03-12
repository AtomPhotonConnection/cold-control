"""
Protocol classes defining the interfaces for laboratory instruments.

These use ``typing.Protocol`` so that both the real hardware drivers and the
dummy stand-ins in ``instruments.dummy`` are structurally compatible without
requiring explicit inheritance.

Usage in type annotations::

    from instruments.protocols import OscilloscopeProtocol, AWGProtocol


    def run_experiment(scope: OscilloscopeProtocol, awg: AWGProtocol) -> None: ...
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
#  Oscilloscope
# ---------------------------------------------------------------------------


@runtime_checkable
class OscilloscopeProtocol(Protocol):
    """Minimal interface expected of an oscilloscope by the experiment runners."""

    def configure_scope(
        self,
        data_chs: dict,
        samp_rate: float = ...,
        timebase_range: tuple = ...,
        high_impedance: bool = ...,
    ) -> None: ...

    def configure_trigger(
        self,
        trigger_channel: int,
        trigger_level: float,
        trigger_slope: str = ...,
    ) -> None: ...

    def configure_from_config(self, scope_config, trigger_slope: str = ...) -> None: ...

    def arm_scope(self, max_acq_wait_sec: float = ..., poll_interval_sec: float = ...) -> bool: ...

    def wait_for_acquisition(
        self,
        max_acq_wait_sec: float = ...,
        poll_interval_sec: float = ...,
    ) -> bool: ...

    def read_slow_return_data(self, channels: list) -> pd.DataFrame | None: ...

    def set_to_digitize(self, channels: list | None = ...) -> bool: ...

    def set_to_stop(self) -> bool: ...

    def quit(self) -> None: ...


# ---------------------------------------------------------------------------
#  AWG (Arbitrary Waveform Generator)
# ---------------------------------------------------------------------------


@runtime_checkable
class AWGProtocol(Protocol):
    """Minimal interface expected of an AWG by the experiment runners."""

    # -- lifecycle --
    def reset(self) -> None: ...
    def close(self) -> None: ...
    def is_connected(self) -> bool: ...

    # -- run control --
    def abort(self) -> None: ...
    def initiate(self) -> None: ...
    def trigger(self) -> None: ...

    # -- channel --
    def select_channel(self, channel: int) -> None: ...
    def enable_channel(self, channel: int) -> None: ...
    def disable_channel(self, channel: int) -> None: ...

    # -- configuration --
    def set_sample_rate(
        self, sample_rate: float, channels: tuple[int, ...] | None = ...
    ) -> None: ...

    def set_amplitude(self, channel: int, amplitude: float) -> None: ...
    def set_offset(self, channel: int, offset: float) -> None: ...

    # -- waveform upload --
    def upload_waveform(
        self,
        waveform_data: np.ndarray,
        segment: int = ...,
        channel: int | None = ...,
    ) -> bool: ...

    # -- markers --
    def configure_marker(
        self,
        marker: int = ...,
        position: int = ...,
        width: int = ...,
        delay: float = ...,
        channel: int | None = ...,
    ) -> None: ...

    # -- high-level --
    def upload_and_arm(self, awg_cfg) -> None: ...


# ---------------------------------------------------------------------------
#  DAQ Controller
# ---------------------------------------------------------------------------


@runtime_checkable
class DAQControllerProtocol(Protocol):
    """Minimal interface expected of a DAQ controller."""

    continuousOutput: bool

    def load(self, sequence_array: np.ndarray) -> None: ...
    def play(self, t_step: float = ..., clear_cards: bool = ...) -> None: ...
    def clear_cards(self) -> None: ...

    def write_channel_values(self) -> None: ...
    def update_channel_value(self, ch_num: int, new_value: float) -> None: ...
    def get_channel_values(self) -> np.ndarray: ...

    def get_channels(self, only_visible: bool = ...) -> list: ...
    def get_dios(self) -> list: ...

    def get_channel_number_name_dict(self, only_visible: bool = ...) -> dict: ...
    def get_channel_calibration_dict(self) -> dict: ...

    def toggle_continuous_output(self) -> None: ...
