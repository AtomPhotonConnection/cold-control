"""
Created on 22 Sep 2016

@author: Tom Barrett
"""

from ctypes import POINTER, byref, c_byte, c_double, c_int8, c_int32, c_int64, c_longlong

import numpy as np

from instruments.quTAU.tdc_base_dll import TdcBaseDll
from instruments.quTAU.tdc_exception import TdcError


class TdcManager:
    """
    todo
    """

    INPUT_CHANNELS = 8

    def __init__(self, device_id=-1):
        """
        The deviceId is the unique id of the TDC device.  -1 will connect to the first
        device found.
        """
        self.deviceId = device_id

    def open(self):
        err = TdcBaseDll.init(self.deviceId)
        if err != 0:
            tdc_err = TdcError(err)
            print("Error opening TDC with message:", tdc_err.message)
            raise tdc_err

    def close(self):
        TdcBaseDll.de_initialise()

    def get_version(self):
        return TdcBaseDll.get_version()

    def get_timebase(self):
        """Returns the timebase of the TDC in seconds. This timebase is used as the
        time unit in many other functions.
        """
        return TdcBaseDll.get_timebase()

    def get_dev_type(self):
        return TdcBaseDll.get_dev_type()

    def get_device_params(self):
        channel_mask, coinc_win, exp_time = c_int32(), c_int32(), c_int32()
        err = TdcBaseDll.get_device_params(byref(channel_mask), byref(coinc_win), byref(exp_time))
        if err != 0:
            raise TdcError(err)
        return (channel_mask.value, coinc_win.value, exp_time.value)

    def enable_tdc_input(self, enabled):
        err = TdcBaseDll.enable_tdc_input(enabled)
        if err != 0:
            raise TdcError(err)

    def set_enabled_channels(self, channels):
        """
        Sets the channels that are enabled.  Channels is a list of channel
        numbers to be enabled wit values in range 0-7.
        Note: internally channels are numbers 0-7 which corresponds to
        1-8 on the box - because qutools are actually tools.
        """
        if len(channels) > 0:
            bitstring = ""
            for k in range(max(channels) + 1):
                bitstring = "1" + bitstring if k in channels else "0" + bitstring
        else:
            bitstring = "0"

        err = TdcBaseDll.enable_channels(int(bitstring, 2))
        if err != 0:
            raise TdcError(err)

    def set_timestamp_buffer_size(self, size=1000000):
        """
        Sets the size of the ring buffer (note the buffer is cleared when
        his function is called.  This function must be called before any
        timestamps can be recored into the buffer.
            size    Buffer size; Range = 1 ... 1000000
        """
        if not 1 <= size <= 1000000:
            print("Buffer size must be in range 1 ... 1000000.")
            size = int(np.clip(size, 1, 1000000))
        err = TdcBaseDll.set_timestamp_buffer_size(size)
        if err != 0:
            raise TdcError(err)

    def get_timestamp_buffer_size(self):
        size = c_int32()
        err = TdcBaseDll.get_timestamp_buffer_size(byref(size))
        if err != 0:
            raise TdcError(err)
        return size.value

    def set_exposure_time(self, exposure_time=1000):
        """
        Sets the exposure time (or integration time) of the internal
        coincidence counters.
        Exposure time in ms with range = 0 ... 65535
        """
        err = TdcBaseDll.set_exposure_time(exposure_time)
        if err != 0:
            raise TdcError(err)

    def get_timestamps(self, reset_buffer=True):
        """
        Get the timestamps in the buffer. The reset_buffer boolean determines
        whether the buffer should be cleared once the timestamps have been retrieved.
        """
        buffer_size = self.get_timestamp_buffer_size()

        timestamps, channels, valid = (
            np.array([-1] * buffer_size, c_int64),
            np.array([-1] * buffer_size, c_int8),
            c_int32(),
        )

        TdcBaseDll.get_last_timestamps(
            reset_buffer,
            timestamps.ctypes.data_as(POINTER(c_int64)),
            channels.ctypes.data_as(POINTER(c_int8)),
            byref(valid),
        )
        return timestamps, channels, valid.value

    def freeze_buffers(self, freeze_buffers):
        """
        The function can be used to freeze the internal buffers, allowing to
        retrieve multiple histograms with the same integration time. When
        frozen, no more events are added to the built-in histograms and
        timestamp buffer. The coincidence counters are not affected.
        Initially, the buffers are not frozen. All types of histograms
        calculated by software are affected.
        """
        TdcBaseDll.freeze_buffers(freeze_buffers)

    def clear_buffer(self):
        self.get_timestamps(reset_buffer=True)

    def generate_timestamps(self, sim_type, par, count):
        """
        Auto-generates timestamps for testing purposes. At least one channel has to be enabled!
            sim_type Type of time diff distribution (use TDC_SimType value from TDC_BaseDLL).
            par      Type specific parameter set. Parameters should be chosen so that most time
                     diffs are positive. Negative diffs are dropped. For both TDC_SimType.SIM_FLAT
                     and TDC_SimType.SIM_NORMAL requires 2 parameters: center and width for time
                     diffs in TDC units.
            count    Number of timestamps to generate
        """
        array = np.array(par)
        err = TdcBaseDll.generate_timestamps(
            sim_type, array.astype(c_double).ctypes.data_as(POINTER(c_double)), count
        )
        if err != 0:
            raise TdcError(err)

    def input_timestamps(self, timestamps, channels, count):
        """
        Input timestamps for testing purposes. At least one channel has to be enabled!

        timestamps: Array of timestamps to process. The timestamps
                    should be in strictly increasing order,
                    otherwise some functions will fail.
        channels:   Array of corresponding channel numbers.
        count:      Number of valid elements in both arrays
        """
        timestamps = np.array(timestamps).astype(c_longlong)
        channels = np.array(channels).astype(c_byte)
        err = TdcBaseDll.input_timestamps(
            timestamps.ctypes.data_as(POINTER(c_longlong)),
            channels.ctypes.data_as(POINTER(c_byte)),
            count,
        )
        if err != 0:
            print(err)
            raise TdcError(err)

    def switch_termination(self, termination_on):
        """
        Switches the 50 Ohm termination of input lines on or off. The function
        requires an 1A type hardware, otherwise TDC_OutOfRange is returned.

        Only for 1A models.
        """
        err = TdcBaseDll.switch_termination(termination_on)
        if err != 0:
            raise TdcError(err)

    def configure_signal_conditioning(self, channel, conditioning, edge, term, threshold):
        """
        Configures a channel's signal conditioning. The availability of signal
        conditioning electronics depends on the device type (TDC_getDevType);
        the function requires an 1B or 1C device. If it isn't present for the
        specified channel, TDC_OutOfRange is returned.

        Primarily, a conditioning type is selected. Depending on the type, the
        three detailed settings may be relevant or ignored by the function,
        see TDC_SignalCond. In particular, SCOND_TTL switches off the complete
        signal conditioning including the input divider (TDC_configureSyncDivider).
        For full access to the details use SCOND_MISC as type.

        Parameters
            channel      Number of the input channel to configure. For 1c
                         devices, use 0=Ext0, 1=Ext1, 2=Sync
            conditioning Type of signal conditioning. By default, the signal
                         conditioning is off (SCOND_TTL).
            edge         Selects the signal edge that is processed as an
                         event: rising (1) or falling (0)
            term         Switches the termination in the signal path on (1) or
                         off (0)
            threshold    Voltage threshold that is used to identify events, in
                         V. Allowed range is -2 ... 3V; internal resolution is 1.2mV
        """
        err = TdcBaseDll.configure_signal_conditioning(channel, conditioning, edge, term, threshold)
        if err != 0:
            raise TdcError(err)
