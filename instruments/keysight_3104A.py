"""
Created on 22/05/2025.
@authors: Marina Llanero Pinero, Matt King


@description: This script contains the OscilloscopeManager class, which is used to manage
the connection to and data acquisition from an oscilloscope (Keysight 3104A / InfiniiVision 3000T).
"""

import numpy as np
import pyvisa as visa
import pandas as pd
import os
from datetime import datetime
import time
import logging
import matplotlib.pyplot as plt

# Robustness: retries and delays for flaky USB/SCPI
DEFAULT_WRITE_QUERY_RETRIES = 3
RETRY_DELAY_SEC = 0.15
COMMAND_DELAY_SEC = 0.02
DEFAULT_TIMEOUT_MS = 60000  # 60 s for long acquisitions


class OscilloscopeManager:

    def __init__(self, scope_id="USB0::0x0957::0x17A0::MY54280441::0::INSTR", read_speed=False):  # 'USB0::0x2A8D::0x900E::MY53450121::0::INSTR'):
        self.scope_id = scope_id
        self.read_speed = read_speed
        self._log = logging.getLogger(__name__)

        try:
            self.rm = visa.ResourceManager()
            self.scope = self.rm.open_resource(scope_id)
            self.scope.timeout = DEFAULT_TIMEOUT_MS

            self.scope.chunk_size = 1024 * 1024
            self.scope.read_termination = '\n'
            self.scope.write_termination = '\n'

            _ = self._query_with_retry("*IDN?")
            print("Connected to the scope: ", _)

        except visa.Error as e:
            print(f"Error al conectar con el osciloscopio: {e}")
            raise

    def _delay(self):
        """Small delay between SCPI commands to avoid USB/scope buffer issues."""
        time.sleep(COMMAND_DELAY_SEC)

    def _write_with_retry(self, cmd, retries=DEFAULT_WRITE_QUERY_RETRIES):
        """Send SCPI command with retries. Raises last exception on failure."""
        last_exc = None
        for attempt in range(retries):
            try:
                self.scope.write(cmd)
                self._delay()
                return
            except Exception as e:
                last_exc = e
                self._log.warning("Scope write attempt %d failed: %s", attempt + 1, e)
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY_SEC)
        raise last_exc

    def _query_with_retry(self, cmd, retries=DEFAULT_WRITE_QUERY_RETRIES):
        """Send SCPI query with retries. Returns response string. Raises last exception on failure."""
        last_exc = None
        for attempt in range(retries):
            try:
                resp = self.scope.query(cmd)
                self._delay()
                return resp
            except Exception as e:
                last_exc = e
                self._log.warning("Scope query attempt %d failed: %s", attempt + 1, e)
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY_SEC)
        raise last_exc

    def clear_error_queue(self):
        """Read and clear the instrument error queue. Returns list of (code, message) or empty."""
        errors = []
        try:
            while True:
                s = self._query_with_retry("SYSTem:ERRor?", retries=2).strip()
                if s.startswith("0,") and ("No error" in s or "No Error" in s):
                    break
                parts = s.split(",", 1)
                code = int(parts[0]) if parts else 0
                msg = parts[1].strip('"') if len(parts) > 1 else s
                errors.append((code, msg))
                if code == 0:
                    break
        except Exception as e:
            self._log.debug("Could not clear error queue: %s", e)
        return errors

    def is_connected(self):
        """Return True if the scope responds to *IDN?."""
        try:
            self.scope.query("*IDN?")
            return True
        except Exception:
            return False

    def quit(self):
        """
        Function to end the connection to the scope at the end of the program.
        """
        try:
            if self.scope is not None:
                self.scope.close()
                self.scope = None
        except Exception as e:
            self._log.warning("Error closing scope: %s", e)
        try:
            if self.rm is not None:
                self.rm.close()
                self.rm = None
        except Exception as e:
            self._log.warning("Error closing resource manager: %s", e)


    @staticmethod
    def save_data(dataframe, filename, window):
            """
            Static method to save a dataframe to a file. 
            Inputs:
             - dataframe (pd.Dataframe): The dataframe to be stored as a csv
             - filename (str): desired name of the file
             
            Returns:
             - full_name (str): full name of the file including file path
            """

            # Get current date and time
            current_date = datetime.now().strftime("%Y-%m-%d")
            current_time = datetime.now().strftime("%H-%M-%S")

            # Ensure the new directory exists
            directory = os.path.join("data", current_date)
            os.makedirs(directory, exist_ok=True) 

            # Creates full file name including time and parent folders
            full_name = f"{window}_{current_time}_{filename}"
            full_name = os.path.join(directory, full_name)

            # Saves the dataframe
            dataframe.to_csv(full_name, index=False)
            print(f"Data saved to {full_name}")
            return full_name


    @staticmethod
    def csv_analysis(filename):
        """
        Static method to plot data from a csv
        Inputs:
         - filename (str): path to the file from which to extract the data
        """

        # Load data from CSV
        data = pd.read_csv(filename)

        title = filename.split("\\")[-1]

        # Plot the data
        plt.figure(figsize=(10, 6))
        plt.plot(data['Time (s)'], data['Voltage (V)'], linestyle="None", marker=".", color="black")
        plt.xlabel('Time (s)')
        plt.ylabel('Voltage (V)')
        plt.title(title)
        plt.grid(True)
        plt.show()


    @staticmethod
    def process_scope_data(filename):
        # Read the CSV file into a DataFrame
        df = pd.read_csv(filename)
        
        # Display basic information about the data
        print("Data Overview:")
        print(df.head())
        print("\nSummary Statistics:")
        print(df.describe())
        
        # Plot each channel's voltage data over time
        plt.figure(figsize=(10, 6))
        for column in df.columns:
            if "Voltage (V)" in column:
                plt.plot(df['Time (s)'], df[column], label=column)
        
        # Customize the plot
        plt.title("Oscilloscope Data")
        plt.xlabel("Time (s)")
        plt.ylabel("Voltage (V)")
        plt.legend()
        plt.grid()
        plt.tight_layout()
        
        # Show the plot
        plt.show()


    def configure_scope(self, data_chs, samp_rate=1e10, timebase_range=(-2.5e-3, 2.5e-3),\
                        high_impedance=True):
        """
        Function to configure the general scope settings.
        Inputs:
         - data_chs: Dict mapping channel number to either (lower, upper) voltage range
           or a dict with 'range' (tuple), 'impedance' ('high'|'low'), 'coupling' ('AC'|'DC').
           If a tuple is given, impedance and coupling default to high and DC.
         - samp_rate (float): Rate at which samples are collected
         - timebase_range (tuple): Start and stop time for the timebase
         - high_impedance (bool): Used only when data_chs values are plain (lower, upper) tuples.
        """
        print("configuring the scope settings")
        self.clear_error_queue()
        self._write_with_retry('ACQUIRE:TYPE HRESOLUTION')

        # set timebase
        t_start, t_stop = timebase_range
        time_span = t_stop - t_start
        time_center = (t_start + t_stop) / 2
        self._write_with_retry('TIMEBASE:REFERENCE CENTER')
        self._write_with_retry(f"TIMEBASE:RANGE {time_span}")
        self._write_with_retry(f"TIMEBASE:POSITION {time_center}")

        for channel, ch_cfg in data_chs.items():
            if isinstance(ch_cfg, dict):
                lower, upper = ch_cfg['range']
                impedance = ch_cfg.get('impedance', 'high').lower()
                coupling = ch_cfg.get('coupling', 'DC').upper()
            else:
                lower, upper = ch_cfg[0], ch_cfg[1]
                impedance = 'high' if high_impedance else 'low'
                coupling = 'DC'

            if impedance in ("low", "50", "50ohm") and coupling == "AC":
                raise ValueError(f"Invalid configuration for channel {channel}: 50 ohm impedance cannot be used with AC coupling.")
            if impedance in ("low", "50", "50ohm") and (upper - lower) > 5:
                raise ValueError(f"Invalid voltage range for channel {channel}: 50 ohm impedance is limited to 5V range.")

            if impedance in ('high', '1meg', '1m'):
                self._write_with_retry(f":CHANnel{channel}:IMPedance ONEMeg")
            elif impedance in ('low', '50', '50ohm'):
                self._write_with_retry(f":CHANnel{channel}:IMPedance FIFty")
            else:
                raise ValueError(f"Invalid impedance for channel {channel}: {impedance!r}. Use 'high' or 'low'.")

            if coupling not in ('AC', 'DC'):
                raise ValueError(f"Invalid coupling for channel {channel}: {coupling!r}. Use 'AC' or 'DC'.")
            self._write_with_retry(f":CHANnel{channel}:COUPling {coupling}")

            v_range = upper - lower
            self._write_with_retry(f":CHANnel{channel}:RANGe {v_range}")

            v_offset = (upper + lower) / 2
            self._write_with_retry(f":CHANnel{channel}:OFFSet {v_offset}")

        self._write_with_retry('WAVEFORM:FORMAT WORD')
        self.clear_error_queue()
        print("scope settings configured")


    def configure_trigger(self, trigger_channel, trigger_level, trigger_slope="+"):
        """
        Function to configure the trigger settings of the oscilloscope.
        Inputs:
         - trigger_channel (int): Channel on which to set the trigger
         - trigger_level (float): Voltage level at which to trigger
         - trigger_slope (str): Slope of the trigger, either '+' or '-'
        """
        self._write_with_retry(":TRIGGER:SWEEP NORMal")
        self._write_with_retry(":TRIGGER:MODE EDGE")
        self._write_with_retry(f":TRIGGER:EDGE:SOURCE CHANNEL{trigger_channel}")
        self._write_with_retry(f":TRIGGER:EDGE:LEVEL {trigger_level}")

        if trigger_slope == "+":
            self._write_with_retry(":TRIGGER:EDGE:SLOPE POSITIVE")
        elif trigger_slope == "-":
            self._write_with_retry(":TRIGGER:EDGE:SLOPE NEGATIVE")
        else:
            raise ValueError(f"Invalid value for trigger_slope: {trigger_slope}")

    

    def set_to_digitize(self, channels=[1, 2]):
        """
        Function to set the scope to digitize mode. This is the primary way to collect
        data from the scope. Use this before sending a trigger pulse to the scope.
        """
        query_result = self._query_with_retry(':DIGitize;*OPC?')
        ok = query_result.strip() == '1'
        if ok:
            print(f"Oscilloscope digitized channels {channels}.")
        return ok

    def set_to_stop(self):
        """
        Function to set the scope to stop mode. This is used to stop the scope from collecting data.
        """
        self._write_with_retry(':STOP')
        print("Oscilloscope set to stop mode.")
        return True

    def reset_scope(self):
        """
        Function to reset the oscilloscope. This will clear all settings and data.
        """
        try:
            self.scope.clear()
        except Exception:
            pass
        self._write_with_retry('*RST')

    def clear_scope(self):
        """
        Function to clear the oscilloscope. This will clear all settings and data.
        """
        try:
            self.scope.clear()
        except Exception:
            pass
        self.clear_error_queue()
        print("Oscilloscope cleared.")




    def read_slow_return_data(self, channels):   
        """
        Function to sample data from multiple channels when a trigger has been manually 
        set on the oscilloscope. This is a slower method of acquiring data, and is used
        when the read speed is slow. It returns the data as a DataFrame rather than saving
        it to a file.

        Inputs:
         - channels (list of int): List of channels to collect data from

        Returns:
         - DataFrame with time and channel voltage columns, or None on failure.
        """
        if self.read_speed is None:
            raise ValueError("Scope read speed not set. Please configure the scope first.")
        if self.read_speed is True:
            print("Warning: Scope is set to high speed.")

        collected_data = None
        self.clear_error_queue()
        self._write_with_retry(':WAVEFORM:POINTS:MODE NORMAL')
        self._write_with_retry('WAVEFORM:FORMAT WORD')
        self._write_with_retry('WAVEFORM:BYTEORDER LSBFIRST')

        for channel in channels:
            self._write_with_retry(f'WAVEFORM:SOURCE CHANNEL{channel}')
            print(f"Collecting data from channel {channel}...")
            errs = self.clear_error_queue()
            if errs:
                for code, msg in errs:
                    print(f"Scope errors: {code}, {msg}")
            opc = self._query_with_retry('*OPC?').strip()
            if opc != '1':
                raise RuntimeError(f"Operation did not complete successfully. OPC returned: {opc!r}")
            preamble = self._query_with_retry('WAVEFORM:PREAMBLE?')
            pre = preamble.split(',')
            print(f"Preamble info: {pre}")
            num_points = int(pre[2])    
            x_incr = float(pre[4])  # XINCREMENT is at index 4
            x_orig = float(pre[5])  # XORIGIN is at index 5
            y_incr = float(pre[7])  # YINCREMENT is at index 7
            y_orig = float(pre[8])  # YORIGIN is at index 8
            y_ref = float(pre[9])   # YREFERENCE is at index 9

            # Binary read can timeout; retry a few times
            for attempt in range(DEFAULT_WRITE_QUERY_RETRIES):
                try:
                    raw_data = self.scope.query_binary_values(
                        'WAVEFORM:DATA?', datatype='H', container=np.array,
                          is_big_endian=False, chunk_size=1024 * 1024
                    )
                    break
                except Exception as e:
                    if attempt == DEFAULT_WRITE_QUERY_RETRIES - 1:
                        raise
                    self._log.warning("WAVEFORM:DATA? attempt %d failed: %s", attempt + 1, e)
                    time.sleep(RETRY_DELAY_SEC)

            y_data = (raw_data-y_ref) * y_incr + y_orig

            if len(y_data) == 0:
                raise ValueError(f"No data collected from channel {channel}.")


            time_data = np.linspace(x_orig, x_orig + x_incr * (num_points), num_points)
            collected_data = pd.DataFrame({'Time (s)': time_data})

            collected_data[f'Channel {channel} Voltage (V)'] = y_data

        return collected_data
        

    def acquire_slow_save_data(self, channels, window=00):   
        """
        Function to sample data from multiple channels when a trigger has been manually 
        set on the oscilloscope. This is a slower method of acquiring data, and is used
        when the read speed is slow. It saves the data to a file rather than returning it.

        Inputs:
         - channels (list of int): List of channels to collect data from
         - window (int): Name for saving the data

        Returns:
         - filename (str): File path of the saved data
        """
        if self.read_speed is None:
            raise ValueError("Scope read speed not set. Please configure the scope first.")
        if self.read_speed is True:
            print("Warning: Scope is set to high speed. Consider using acquire_slow_return_data() instead.")

        collected_data = self.read_slow_return_data(channels)
        if collected_data is None:
            raise RuntimeError("read_slow_return_data returned None")
        channels_str = "_".join(map(str, channels))
        filename = self.save_data(collected_data, f"channels_{channels_str}_data", window)
        return filename
    




    def arm_scope(self, max_acq_wait_sec=10, poll_interval_sec=0.1):
        """
        Function to arm the oscilloscope ready to collect data when it receives a trigger.
        On timeout or error we clear the scope buffer but do NOT close the connection,
        so the caller can retry or continue.
        """
        self.clear_error_queue()
        self._write_with_retry(':SINGLE')

        # Poll :AER? (Trigger Armed Event Register); returns 1 when armed.
        print("Waiting for oscilloscope to arm (polling :AER?)...\n")
        start_time = time.perf_counter()
        armed_status = 0
        acq_started = False

        while armed_status != 1 and (time.perf_counter() - start_time) <= max_acq_wait_sec:
            time.sleep(poll_interval_sec)
            try:
                query_result = self._query_with_retry(":AER?")
                armed_status = int(query_result.strip().split()[0] if query_result.strip() else 0)
                if armed_status == 1:
                    acq_started = True
                    break
            except Exception as e:
                print(f"Error during arming poll: {e}")
                acq_started = False
                break

        if not acq_started:
            print("Oscilloscope did not arm within the maximum wait time.")
            try:
                self.scope.clear()
            except Exception:
                pass
            self.clear_error_queue()
            raise RuntimeError("Oscilloscope failed to arm within the specified time.")

        print("Oscilloscope is armed and ready for trigger!")
        return True
    

    def wait_for_acquisition(self, max_acq_wait_sec=1, poll_interval_sec=0.01):
        """
        Wait for acquisition to complete after trigger. Polls :ACQuire:COMPlete?, :TER?, :RSTATE?.
        """
        print("Waiting for acquisition to complete...")
        start_time = time.perf_counter()
        triggered = False
        success = False
        acq_complete_bool = False
        run_state = ""

        while not success and (time.perf_counter() - start_time) <= max_acq_wait_sec:
            time.sleep(poll_interval_sec)
            try:
                acq_complete_str = self._query_with_retry(":ACQuire:COMPlete?").strip()
                run_state = self._query_with_retry(":RSTATE?").strip().upper()

                try:
                    acq_pct = int(acq_complete_str.split()[0])
                except (ValueError, IndexError):
                    acq_pct = 0
                acq_complete_bool = acq_pct >= 100
                run_state_bool = "STOP" in run_state
                #print(f"Acquisition complete: {acq_complete_bool}, {acq_pct}% complete.\nRun state bool: {run_state_bool}")

                # Only read :TER? when acquisition appears done (TER is cleared on read)
                if acq_complete_bool and run_state_bool and triggered is False:
                    ter_str = self._query_with_retry(":TER?").strip()
                    triggered = ter_str == "+1"
                    #print(f"Triggered status from :TER?: {ter_str} -> {triggered}")

                success = acq_complete_bool and run_state_bool and triggered
                if success:
                    break
            except Exception as e:
                print(f"Error during completion poll: {e}")
                break

        if not success:
            print("Acquisition did not complete within the maximum wait time.")

        print(f"Acquisition complete: {acq_complete_bool}, {acq_pct}% complete.")
        print(f"Triggered: {triggered}, result from :TER? is {ter_str}")
        print(f"Stopped: {run_state_bool}, run state is {run_state}")

        print("Acquisition complete. Ready to retrieve data.\n")
        return success