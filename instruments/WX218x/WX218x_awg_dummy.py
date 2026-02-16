"""
Dummy AWG implementation for development mode.

Provides the same interface as WX218x_awg but prints what it would do
instead of sending commands to hardware. No DLLs or VISA connections required.
"""
from ctypes import c_int32, c_uint
import numpy as np


class DummyWX218x_awg:
    """Drop-in replacement for WX218x_awg that prints operations instead of
    calling the real DLL. Used when development_mode is True."""

    MANUFACTURER_ID = '0x168C'

    def __init__(self, name=None):
        self.name = name or 'DUMMY_AWG'
        self.vi_session = c_uint(0)
        self._channels_enabled = set()
        self._sample_rate = 1.25e9
        self._next_wfm_handle = 1
        print(f"[DEV AWG] Created dummy AWG instance (name={self.name})")

    def open(self, verify_id=False, reset=False, options_string=None):
        print(f"[DEV AWG] open(verify_id={verify_id}, reset={reset})")

    def close(self):
        print("[DEV AWG] close()")

    def reset(self):
        print("[DEV AWG] reset()")

    def enable_channel(self, channel_name):
        self._channels_enabled.add(channel_name)
        print(f"[DEV AWG] enable_channel({channel_name})")

    def disable_channel(self, channel_name):
        self._channels_enabled.discard(channel_name)
        print(f"[DEV AWG] disable_channel({channel_name})")

    def configure_output_mode(self, output_mode):
        print(f"[DEV AWG] configure_output_mode({output_mode})")

    def configure_operation_mode(self, channel_name, operation_mode):
        print(f"[DEV AWG] configure_operation_mode({channel_name}, {operation_mode})")

    def configure_standard_waveform(self, channel_name, waveform,
                                    amplitude=1, dc_offset=0,
                                    frequency=10**6, start_phase=0):
        print(f"[DEV AWG] configure_standard_waveform({channel_name}, wfm={waveform}, "
              f"amp={amplitude}, dc_offset={dc_offset}, freq={frequency}, phase={start_phase})")

    def initiate_generation(self):
        print("[DEV AWG] initiate_generation()")

    def abort_generation(self):
        print("[DEV AWG] abort_generation()")

    def set_active_channel(self, channel_name):
        print(f"[DEV AWG] set_active_channel({channel_name})")

    def configure_sample_rate(self, sample_rate):
        self._sample_rate = sample_rate
        print(f"[DEV AWG] configure_sample_rate({sample_rate})")

    def load_arbitrary_waveform_from_file(self, filename, channel_name):
        handle = c_int32(self._next_wfm_handle)
        self._next_wfm_handle += 1
        print(f"[DEV AWG] load_arbitrary_waveform_from_file({filename}, {channel_name}) -> handle={handle.value}")
        return handle

    def create_arbitrary_waveform(self, data):
        handle = c_int32(self._next_wfm_handle)
        self._next_wfm_handle += 1
        length = len(data) if hasattr(data, '__len__') else 0
        print(f"[DEV AWG] create_arbitrary_waveform(len={length}) -> handle={handle.value}")
        return handle

    def create_arbitrary_waveform_custom(self, data):
        handle = c_int32(self._next_wfm_handle)
        self._next_wfm_handle += 1
        length = len(data) if hasattr(data, '__len__') else 0
        print(f"[DEV AWG] create_arbitrary_waveform_custom(len={length}) -> handle={handle.value}")
        return handle

    def create_custom_adv(self, data1, data2):
        h1 = c_int32(self._next_wfm_handle)
        self._next_wfm_handle += 1
        h2 = c_int32(self._next_wfm_handle)
        self._next_wfm_handle += 1
        print(f"[DEV AWG] create_custom_adv(len1={len(data1)}, len2={len(data2)}) -> handles=({h1.value}, {h2.value})")
        return h1, h2

    def clear_arbitrary_waveform(self, waveform_handle=-1):
        print(f"[DEV AWG] clear_arbitrary_waveform(handle={waveform_handle})")

    def configure_arb_gain(self, channel_name, gain):
        print(f"[DEV AWG] configure_arb_gain({channel_name}, gain={gain})")

    def clear_arbitrary_sequence(self, sequence_handle=-1):
        print(f"[DEV AWG] clear_arbitrary_sequence(handle={sequence_handle})")

    def configure_arb_wave_trace_mode(self, trace_mode):
        print(f"[DEV AWG] configure_arb_wave_trace_mode({trace_mode})")

    def configure_once_count(self, channel_name, count):
        print(f"[DEV AWG] configure_once_count({channel_name}, count={count})")

    def configure_advance_mode(self, channel_name, advance_mode):
        print(f"[DEV AWG] configure_advance_mode({channel_name}, mode={advance_mode})")

    def configure_trigger_source(self, channel_name, source):
        print(f"[DEV AWG] configure_trigger_source({channel_name}, source={source})")

    def configure_trigger_level(self, channel_name, level):
        print(f"[DEV AWG] configure_trigger_level({channel_name}, level={level})")

    def configure_trigger_slope(self, channel_name, slope):
        print(f"[DEV AWG] configure_trigger_slope({channel_name}, slope={slope})")

    def configure_trigger_impedance(self, trigger_impedance):
        print(f"[DEV AWG] configure_trigger_impedance({trigger_impedance})")

    def send_software_trigger(self):
        print("[DEV AWG] send_software_trigger()")

    def configure_burst_count(self, channel_name, count):
        print(f"[DEV AWG] configure_burst_count({channel_name}, count={count})")

    def configure_marker(self, channel_name, index, source=None,
                         position=0, levels=(0, 1.2), delay=0, width=64):
        print(f"[DEV AWG] configure_marker({channel_name}, idx={index}, pos={position}, "
              f"levels={levels}, delay={delay}, width={width})")

    def configure_marker_enabled(self, channel_name, index, enabled):
        print(f"[DEV AWG] configure_marker_enabled({channel_name}, idx={index}, enabled={enabled})")

    def configure_marker_source(self, channel_name, source):
        print(f"[DEV AWG] configure_marker_source({channel_name}, source={source})")

    def configure_marker_position(self, channel_name, index, position):
        print(f"[DEV AWG] configure_marker_position({channel_name}, idx={index}, pos={position})")

    def configure_marker_high_level(self, channel_name, level):
        print(f"[DEV AWG] configure_marker_high_level({channel_name}, level={level})")

    def configure_marker_low_level(self, channel_name, level):
        print(f"[DEV AWG] configure_marker_low_level({channel_name}, level={level})")

    def configure_marker_delay(self, channel_name, index, delay):
        print(f"[DEV AWG] configure_marker_delay({channel_name}, idx={index}, delay={delay})")

    def configure_marker_width(self, channel_name, index, width):
        print(f"[DEV AWG] configure_marker_width({channel_name}, idx={index}, width={width})")

    def set_marker_width(self, channel_name, index, width):
        print(f"[DEV AWG] set_marker_width({channel_name}, idx={index}, width={width})")

    def marker_refresh(self, channel_name):
        print(f"[DEV AWG] marker_refresh({channel_name})")

    def configure_marker_index(self, channel_name, index):
        print(f"[DEV AWG] configure_marker_index({channel_name}, idx={index})")

    def configure_dig_patt_delay_mode(self, channel_name, delay_mode):
        print(f"[DEV AWG] configure_dig_patt_delay_mode({channel_name}, mode={delay_mode})")

    def configure_couple_enabled(self, enabled):
        print(f"[DEV AWG] configure_couple_enabled({enabled})")

    def _validate_response(self, response_code):
        pass  # No-op in dummy mode
