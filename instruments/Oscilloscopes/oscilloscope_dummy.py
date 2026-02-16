"""
Dummy OscilloscopeManager for development mode.

Provides the same interface as the OscilloscopeManager classes in
instruments/Oscilloscopes/ but prints what it would do instead of
connecting via VISA. No hardware or pyvisa required.
"""
import numpy as np
import pandas as pd


class DummyOscilloscopeManager:
    """Drop-in replacement for OscilloscopeManager that prints operations
    instead of connecting to real hardware. Used when development_mode is True."""

    def __init__(self, scope_id="DUMMY_SCOPE", read_speed=False):
        self.scope_id = scope_id
        self.read_speed = read_speed
        self.scope = None
        self.rm = None
        self._channels_configured = {}
        self._trigger_channel = 1
        self._trigger_level = 0.0
        print(f"[DEV SCOPE] Created dummy oscilloscope (id={scope_id})")

    def _delay(self):
        pass

    def _write_with_retry(self, cmd, retries=3):
        print(f"[DEV SCOPE] SCPI write: {cmd}")

    def _query_with_retry(self, cmd, retries=3):
        print(f"[DEV SCOPE] SCPI query: {cmd}")
        if "*IDN?" in cmd:
            return "DUMMY,DummyScope,000000,1.0"
        if "*OPC?" in cmd:
            return "1"
        if ":AER?" in cmd:
            return "1"
        if ":ADER?" in cmd:
            return "1"
        if ":PDER?" in cmd:
            return "1"
        return "0"

    def clear_error_queue(self):
        return []

    def is_connected(self):
        return True

    def quit(self):
        print("[DEV SCOPE] quit()")

    @staticmethod
    def save_data(dataframe, filename, window):
        print(f"[DEV SCOPE] save_data(filename={filename}, window={window}) - skipped in dev mode")
        return f"dummy_{filename}"

    def configure_scope(self, data_chs, samp_rate=None,
                        timebase_range=(-2.5e-3, 2.5e-3), high_impedance=True):
        self._channels_configured = data_chs
        print(f"[DEV SCOPE] configure_scope(channels={list(data_chs.keys())}, "
              f"samp_rate={samp_rate}, timebase={timebase_range})")

    def configure_trigger(self, trigger_channel, trigger_level, trigger_slope="+"):
        self._trigger_channel = trigger_channel
        self._trigger_level = trigger_level
        print(f"[DEV SCOPE] configure_trigger(ch={trigger_channel}, "
              f"level={trigger_level}, slope={trigger_slope})")

    def set_to_digitize(self, channels=None):
        if channels is None:
            channels = [1, 2]
        print(f"[DEV SCOPE] set_to_digitize(channels={channels})")
        return True

    def set_to_stop(self):
        print("[DEV SCOPE] set_to_stop()")
        return True

    def set_to_run(self):
        print("[DEV SCOPE] set_to_run()")
        return True

    def reset_scope(self):
        print("[DEV SCOPE] reset_scope()")

    def clear_scope(self):
        print("[DEV SCOPE] clear_scope()")

    def read_slow_return_data(self, channels):
        """Return a dummy DataFrame with synthetic data."""
        print(f"[DEV SCOPE] read_slow_return_data(channels={channels})")
        n_points = 1000
        time_data = np.linspace(-2.5e-3, 2.5e-3, n_points)
        data_dict = {'Time (s)': time_data}
        for ch in channels:
            data_dict[f'Channel {ch} Voltage (V)'] = np.random.normal(0, 0.01, n_points)
        return pd.DataFrame(data_dict)

    def read_slow_return_data_avgd(self, channels, averages=16):
        print(f"[DEV SCOPE] read_slow_return_data_avgd(channels={channels}, averages={averages})")
        return self.read_slow_return_data(channels)

    def acquire_slow_save_data(self, channels, window=0):
        print(f"[DEV SCOPE] acquire_slow_save_data(channels={channels}, window={window})")
        data = self.read_slow_return_data(channels)
        return f"dummy_data_channels_{'_'.join(map(str, channels))}"

    def arm_scope(self, max_acq_wait_sec=10, poll_interval_sec=0.1):
        print(f"[DEV SCOPE] arm_scope(max_wait={max_acq_wait_sec}s)")
        return True

    def wait_for_acquisition(self, max_acq_wait_sec=10, poll_interval_sec=0.1):
        print(f"[DEV SCOPE] wait_for_acquisition(max_wait={max_acq_wait_sec}s)")
        return True
