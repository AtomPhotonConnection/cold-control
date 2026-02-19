"""
AWGManager — PyVISA-based controller for the Tabor WX218x / WX2184C AWG.

Replaces the old DLL-based WX218x_awg wrapper with direct SCPI commands
sent over PyVISA (USB/LAN/GPIB). The SCPI command set is documented in
the WX2184C Programming Reference (Chapter 4).

Typical usage::

    from instruments.WX218x.awg_manager import AWGManager

    awg = AWGManager()  # auto-detects by manufacturer ID
    awg.abort()
    awg.disable_all_channels()
    awg.configure_sample_rate(1e9)
    awg.set_output_mode("USER")  # arbitrary waveform mode
    awg.enable_coupling()

    awg.select_channel(1)
    awg.define_segment(1, len(data))
    awg.upload_waveform(data)  # numpy int16 array, 0–16383

    awg.configure_trigger(channel=1, mode="EXT", level=1.6, slope="POS")
    awg.set_burst_count(1, count=1)
    awg.set_trace_mode("SING")

    awg.configure_marker(marker=1, position=100, width=64, high_level=1.2, low_level=0.0)

    awg.enable_channel(1)
    awg.initiate()
    # ... triggered output happens here ...
    awg.close()

Created: 2026-02-11
Authors: Marina Llanero Pinero, Matt King (refactored from DLL-based driver)
"""

from __future__ import annotations

import logging
import time
from typing import Optional, cast

import numpy as np
import pyvisa as visa
from pyvisa.resources import MessageBasedResource

from classes.ExperimentalConfigs import AwgConfiguration

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MANUFACTURER_ID = "0x168C"

DEFAULT_TIMEOUT_MS = 30_000  # 30 s — generous for large uploads
DEFAULT_WRITE_QUERY_RETRIES = 3
RETRY_DELAY_SEC = 0.15
COMMAND_DELAY_SEC = 0.02  # small gap between commands

# WX2184C waveform data is 14-bit: values 0 … 16 383.
# 0 → −full-scale, 8192 → 0 V, 16383 → +full-scale.
DAC_BITS = 14
DAC_MAX = (1 << DAC_BITS) - 1  # 16 383
DAC_MID = 1 << (DAC_BITS - 1)  # 8 192

logger = logging.getLogger(__name__)


# ========================================================================
# MARK:Helper functions
# ========================================================================
def process_waveforms(
    _outp_channels, _channel_lags, _waveform_sequence, _waveforms_list, _sample_rate
) -> dict[int, np.ndarray]:
    """
    Helper function to process waveforms from the AwgConfiguration object and prepare them for upload.
    """

    print("Processing waveforms...")
    all_ch_data = {}

    for i, ch in enumerate(_outp_channels):
        # calculate timing offset
        lag_us = _channel_lags[i]
        lag_samples = int(round(lag_us * _sample_rate * 1e-6))
        print(f"Channel {ch}: lag {lag_us} us → {lag_samples} samples")

        # build full waveform from sequence
        ch_wf_ids = _waveform_sequence[i]
        ch_waveforms = [_waveforms_list[wf_id] for wf_id in ch_wf_ids]
        raw_chunks = [np.array(w.get(sample_rate=_sample_rate)) for w in ch_waveforms]
        full_wf = np.concatenate(raw_chunks)

        # apply lag by padding with zeros at the start
        if lag_samples > 0:
            full_wf = np.pad(full_wf, (lag_samples, 0), mode="constant", constant_values=0)
            print(f"Channel {ch}: applied lag by padding with {lag_samples} zeros")

        all_ch_data[ch] = full_wf

    # Align channels to the same length and to a multiple of 16 samples
    max_len = max(len(d) for d in all_ch_data.values())
    if max_len % 16 != 0:
        max_len += 16 - (max_len % 16)
    aligned: dict[int, np.ndarray] = {
        ch: np.pad(d, (0, max_len - len(d)), "constant") for ch, d in all_ch_data.items()
    }
    print(f"Aligned all channels to {max_len} samples (multiple of 16)")

    return aligned


def validate_waveform_size(num_points):
    """
    Validate that waveform size meets requirements

    Requirements from manual:
    - Minimum: 192 points
    - Must be multiple of 16 points

    Args:
        num_points: Number of waveform points

    Returns:
        Validated number of points
    """
    if num_points < 192:
        raise ValueError(f"Waveform must be at least 192 points (got {num_points})")

    if num_points % 16 != 0:
        # Round up to nearest multiple of 16
        adjusted = ((num_points + 15) // 16) * 16
        print(
            f"Warning: Waveform size adjusted from {num_points} to {adjusted} (must be multiple of 16)"
        )
        return adjusted

    return num_points


def normalize_waveform(waveform_data):
    """
    Normalize waveform data to 14-bit DAC values (0-16383)

    The WX2184C uses 14-bit DAC values:
    - 0x0000 (0) corresponds to -2V
    - 0x2000 (8192) corresponds to 0V
    - 0x3FFF (16383) corresponds to +2V

    Args:
        waveform_data: NumPy array of float values (typically -1.0 to +1.0)

    Returns:
        NumPy array of uint16 values (0-16383)
    """
    # Normalize to -1.0 to +1.0 range
    waveform_normalized = np.clip(waveform_data, -1.0, 1.0)

    # Scale to 0-16383 (14-bit range)
    # -1.0 -> 0, 0.0 -> 8192, +1.0 -> 16383
    dac_values = ((waveform_normalized + 1.0) * 8191.5).astype(np.uint16)

    # Ensure we don't exceed 14-bit range
    dac_values = np.clip(dac_values, 0, 16383)

    return dac_values


def create_binary_block_header(num_bytes):
    """
    Create IEEE 488.2 binary block header

    Format: #<num_digits><byte_count><data>
    Example: #42048 means 4 digits follow, then 2048 bytes of data

    Args:
        num_bytes: Number of bytes in the data block

    Returns:
        Header string (e.g., '#42048')
    """
    byte_count_str = str(num_bytes)
    num_digits = len(byte_count_str)
    header = f"#{num_digits}{byte_count_str}"
    return header


# =========================================================================
# MARK:AWGManager
# =========================================================================


class AWGManager:
    """
    Manages a VISA connection to a Tabor WX218x / WX2184C AWG and exposes
    every operation needed by cold-control experiments via SCPI.

    Parameters
    ----------
    resource_id : str or None
        Full VISA resource string, e.g.
        ``"USB0::0x168C::0x1284::0000215582::0::INSTR"``.
        If *None*, the first resource whose address contains
        :data:`MANUFACTURER_ID` is used.
    timeout_ms : int
        VISA I/O timeout in milliseconds.
    """

    # ----- construction / connection ----------------------------------------

    def __init__(
        self,
        resource_id: str = "USB0::0x168C::0x1284::0000215582::0::INSTR",
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self._log = logging.getLogger(__name__)
        self.rm = visa.ResourceManager()

        self.resource_id = resource_id
        self._log.info("Opening AWG: %s", resource_id)
        instrument = self.rm.open_resource(resource_id)
        self.inst = cast(MessageBasedResource, instrument)

        self.inst.timeout = timeout_ms
        self.inst.read_termination = "\n"
        self.inst.write_termination = "\n"
        self.inst.clear()

        idn = self._query("*IDN?")
        print(f"Connected to AWG: {idn}")

    # ----- low-level I/O (with retries, mirroring OscilloscopeManager) ------

    def _delay(self) -> None:
        time.sleep(COMMAND_DELAY_SEC)

    def _write(self, cmd: str, retries: int = DEFAULT_WRITE_QUERY_RETRIES) -> None:
        """Send a SCPI command with retries."""
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                self.inst.write(cmd)
                self._delay()
                return
            except Exception as exc:
                last_exc = exc
                self._log.warning("AWG write attempt %d failed: %s", attempt + 1, exc)
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY_SEC)
        raise last_exc  # type: ignore[misc]

    def _query(self, cmd: str, retries: int = DEFAULT_WRITE_QUERY_RETRIES) -> str:
        """Send a SCPI query with retries and return the response string."""
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                resp = self.inst.query(cmd)
                self._delay()
                return resp.strip()
            except Exception as exc:
                last_exc = exc
                self._log.warning("AWG query attempt %d failed: %s", attempt + 1, exc)
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY_SEC)
        raise last_exc  # type: ignore[misc]

    # ----- error helpers ----------------------------------------------------

    def clear_error_queue(self) -> list:
        """Read and clear the AWG error queue. Returns list of (code, msg)."""
        errors: list = []
        try:
            while True:
                s = self._query("SYST:ERR?")
                if s.startswith("0,") or "No error" in s:
                    break
                parts = s.split(",", 1)
                code = int(parts[0]) if parts else 0
                msg = parts[1].strip(' "') if len(parts) > 1 else s
                errors.append((code, msg))
                if code == 0:
                    break
        except Exception as exc:
            self._log.debug("Could not clear AWG error queue: %s", exc)
        if errors:
            self._log.warning("AWG errors: %s", errors)
        return errors

    def is_connected(self) -> bool:
        """Return True if the AWG responds to ``*IDN?``."""
        try:
            self._query("*IDN?")
            return True
        except Exception:
            return False

    def check_errors(self):
        """Check for instrument errors"""
        try:
            error = self.inst.query(":SYST:ERR?")
            if not error.startswith("0,"):
                print(f"Instrument error: {error.strip()}")
                return False
            return True
        except Exception as e:
            print(f"Error checking instrument status: {e}")
            return False

    # =====================================================================
    # High-level instrument commands
    # =====================================================================

    # ----- lifecycle --------------------------------------------------------

    def reset(self) -> None:
        """``*RST`` — place instrument in known state."""
        self._write("*RST")
        self.inst.write("*CLS")  # clear status registers and error queue
        self.inst.write(":TRAC:DEL:ALL")  # clear waveform memory
        self.inst.query("*OPC?")  # wait for reset to complete
        time.sleep(1)  # allow reset to settle

    def reboot(self) -> None:
        """``SYST:REB`` — reboot the AWG firmware."""
        self._write(":SYSTem:REBoot")

    def close(self) -> None:
        """Close the VISA session."""
        try:
            self.inst.close()
        except Exception as exc:
            self._log.warning("Error closing AWG VISA session: %s", exc)
        try:
            self.rm.close()
        except Exception as exc:
            self._log.warning("Error closing resource manager: %s", exc)

    # ----- run control (abort / initiate / enable) --------------------------

    def abort(self) -> None:
        """Unconditional stop of output waveform generation."""
        self._write(":ABORt")

    def initiate(self) -> None:
        """
        Enable output generation and arm for trigger.

        In triggered mode (``INIT:CONT OFF``) the AWG waits for a trigger
        event after this command.
        """
        self._write(":ENABle")

    def wait_opc(self, timeout_s: float = 10.0) -> bool:
        """Block until ``*OPC?`` returns ``1`` or timeout."""
        old_timeout = self.inst.timeout
        self.inst.timeout = int(timeout_s * 1000)
        try:
            resp = self._query("*OPC?")
            return resp.strip() == "1"
        finally:
            self.inst.timeout = old_timeout

    def trigger(self) -> None:
        """Send a software trigger (``*TRG``). Only relevant in triggered mode."""
        self._write(":TRIGger")

    # ----- channel selection & output state ----------------------------------

    def select_channel(self, channel: int) -> None:
        """
        Select the active channel for subsequent programming.

        Parameters
        ----------
        channel : int
            1, 2, 3 or 4.
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError(f"Invalid channel {channel}. Must be 1–4.")
        self._write(f":INST:SEL {channel}")

    def enable_channel(self, channel: int) -> None:
        """Turn on the output of *channel*."""
        self.select_channel(channel)
        self._write(":OUTP ON")

    def disable_channel(self, channel: int) -> None:
        """Turn off the output of *channel*."""
        self.select_channel(channel)
        self._write(":OUTP OFF")

    # ----- coupling ----------------------------------------------------------

    def enable_coupling(self) -> None:
        """Couple channels 1&2 with 3&4 so they share a sample clock."""
        # Instrument:Couple:State ON|OFF
        self._write(":INST:COUP:STAT ON")

    def disable_coupling(self) -> None:
        self._write(":INST:COUP:STAT OFF")

    # ----- clock / sample rate -----------------------------------------------

    def configure_sample_rate(self, sample_rate: float) -> None:
        """
        Set the sample clock frequency in Sa/s.

        Valid range: 10 MSa/s … 2.3 GSa/s.
        """
        self._write(f":FREQ:RAST {sample_rate:.10g}")

    def get_sample_rate(self) -> float:
        return float(self._query(":FREQ:RAST?"))

    # ----- output mode -------------------------------------------------------

    def set_output_mode(self, mode: str = "USER") -> None:
        """
        Select the function mode for all channels.

        Parameters
        ----------
        mode : str
            One of ``"FIX"`` (standard), ``"USER"`` (arbitrary), ``"SEQ"``
            (sequenced), ``"ASEQ"`` (advanced seq), ``"MOD"``, ``"PULS"``,
            ``"PATT"``.
        """
        if mode not in ("FIX", "USER", "SEQ", "ASEQ", "MOD", "PULS", "PATT"):
            raise ValueError(f"Invalid output mode {mode}.")
        self._write(f":FUNC:MODE {mode}")

    # ----- run mode (continuous / triggered) ----------------------------------

    def set_continuous(self, on: bool = True) -> None:
        """
        ``INIT:CONT ON`` → continuous;  ``INIT:CONT OFF`` → triggered.
        """
        # Full command is  :INITiate:CONTinuous ON|OFF
        self._write(f":INIT:CONT {'ON' if on else 'OFF'}")

    def set_trigger_source(self, source: str = "EXT") -> None:
        """
        Set trigger source advance.

        Parameters
        ----------
        source : str
            ``"EXT"`` (external TRIG IN), ``"BUS"`` (software), ``"TIM"``
            (internal timer), ``"EVEN"`` (Event IN).
        """
        if source not in ("EXT", "BUS", "TIM", "EVEN"):
            raise ValueError(f"Invalid trigger source {source}.")
        self._write(f":TRIG:SOUR:ADV {source}")

    def set_trigger_level(self, level: float = 1.6) -> None:
        """Set trigger threshold in volts (−5 V to +5 V)."""
        # :TRIGger:LEVel <level>
        self._write(f":TRIG:LEV {level}")

    def set_trigger_slope(self, slope: str = "POS") -> None:
        """Set trigger edge: ``"POS"``, ``"NEG"`` or ``"EITH"``."""
        if slope not in ("POS", "NEG", "EITH"):
            raise ValueError(f"Invalid slope {slope}. Must be 'POS', 'NEG' or 'EITH'.")
        else:
            self._write(f":TRIG:SLOP {slope}")

    def set_burst_count(self, count: int = 1) -> None:
        """
        Set the burst (trigger count) for *channel*.

        Range: 1 … 16 777 216.
        """
        self._write(f":TRIG:COUN {count}")

    # ----- amplitude / gain / offset -----------------------------------------

    def set_amplitude(self, channel: int, amplitude: float) -> None:
        """
        Set peak-to-peak amplitude for *channel* in volts.

        DC path: 50 mV … 2 V.  HV path: 50 mV … 4 V.
        """
        self.select_channel(channel)
        self._write(f":VOLT {amplitude}")

    def set_amplitude_all(self, amplitude: float) -> None:
        """Set amplitude for ALL channels."""
        self._write(f":VOLT:ALL {amplitude}")

    def set_offset(self, channel: int, offset: float) -> None:
        """Set DC offset for *channel* (−1 V … +1 V)."""
        self.select_channel(channel)
        self._write(f":VOLT:OFFS {offset}")

    def set_output_coupling(self, mode: str = "DC") -> None:
        """Select output amplifier path for all channels: ``"DC"`` or ``"HV"``."""
        self._write(f":OUTP:COUP:ALL {mode}")

    # play a standard sine wave on a particular channel at a particular frequency
    def play_sine_wave(self, channel: int, frequency: float, amplitude: float = 1.0) -> None:
        """Configure a standard sine wave on *channel* with given frequency and amplitude."""
        self.select_channel(channel)
        self.set_output_mode("FIX")
        self._write(":FUNC:SHAP SIN")
        self._write(f":FREQ {frequency}")
        self._write(f":VOLT {amplitude}")

    # ----- trace / waveform memory -------------------------------------------

    def set_trace_mode(self, mode: str = "SING") -> None:
        """
        Set waveform download mode.

        Parameters
        ----------
        mode : str
            ``"SING"`` — download to selected channel only.
            ``"DUPL"`` — duplicate to paired channel.
            ``"ZER"``  — zero paired channel.
            ``"COMB"`` — combined (interleaved) for both channels of a pair.
        """
        self._write(f":TRAC:MODE {mode}")

    def define_segment(self, segment: int, length: int) -> None:
        """
        Pre-define a memory segment.

        Parameters
        ----------
        segment : int
            Segment number (1 … 32 000).
        length : int
            Number of samples. **Must** be a multiple of 16.
        """
        if length % 16 != 0:
            raise ValueError(f"Segment length {length} is not a multiple of 16 (AWG requirement).")
        self._write(f":TRAC:DEF {segment},{length}")

    def select_segment(self, segment: int) -> None:
        """Select the active waveform segment."""
        self._write(f":TRAC:SEL {segment}")

    def delete_all_segments(self) -> None:
        """Delete all waveform segments from memory."""
        self._write(":TRAC:DEL:ALL")

    def delete_segment(self, segment: int) -> None:
        self._write(f":TRAC:DEL {segment}")

    def clear_all(self) -> None:
        """Delete all segments and all sequences."""
        self.delete_all_segments()
        self.delete_all_sequences()

    # ----- waveform upload ---------------------------------------------------
    def upload_waveform(
        self,
        waveform_data: np.ndarray,
        segment: int = 1,
        channel: Optional[int] = None,
    ) -> bool:
        """
        Upload waveform data to the AWG.

        Parameters
        ----------
        data : np.ndarray
            Waveform as **float (−1 … +1)** or **uint16 DAC codes (0 … 16 383)**.
            If float, it is converted automatically via :meth:`float_to_dac`.
            Length must be a multiple of 16.
        segment : int
            Target segment number (default 1).
        channel : int or None
            If given, ``select_channel`` is called first.


        Upload arbitrary waveform to AWG memory

        This is the critical function that must be done correctly to avoid
        freezing the AWG. Follows the proper sequence from the manual.

        Args:
            waveform_data: NumPy array of float values (-1.0 to +1.0)
            segment: Segment number (1-32000)

        Returns:
            True if successful, False otherwise
        """
        if channel is not None:
            self.select_channel(channel)
        else:
            raise ValueError("Channel must be specified for waveform upload.")

        self.set_trace_mode("SING")  # ensure single-channel upload mode

        try:
            # Step 1: Validate and adjust waveform size
            num_points = len(waveform_data)
            validated_points = validate_waveform_size(num_points)

            # Pad with zeros if size was adjusted
            if validated_points > num_points:
                waveform_data = np.pad(
                    waveform_data, (0, validated_points - num_points), mode="constant"
                )

            # Step 2: Convert to 14-bit DAC values
            dac_values = normalize_waveform(waveform_data)

            # Step 3: Define segment in memory
            # CRITICAL: Must define segment BEFORE uploading data
            print(f"Defining segment {segment} with {validated_points} points...")
            self.inst.write(f":TRAC:DEF {segment},{validated_points}")
            time.sleep(0.05)  # Small delay after defining

            if not self.check_errors():
                print("Error defining segment!")
                return False

            # Step 4: Select the segment
            print(f"Selecting segment {segment}...")
            self.inst.write(f":TRAC:SEL {segment}")
            time.sleep(0.05)

            if not self.check_errors():
                print("Error selecting segment!")
                return False

            # Step 5: Prepare binary data
            # Each point is 2 bytes (16-bit word, but only 14 bits used)
            binary_data = dac_values.astype("<u2").tobytes()  # Little-endian uint16
            num_bytes = len(binary_data)

            # Step 6: Create IEEE 488.2 binary block header
            header = create_binary_block_header(num_bytes)
            command = f":TRAC:DATA {header}"

            # Step 7: Upload data using binary write
            print(f"Uploading {validated_points} points ({num_bytes} bytes)...")

            # Write command header
            self.inst.write_raw(command.encode("ascii"))

            # Write binary data
            self.inst.write_raw(binary_data)

            # Write termination
            self.inst.write_raw(b"\n")

            # Wait for operation to complete
            self.inst.query("*OPC?")
            time.sleep(0.1)

            # Step 8: Verify no errors occurred
            if not self.check_errors():
                print("Error during waveform upload!")
                return False

            print(f"Successfully uploaded waveform to segment {segment}")
            return True

        except Exception as e:
            print(f"Error uploading waveform: {e}")
            return False

    # ----- marker output commands --------------------------------------------

    def configure_marker(
        self,
        marker: int = 2,
        position: int = 0,
        width: int = 4,
        delay: float = 0.0,
        channel: Optional[int] = None,
    ) -> None:
        """
        Configure a marker output on the currently selected (or specified)
        channel.

        Parameters
        ----------
        marker : int
            Marker index (1 or 2).
        position : int
            Start position in waveform points from segment start.
        width : int
            Marker pulse width in waveform points (must be ≥ 2, even).
        high_level : float
            Marker high voltage (0.5 … 1.2 V).
        delay : float
            Delay from SYNC in seconds (0 … 3 ns).
        channel : int or None
            If given, ``select_channel`` is called first.
        """
        if channel is not None:
            self.select_channel(channel)

        if marker not in (1, 2):
            raise ValueError(f"Marker must be 1 or 2, got {marker}.")
        if position < 0:
            self._log.warning("Marker position clamped from %d to 0.", position)
            position = 0
        if width < 0:
            width = 0

        high_level = 1.2
        mark_source = "WAVE"

        self._write(f":MARK:SEL {marker}")
        self._write(f":MARK:SOUR {mark_source}")
        self._write(f":MARK:POS {position}")
        self._write(f":MARK:WIDT {width}")
        # self._write(f":MARKer:VOLT:HIGH {high_level}")

        self._write(f":MARK:DEL {delay}")
        self._write(":MARK:STAT ON")
        self._log.info(
            "Marker %d configured: pos=%d, width=%d",
            marker,
            position,
            width,
        )

    def disable_marker(self, marker: int = 1, channel: Optional[int] = None) -> None:
        """Turn off a marker."""
        if channel is not None:
            self.select_channel(channel)
        self._write(f":MARK:SEL {marker}")
        self._write(":MARK:STAT OFF")

    # ----- sequence commands -------------------------------------------------

    def define_sequence_step(self, step: int, segment: int, loops: int = 1, jump: int = 0) -> None:
        """
        Define one step of a sequence table.

        Parameters
        ----------
        step : int
            Step number (1-based, ascending, min 3 steps total).
        segment : int
            Segment number to play at this step.
        loops : int
            Number of times to repeat this segment.
        jump : int
            Jump flag (0 = no jump, 1 = wait for event before advancing).
        """
        self._write(f":SEQ:DEF {step},{segment},{loops},{jump}")

    def set_sequence_advance(self, mode: str = "AUTO") -> None:
        """Set sequence advance mode: ``"AUTO"`` | ``"ONCE"`` | ``"STEP"``."""
        self._write(f":SEQ:ADV {mode}")

    def set_sequence_length(self, length: int) -> None:
        self._write(f":SEQ:LENG {length}")

    def select_sequence(self, seq_num: int) -> None:
        self._write(f":SEQ:SEL {seq_num}")

    def delete_all_sequences(self) -> None:
        """Delete all sequences."""
        self._write(":SEQ:DEL:ALL")

    # ----- MARK:compound methods

    def configure_for_triggered_output(
        self,
        _sample_rate: float,
        _channels: list[int],
        _burst_count: int,
        _amplitudes: list[float],
        _offsets: list[float],
    ) -> None:
        """
        One-call setup that mirrors the old ``configure_awg`` workflow:

        1. Abort + disable channels.
        2. Clear memory.
        3. Set sample rate, arbitrary mode, coupling.
        4. Configure trigger on each channel.
        5. (Waveforms must still be uploaded separately.)
        """
        trigger_level = 1.6  # V, typical for external trigger from scope or pulse generator
        trigger_slope = "POS"  # positive edge trigger
        trigger_source = "EXT"  # external trigger input

        self.abort()
        for ch in _channels:
            self.disable_channel(ch)
        self.clear_all()

        self.delete_all_segments()

        self.configure_sample_rate(_sample_rate)
        self.set_output_mode("USER")  # arbitrary
        self.enable_coupling()

        for i, ch in enumerate(_channels):
            self.select_channel(ch)
            self.set_continuous(False)
            self.set_trigger_level(trigger_level)
            self.set_trigger_source(trigger_source)
            self.set_trigger_slope(trigger_slope)

            self.set_burst_count(_burst_count)
            self.set_amplitude(ch, _amplitudes[i])
            self.set_offset(ch, _offsets[i])

    def upload_and_arm(self, awg_cfg: AwgConfiguration) -> None:
        """
        Full configure → upload → arm cycle used by experiment runners.

        Parameters
        ----------
        awg_cfg : AwgConfiguration
            The AWG configuration object containing all necessary settings.
        Returns
        -------
        None
        """
        waveform_sequence = awg_cfg.waveform_sequence
        sample_rate = awg_cfg.sample_rate
        burst_count = awg_cfg.burst_count
        outp_channels = awg_cfg.waveform_output_channels
        channel_lags = awg_cfg.waveform_output_channel_lags
        marker_width_us = awg_cfg.marker_width
        ch_amplitudes = [1.0 for _ in outp_channels]  # TODO: get from config
        ch_offsets = [0.0 for _ in outp_channels]  # TODO: get from config

        waveforms_list = awg_cfg.waveforms  # TODO: make a dict rather than list

        if awg_cfg.waveform_stitch_delays is not None:
            raise DeprecationWarning("Stitch delays are deprecated")
        if awg_cfg.interleave_waveforms is not None:
            raise DeprecationWarning("Interleaving waveforms is deprecated")
        if awg_cfg.marked_channels is not None:
            raise DeprecationWarning("Marked channels are deprecated")

        # --- Process waveforms ---
        all_ch_data = process_waveforms(
            outp_channels, channel_lags, waveform_sequence, waveforms_list, sample_rate
        )

        # --- Configure the scope for triggered output ---
        self.configure_for_triggered_output(
            sample_rate, outp_channels, burst_count, ch_amplitudes, ch_offsets
        )

        self.wait_opc()
        print("AWG configured for triggered output.")

        # --- Upload waveforms for each channel ---
        for ch in outp_channels:
            data = all_ch_data[ch]
            success = self.upload_waveform(data, segment=1, channel=ch)
            if not success:
                raise RuntimeError(f"Failed to upload waveform for channel {ch}")
            print(f"Waveform for channel {ch} uploaded successfully.")

        # --- Configure markers ---
        self.configure_marker(width=marker_width_us * sample_rate * 1e-6)

        # --- Enable outputs and arm ---
        for ch in outp_channels:
            self.enable_channel(ch)

        self.initiate()
        self._log.info("AWG armed and waiting for trigger.")

        print("AWG armed and waiting for trigger.")

    # ----- context manager ---------------------------------------------------

    def __enter__(self) -> AWGManager:
        return self

    def __exit__(self, *exc) -> None:
        try:
            self.abort()
        except Exception:
            pass
        self.close()

    def __repr__(self) -> str:
        return f"AWGManager({self.resource_id!r})"
