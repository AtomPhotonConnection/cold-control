"""
AWGManager — PyVISA-based controller for the Tabor WX218x / WX2184C AWG.

Replaces the old DLL-based WX218x_awg wrapper with direct SCPI commands
sent over PyVISA (USB/LAN/GPIB). The SCPI command set is documented in
the WX2184C Programming Reference (Chapter 4).

Typical usage::

    from instruments.WX218x.awg_manager import AWGManager

    awg = AWGManager()                     # auto-detects by manufacturer ID
    awg.abort()
    awg.disable_all_channels()
    awg.configure_sample_rate(1e9)
    awg.set_output_mode("USER")            # arbitrary waveform mode
    awg.enable_coupling()

    awg.select_channel(1)
    awg.define_segment(1, len(data))
    awg.upload_waveform(data)              # numpy int16 array, 0–16383

    awg.configure_trigger(channel=1, mode="EXT", level=1.6, slope="POS")
    awg.set_burst_count(1, count=1)
    awg.set_trace_mode("SING")

    awg.configure_marker(marker=1, position=100, width=64,
                         high_level=1.2, low_level=0.0)

    awg.enable_channel(1)
    awg.initiate()
    # ... triggered output happens here ...
    awg.close()

Created: 2026-02-11
Authors: Marina Llanero Pinero, Matt King (refactored from DLL-based driver)
"""
from __future__ import annotations

import logging
import struct
import time
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np
import pyvisa as visa

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MANUFACTURER_ID = "0x168C"

DEFAULT_TIMEOUT_MS = 30_000          # 30 s — generous for large uploads
DEFAULT_WRITE_QUERY_RETRIES = 3
RETRY_DELAY_SEC = 0.15
COMMAND_DELAY_SEC = 0.02             # small gap between commands

# WX2184C waveform data is 14-bit: values 0 … 16 383.
# 0 → −full-scale, 8192 → 0 V, 16383 → +full-scale.
DAC_BITS = 14
DAC_MAX = (1 << DAC_BITS) - 1       # 16 383
DAC_MID = 1 << (DAC_BITS - 1)       # 8 192

logger = logging.getLogger(__name__)


# =========================================================================
# AWGManager
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
        resource_id: Optional[str] = None,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self._log = logging.getLogger(__name__)
        self.rm = visa.ResourceManager()

        if resource_id is None:
            resource_id = self._auto_detect()

        self.resource_id = resource_id
        self._log.info("Opening AWG: %s", resource_id)

        self.inst = self.rm.open_resource(resource_id)
        self.inst.timeout = timeout_ms
        # Large chunk size speeds up binary uploads
        self.inst.chunk_size = 4 * 1024 * 1024
        self.inst.read_termination = "\n"
        self.inst.write_termination = "\n"

        idn = self._query("*IDN?")
        print(f"Connected to AWG: {idn}")

    def _auto_detect(self) -> str:
        """Find the first VISA resource whose address contains the manufacturer ID."""
        resources = self.rm.list_resources()
        self._log.debug("VISA resources: %s", resources)
        try:
            return next(r for r in resources if MANUFACTURER_ID in r)
        except StopIteration:
            raise RuntimeError(
                f"No AWG with manufacturer ID {MANUFACTURER_ID} found. "
                f"Connected resources: {resources}"
            )

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

    def _write_binary(self, cmd_prefix: str, data: bytes) -> None:
        """
        Send a SCPI command followed by an IEEE-488.2 definite-length binary
        block (``#<digits><byte_count><data>``).
        """
        n_bytes = len(data)
        count_str = str(n_bytes)
        header = f"#{len(count_str)}{count_str}"
        # Build raw message: command + header + binary payload
        raw = (cmd_prefix + header).encode("ascii") + data
        self.inst.write_raw(raw)
        self._delay()

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

    # =====================================================================
    # High-level instrument commands
    # =====================================================================

    # ----- lifecycle --------------------------------------------------------

    def reset(self) -> None:
        """``*RST`` — place instrument in known state."""
        self._write("*RST")
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

    def enable_all_channels(self, channels: Sequence[int] = (1, 2, 3, 4)) -> None:
        for ch in channels:
            self.enable_channel(ch)

    def disable_all_channels(self, channels: Sequence[int] = (1, 2, 3, 4)) -> None:
        for ch in channels:
            self.disable_channel(ch)

    # ----- coupling ----------------------------------------------------------

    def enable_coupling(self) -> None:
        """Couple channels 1&2 with 3&4 so they share a sample clock."""
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
        self._write(f":FUNC:MODE {mode}")

    # ----- run mode (continuous / triggered) ----------------------------------

    def set_continuous(self, on: bool = True) -> None:
        """
        ``INIT:CONT ON`` → continuous;  ``INIT:CONT OFF`` → triggered.
        """
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
        self._write(f":TRIG:SOUR:ADV {source}")

    def set_trigger_level(self, level: float = 1.6) -> None:
        """Set trigger threshold in volts (−5 V to +5 V)."""
        self._write(f":TRIG:LEV {level}")

    def set_trigger_slope(self, slope: str = "POS") -> None:
        """Set trigger edge: ``"POS"``, ``"NEG"`` or ``"EITH"``."""
        self._write(f":TRIG:SLOP {slope}")

    def configure_trigger(
        self,
        channel: int,
        mode: str = "EXT",
        level: float = 1.6,
        slope: str = "POS",
    ) -> None:
        """
        Convenience: select *channel*, switch to triggered mode, and set
        source / level / slope in one call.
        """
        self.select_channel(channel)
        self.set_continuous(False)              # triggered mode
        self.set_trigger_source(mode)
        self.set_trigger_level(level)
        self.set_trigger_slope(slope)

    def set_burst_count(self, channel: int, count: int = 1) -> None:
        """
        Set the burst (trigger count) for *channel*.

        Range: 1 … 16 777 216.
        """
        self.select_channel(channel)
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
            raise ValueError(
                f"Segment length {length} is not a multiple of 16 (AWG requirement)."
            )
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

    @staticmethod
    def float_to_dac(data: np.ndarray) -> np.ndarray:
        """
        Convert a floating-point waveform (−1 … +1) to 14-bit DAC codes
        (0 … 16 383) stored as ``uint16``.

        This matches the DLL's ``create_arbitrary_waveform_custom`` behaviour::

            DAC = round((1 + sample) * 8191)

        Parameters
        ----------
        data : np.ndarray
            Waveform samples in the range [−1, +1].

        Returns
        -------
        np.ndarray of uint16
        """
        data = np.asarray(data, dtype=np.float64)
        dac = np.clip(np.round((1.0 + data) * (DAC_MAX / 2)), 0, DAC_MAX).astype(np.uint16)
        return dac

    def upload_waveform(
        self,
        data: np.ndarray,
        segment: int = 1,
        channel: Optional[int] = None,
    ) -> None:
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
        """
        if channel is not None:
            self.select_channel(channel)

        data = np.asarray(data)
        if np.issubdtype(data.dtype, np.floating):
            data = self.float_to_dac(data)
        data = data.astype(np.uint16)

        n_samples = len(data)
        if n_samples % 16 != 0:
            # Silently pad to next multiple of 16
            pad = 16 - (n_samples % 16)
            data = np.pad(data, (0, pad), constant_values=DAC_MID)
            n_samples = len(data)
            self._log.info("Padded waveform by %d samples to reach multiple of 16.", pad)

        # Define segment, select it, then upload binary data
        self.define_segment(segment, n_samples)
        self.select_segment(segment)

        # Convert to little-endian bytes (each sample is 2 bytes)
        raw_bytes = data.astype("<u2").tobytes()
        self._write_binary(":TRAC:DATA ", raw_bytes)
        self._log.info("Uploaded %d samples (%d bytes) to segment %d.", n_samples, len(raw_bytes), segment)

    # ----- marker output commands --------------------------------------------

    def configure_marker(
        self,
        marker: int = 1,
        position: int = 0,
        width: int = 4,
        high_level: float = 1.2,
        low_level: float = 0.0,
        delay: float = 0.0,
        source: str = "WAVE",
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
        low_level : float
            Marker low voltage.
        delay : float
            Delay from SYNC in seconds (0 … 3 ns).
        source : str
            ``"WAVE"`` (from waveform memory) or ``"USER"`` (user-defined).
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

        self._write(f":MARK:SEL {marker}")
        self._write(f":MARK:SOUR {source}")
        self._write(f":MARK:POS {position}")
        self._write(f":MARK:WIDT {width}")
        self._write(f":MARK:VOLT:HIGH {high_level}")
        # Low level is not an independent SCPI command in the WX2184C marker
        # subsystem — the low level is implicitly 0 V. But we keep the
        # parameter for API completeness. If the hardware supports it in
        # future firmware, uncomment:
        # self._write(f":MARK:VOLT:LOW {low_level}")
        self._write(f":MARK:DEL {delay}")
        self._write(f":MARK:STAT ON")
        # Refresh marker (similar to the DLL's marker_refresh call)
        self._write(f":MARK:REF ON")
        self._log.info(
            "Marker %d configured: pos=%d, width=%d, high=%.2f V",
            marker, position, width, high_level,
        )

    def disable_marker(self, marker: int = 1, channel: Optional[int] = None) -> None:
        """Turn off a marker."""
        if channel is not None:
            self.select_channel(channel)
        self._write(f":MARK:SEL {marker}")
        self._write(":MARK:STAT OFF")

    # ----- sequence commands -------------------------------------------------

    def define_sequence_step(
        self, step: int, segment: int, loops: int = 1, jump: int = 0
    ) -> None:
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

    # ----- convenience / compound methods ------------------------------------

    def configure_for_triggered_output(
        self,
        sample_rate: float,
        channels: Sequence[int] = (1,),
        trigger_level: float = 1.6,
        trigger_slope: str = "POS",
        burst_count: int = 1,
        amplitude: float = 2.0,
    ) -> None:
        """
        One-call setup that mirrors the old ``configure_awg`` workflow:

        1. Abort + disable channels.
        2. Clear memory.
        3. Set sample rate, arbitrary mode, coupling.
        4. Configure trigger on each channel.
        5. (Waveforms must still be uploaded separately.)
        """
        self.abort()
        self.disable_all_channels(channels)
        self.clear_all()

        self.configure_sample_rate(sample_rate)
        self.set_output_mode("USER")               # arbitrary
        self.enable_coupling()
        self.set_trace_mode("SING")

        for ch in channels:
            self.configure_trigger(
                channel=ch,
                mode="EXT",
                level=trigger_level,
                slope=trigger_slope,
            )
            self.set_burst_count(ch, burst_count)
            self.set_amplitude(ch, amplitude)

    def upload_and_arm(
        self,
        waveforms: dict[int, np.ndarray],
        sample_rate: float,
        burst_count: int = 1,
        trigger_level: float = 1.6,
        amplitude: float = 2.0,
        marker_config: Optional[dict] = None,
    ) -> float:
        """
        Full configure → upload → arm cycle used by experiment runners.

        Parameters
        ----------
        waveforms : dict[int, np.ndarray]
            Mapping of channel number (1–4) → float waveform array (−1 … +1).
        sample_rate : float
            Sample rate in Sa/s.
        burst_count : int
            Number of bursts per trigger.
        trigger_level : float
            Trigger threshold in volts.
        amplitude : float
            Output amplitude in volts (50 mV … 2 V DC path).
        marker_config : dict or None
            If given, keys: ``channel``, ``marker``, ``position``, ``width``,
            ``high_level``.  Forwarded to :meth:`configure_marker`.

        Returns
        -------
        float
            Waveform duration in seconds (length / sample_rate).
        """
        channels = sorted(waveforms.keys())

        # 1. Configure global settings
        self.configure_for_triggered_output(
            sample_rate=sample_rate,
            channels=channels,
            trigger_level=trigger_level,
            burst_count=burst_count,
            amplitude=amplitude,
        )

        # 2. Upload waveforms
        duration_samples = 0
        for ch in channels:
            data = waveforms[ch]
            self.upload_waveform(data, segment=1, channel=ch)
            duration_samples = max(duration_samples, len(data))

        # 3. Marker
        if marker_config is not None:
            self.configure_marker(**marker_config)

        # 4. Enable outputs and arm
        for ch in channels:
            self.enable_channel(ch)

        self.initiate()
        self._log.info("AWG armed and waiting for trigger.")

        return duration_samples / sample_rate

    # ----- context manager ---------------------------------------------------

    def __enter__(self) -> "AWGManager":
        return self

    def __exit__(self, *exc) -> None:
        try:
            self.abort()
        except Exception:
            pass
        self.close()

    def __repr__(self) -> str:
        return f"AWGManager({self.resource_id!r})"
