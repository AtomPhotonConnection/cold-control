"""
Created on 06/02/2026.
@authors: Marina Llanero Pinero, Matt King, (Updated for Agilent 9000 Series)

@description: This script contains the OscilloscopeManager class, updated to manage
the connection to and data acquisition from an Agilent Infiniium 9000 Series Oscilloscope.
"""
from datetime import datetime
import os
import time
import logging
from typing import cast

import numpy as np
import pyvisa as visa
from pyvisa.resources import MessageBasedResource
import pandas as pd
import matplotlib.pyplot as plt

# Robustness: retries and delays for flaky USB/SCPI
DEFAULT_WRITE_QUERY_RETRIES = 3
RETRY_DELAY_SEC = 0.15
COMMAND_DELAY_SEC = 0.05 # Increased slightly for 9000 series processing
DEFAULT_TIMEOUT_MS = 10e3  # 10 s for long acquisitions


class OscilloscopeManager:

    def __init__(self, scope_id="USB0::0x0957::0x9009::MY12345678::0::INSTR", read_speed=False): 
        # Note: Default ID is a placeholder for 9000 series. Update with your specific address.
        self.scope_id = scope_id
        self.read_speed = read_speed
        self._log = logging.getLogger(__name__)

        try:
            self.rm = visa.ResourceManager()
            scope = self.rm.open_resource(scope_id)
            self.scope = cast(MessageBasedResource, scope)
            self.scope.timeout = DEFAULT_TIMEOUT_MS

            self.scope.chunk_size = 1024 * 1024
            self.scope.read_termination = '\n'
            self.scope.write_termination = '\n'

            # Clear interface and buffer
            self.scope.clear()
            
            _ = self._query_with_retry("*IDN?")
            print("Connected to the scope: ", _)

        except visa.Error as e:
            print(f"Error connecting to oscilloscope: {e}")
            raise

    def _delay(self):
        """Small delay between SCPI commands."""
        time.sleep(COMMAND_DELAY_SEC)

    def _write_with_retry(self, cmd, retries=DEFAULT_WRITE_QUERY_RETRIES):
        """Send SCPI command with retries. Raises last exception on failure."""
        last_exc = None
        for attempt in range(retries):
            try:
                self.scope = cast(MessageBasedResource, self.scope)
                self.scope.write(cmd)
                self._delay()
                return
            except Exception as e:
                last_exc = e
                self._log.warning("Scope write attempt %d failed: %s", attempt + 1, e)
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY_SEC)
        if last_exc:
            raise last_exc

    def _query_with_retry(self, cmd, retries=DEFAULT_WRITE_QUERY_RETRIES):
        """Send SCPI query with retries. Returns response string. Raises last exception on failure."""
        last_exc = None
        for attempt in range(retries):
            try:
                self.scope = cast(MessageBasedResource, self.scope)
                resp = self.scope.query(cmd)
                self._delay()
                return resp
            except Exception as e:
                last_exc = e
                self._log.warning("Scope query attempt %d failed: %s", attempt + 1, e)
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY_SEC)
        if last_exc:
            raise last_exc

    def clear_error_queue(self):
        """Read and clear the instrument error queue. Returns list of (code, message) or empty."""
        errors = []
        try:
            while True:
                s = self._query_with_retry(":SYSTem:ERRor?", retries=2)
                s = cast(str, s).strip()
                if s.startswith("0") or "No error" in s:
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
            self.scope = cast(MessageBasedResource, self.scope)
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
        plt.show()


    def configure_scope(self, data_chs, samp_rate=None, timebase_range=(-2.5e-3, 2.5e-3),\
                        high_impedance=True):
        """
        Function to configure the general scope settings for Agilent 9000 Series.
        Inputs:
         - data_chs: Dict mapping channel number to settings (range, impedance, coupling).
         - samp_rate: (Not always directly settable on 9000 without specific mode, 
           controlled via memory depth/timebase, but left for interface consistency).
         - timebase_range: Start and stop time for the timebase.
         - high_impedance: used if data_chs is simple tuple format.
        """
        print("configuring the scope settings")
        self.clear_error_queue()
        
        self._write_with_retry(':ACQuire:MODE HRESolution') 

        # set timebase
        t_start, t_stop = timebase_range
        time_span = t_stop - t_start
        time_center = (t_start + t_stop) / 2
        self._write_with_retry(':TIMebase:REFerence CENTer')
        self._write_with_retry(f":TIMebase:RANGe {time_span}")
        self._write_with_retry(f":TIMebase:POSition {time_center}")

        for channel, ch_cfg in data_chs.items():
            if isinstance(ch_cfg, dict):
                lower, upper = ch_cfg['range']
                impedance = ch_cfg.get('impedance', 'high').lower()
                coupling = ch_cfg.get('coupling', 'DC').upper()
            else:
                lower, upper = ch_cfg[0], ch_cfg[1]
                impedance = 'high' if high_impedance else 'low'
                coupling = 'DC'

            # Explicitly enable the channel on screen
            self._write_with_retry(f":CHANnel{channel}:DISPlay ON")

            # Impedance logic for 9000 Series
            if impedance in ('high', '1meg', '1m'):
                self._write_with_retry(f":CHANnel{channel}:IMPedance ONEMeg")
            elif impedance in ('low', '50', '50ohm'):
                self._write_with_retry(f":CHANnel{channel}:IMPedance FIFTy")
            else:
                raise ValueError(f"Invalid impedance for channel {channel}: {impedance!r}")

            if coupling not in ('AC', 'DC'):
                raise ValueError(f"Invalid coupling for channel {channel}: {coupling!r}")
            self._write_with_retry(f":CHANnel{channel}:COUPling {coupling}")

            # Voltage Range/Scale
            v_range = upper - lower
            self._write_with_retry(f":CHANnel{channel}:RANGe {v_range}")
            
            v_offset = (upper + lower) / 2
            self._write_with_retry(f":CHANnel{channel}:OFFSet {v_offset}")

        # Set Waveform Format preferences
        self._write_with_retry(':WAVeform:FORMat WORD')
        self._write_with_retry(':WAVeform:BYTeorder LSBFirst')
        self.clear_error_queue()
        print("scope settings configured")


    def configure_trigger(self, trigger_channel, trigger_level, trigger_slope="+"):
        """
        Function to configure the trigger settings of the oscilloscope.
        """
        self._write_with_retry(":TRIGger:SWEep NORMal")
        self._write_with_retry(":TRIGger:MODE EDGE")
        self._write_with_retry(f":TRIGger:EDGE:SOURCe CHANnel{trigger_channel}")
        self._write_with_retry(f":TRIGger:LEVel CHANnel{trigger_channel}, {trigger_level}")

        if trigger_slope == "+":
            self._write_with_retry(":TRIGger:EDGE:SLOPE POSitive")
        elif trigger_slope == "-":
            self._write_with_retry(":TRIGger:EDGE:SLOPE NEGative")
        else:
            raise ValueError(f"Invalid value for trigger_slope: {trigger_slope}")

    
    def set_to_digitize(self, channels=[1, 2]):
        """
        Function to set the scope to digitize mode. 
        For Agilent 9000, DIGitize clears memory, starts acquisition, and waits for completion.
        """
        # Construct channel string like "CHANnel1,CHANnel2"
        chan_str = ",".join([f"CHANnel{c}" for c in channels])
        cmd = f":DIGitize {chan_str}" if channels else ":DIGitize"
        # cmd = ":DIGitize"
        
        #print(f"Digitizing channels {channels}...")
        print("Digitizing displayed channels...")
        # Use *OPC? to wait for digitize to finish
        query_result = self._query_with_retry(f"{cmd};*OPC?")
        ok = cast(str, query_result).strip() == '1'
        if ok:
            print("Digitize complete.")
        return ok

    def set_to_stop(self):
        """Stop the scope."""
        self._write_with_retry(':STOP')
        print("Oscilloscope set to stop mode.")
        return True

    def set_to_run(self):
        """Set the scope to free-running (continuous) acquisition mode."""
        self.clear_error_queue()
        self._write_with_retry(':RUN')
        print("Oscilloscope set to run mode.")
        return True

    def reset_scope(self):
        """Reset the oscilloscope."""
        try:
            cast(MessageBasedResource, self.scope).clear()
            #self.scope.clear()
        except Exception:
            pass
        self._write_with_retry('*RST')

    def clear_scope(self):
        """Clear scope display/data."""
        try:
            cast(MessageBasedResource, self.scope).clear()
        except Exception:
            pass
        self.clear_error_queue()
        print("Oscilloscope cleared.")


    def read_slow_return_data(self, channels):   
        """
        Function to read data from multiple channels after acquisition is complete.
        Adapted for Agilent/Keysight 9000 Series.

        The scope must already be stopped with valid data in memory
        (e.g. after :DIGitize or :SINGLE + trigger).

        Returns:
         - DataFrame with time and channel voltage columns, or None on failure.
        """
        collected_data = None
        self.clear_error_queue()
        
        # Waveform transfer setup for 9000 series
        self._write_with_retry(':WAVeform:FORMat WORD')       # 16-bit integers
        self._write_with_retry(':WAVeform:BYTeorder LSBFirst')
        self._write_with_retry(':WAVeform:STReaming OFF')      # Disable streaming for query_binary_values compatibility

        time_vector_created = False
        data_dict = {}

        for channel in channels:
            self._write_with_retry(f':WAVeform:SOURCe CHANnel{channel}')

            print(f"Collecting data from channel {channel}...")
            
            errs = self.clear_error_queue()
            if errs:
                for code, msg in errs:
                    print(f"  Scope error (pre-read): {code}, {msg}")
            
            # Preamble: format, type, points, count, xinc, xorg, xref, yinc, yorg, yref
            preamble = cast(str, self._query_with_retry(':WAVeform:PREamble?'))
            pre = preamble.split(',')
            
            num_points = int(pre[2])
            x_incr = float(pre[4])
            x_orig = float(pre[5])
            y_incr = float(pre[7])
            y_orig = float(pre[8])
            y_ref = float(pre[9])

            print(f"  Preamble: {num_points} points, x_incr={x_incr:.2e}, y_incr={y_incr:.2e}")

            if num_points == 0:
                errs = self.clear_error_queue()
                for code, msg in errs:
                    print(f"  Scope error: {code}, {msg}")
                raise ValueError(f"Preamble reports 0 points for channel {channel}. "
                                 "Check that acquisition completed and channel is enabled.")

            # Binary read — WORD format on 9000 series is signed 16-bit ('h')
            raw_data = None
            for attempt in range(DEFAULT_WRITE_QUERY_RETRIES):
                try:
                    raw_data = cast(MessageBasedResource, self.scope).query_binary_values(
                        ':WAVeform:DATA?', datatype='h', container=np.array, #type: ignore
                        is_big_endian=False, chunk_size=1024 * 1024
                    )
                    break
                except Exception as e:
                    self._log.warning("WAVEFORM:DATA? attempt %d failed: %s", attempt + 1, e)
                    errs = self.clear_error_queue()
                    for code, msg in errs:
                        self._log.warning("  Scope error: %d, %s", code, msg)
                    if attempt == DEFAULT_WRITE_QUERY_RETRIES - 1:
                        raise
                    time.sleep(RETRY_DELAY_SEC)

            if raw_data is None or len(raw_data) == 0:
                errs = self.clear_error_queue()
                for code, msg in errs:
                    print(f"  Scope error (post-read): {code}, {msg}")
                raise ValueError(f"No data collected from channel {channel}. "
                                 f"Expected {num_points} points.")

            print(f"  Received {len(raw_data)} samples")

            # Convert to voltage
            raw_data = cast(np.ndarray, raw_data)
            y_data = (raw_data - y_ref) * y_incr + y_orig
            data_dict[f'Channel {channel} Voltage (V)'] = y_data

            # Create time vector once (from first channel)
            if not time_vector_created:
                time_data = x_orig + x_incr * np.arange(len(y_data))
                data_dict['Time (s)'] = time_data
                time_vector_created = True

        # Construct DataFrame with Time first
        if data_dict:
            cols = ['Time (s)'] + [k for k in data_dict.keys() if k != 'Time (s)']
            collected_data = pd.DataFrame({k: data_dict[k] for k in cols})


        return collected_data
        

    def read_slow_return_data_avgd(self, channels, averages=16):
        """
        Configures the scope for hardware averaging, digitizes, and returns
        the averaged waveforms.

        Sequence:
            1. Set acquire mode to AVERage with requested count
            2. :DIGitize — clears old data, arms, waits for all averages, stops
            3. Read waveform data (already averaged in hardware)

        Note: :DIGitize internally runs the full acquire cycle (arm → trigger ×N → stop),
        so there is no need to call :RUN beforehand.

        Inputs:
            - channels (list of int): Channels to acquire.
            - averages (int): Number of averages to compute.

        Returns:
            - DataFrame with Time and Voltage columns.
        """
        print(f"Starting averaged acquisition ({averages} averages)...")
        self.clear_error_queue()

        # display channels must be on for DIGitize to acquire them, so ensure they're enabled
        for ch in channels:
            self._write_with_retry(f":CHANnel{ch}:DISPlay ON")

        # 1. Configure averaging
        self._write_with_retry(":ACQuire:AVERage ON")
        self._write_with_retry(f":ACQuire:AVERage:COUNt {averages}")

        # 2. Digitize — handles arm/trigger/stop internally
        #    This blocks until all 'averages' triggers have been collected.
        success = self.set_to_digitize(channels)
        if not success:
            errs = self.clear_error_queue()
            for code, msg in errs:
                print(f"  Scope error: {code}, {msg}")
            raise RuntimeError("Digitize command failed during averaged acquisition.")

        # 3. Read the (hardware-averaged) waveform
        return self.read_slow_return_data(channels)


    def acquire_slow_save_data(self, channels, window=00):   
        """
        Wrapper to acquire and save data.
        """
        collected_data = self.read_slow_return_data(channels)
        if collected_data is None:
            raise RuntimeError("read_slow_return_data returned None")
        channels_str = "_".join(map(str, channels))
        filename = self.save_data(collected_data, f"channels_{channels_str}_data", window)
        return filename
    

    def arm_scope(self, max_acq_wait_sec=10, poll_interval_sec=0.1):
        """
        Arms the scope (Single Trigger) and waits for it to be armed.
        """
        self.clear_error_queue()
        self._write_with_retry(':SINGLE')

        # Poll :AER? (Arm Event Register) [cite: 1563]
        print("Waiting for oscilloscope to arm...")
        start_time = time.perf_counter()
        
        while (time.perf_counter() - start_time) <= max_acq_wait_sec:
            time.sleep(poll_interval_sec)
            try:
                # AER? reads and clears the register. Returns 1 if armed.
                aer = self._query_with_retry(":AER?")
                aer = cast(str, aer)
                if aer.strip() == "1":
                    print("Oscilloscope is armed and ready for trigger!")
                    return True
            except Exception as e:
                print(f"Error checking arm status: {e}")

        print("Oscilloscope did not arm within timeout.")
        return False
    

    def wait_for_acquisition(self, max_acq_wait_sec=10, poll_interval_sec=0.1):
        """
        Waits for acquisition to complete by polling status registers.
        
        For Keysight 9000 series:
        - :PDER? returns 1 when processing is done (clears on read).
        - :ADER? returns 1 when the acquisition is done (clears on read).
        
        We check both: PDER=1 OR ADER=1, since after a :SINGLE the scope
        transitions to stopped once the trigger is received and acquisition completes.
        """
        print("Waiting for acquisition to complete...")
        start_time = time.perf_counter()
        success = False

        while not success and (time.perf_counter() - start_time) <= max_acq_wait_sec:
            time.sleep(poll_interval_sec)
            try:
                # PDER? (Process Done Event Register) returns 1 when done
                try:
                    pder = cast(str, self._query_with_retry(":PDER?", retries=2)).strip()
                    print(f"Polled :PDER? = {pder}")
                    if pder == "1":
                        success = True
                        break
                except Exception:
                    pass

                # Fallback: check Acquisition Done Event Register
                ader = cast(str, self._query_with_retry(":ADER?", retries=2)).strip()
                print(f"Polled :ADER? = {ader}")
                if ader == "1":
                    success = True
                    break

            except Exception as e:
                print(f"Error during completion poll: {e}")
                break

        if success:
            print("Acquisition complete.")
        else:
            print(f"Warning: Acquisition did not complete within {max_acq_wait_sec}s timeout.")
        return success