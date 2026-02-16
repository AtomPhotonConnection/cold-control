"""
Pulse Shape Experiment Classes

Self-contained module with three classes for running pulse-shape calibration
experiments on the AWG + oscilloscope setup:

    PulseShapeConfig           – parses a .ini file into typed attributes
    PulseShapeExperimentResult – holds all data/metrics from a single run
    PulseShapeExperimentRunner – programs AWG, reads scope, returns a Result

These classes deliberately contain *no* optimisation logic.  The optimisation
loop (NLMS, Wiener, gradient descent, etc.) lives in the calling script, which
can call runner.run() repeatedly with different waveforms.

Usage example::

    from pulse_experiment import (
        PulseShapeConfig,
        PulseShapeExperimentRunner,
        load_signal_from_path,
    )

    cfg    = PulseShapeConfig("config_pulse_experiment.ini")
    wave   = load_signal_from_path(cfg.get_theoretical_signal_path(), cfg.amplitude)
    runner = PulseShapeExperimentRunner(cfg, wave)
    result = runner.run()
    result.plot()
    runner.close()
"""

import csv
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyvisa as visa
from configobj import ConfigObj

from instruments.Oscilloscopes.agilent_mso9254A import OscilloscopeManager
from instruments.WX218x.awg_manager import AWGManager
from classes.ExperimentalConfigs import AwgConfiguration, Waveform

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# =========================================================================
# Standalone helpers (previously in pulse_optimizer_core.py)
# =========================================================================

def load_signal_from_path(csv_path: str, amplitude: float) -> np.ndarray:
    """
    Load a waveform from CSV and normalise to *amplitude*.

    Args:
        csv_path:  Path to a headerless CSV (values in first row/column).
        amplitude: Peak amplitude for the returned signal.

    Returns:
        Normalised signal as a 1-D numpy array.
    """
    data = pd.read_csv(csv_path, header=None)
    signal = data.T.to_numpy().flatten()
    signal = (signal / signal.max()) * amplitude
    return signal





def compute_error_metrics(
    measured: np.ndarray,
    theoretical: np.ndarray,
    time_array: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """
    Compute error metrics between *measured* and *theoretical* signals.

    Returns:
        Dict with ``'mse'``, ``'rmse'``, ``'mae'``, and optionally
        ``'trapz_error'``.
    """
    measured = np.asarray(measured)
    theoretical = np.asarray(theoretical)

    min_len = min(len(measured), len(theoretical))
    measured = measured[:min_len]
    theoretical = theoretical[:min_len]

    mse = float(np.mean((measured - theoretical) ** 2) / np.mean(theoretical ** 2))
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(measured - theoretical)))

    metrics: Dict[str, float] = {"mse": mse, "rmse": rmse, "mae": mae}

    if time_array is not None and len(time_array) == len(theoretical):
        trapz_error = float(
            np.trapz(np.abs(measured - theoretical), time_array)
            / np.trapz(np.abs(theoretical), time_array)
        )
        metrics["trapz_error"] = trapz_error

    return metrics


def normalize_signals_to_max(
    measured: np.ndarray, theoretical: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Normalise both signals so their peaks equal the *smaller* of the two maxima."""
    min_max = min(measured.max(), theoretical.max())
    return (
        measured / measured.max() * min_max,
        theoretical / theoretical.max() * min_max,
    )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _cfg_section(cfg: ConfigObj, key: str) -> Dict[str, str]:
    """Extract a config section with a runtime guard."""
    section = cfg[key]
    if not isinstance(section, dict):
        raise TypeError(f"Config key '{key}' must be a section, got scalar: {section!r}")
    return section


# =========================================================================
# PulseShapeConfig
# =========================================================================

class PulseShapeConfig:
    """
    Typed representation of a pulse-shape experiment configuration file.

    Parses a ``.ini`` file (same layout as ``config_inverted.ini``) and exposes
    every parameter as a Python attribute with the correct type.

    Example::

        cfg = PulseShapeConfig("config_pulse_experiment.ini")
        print(cfg.channel, cfg.pulse_type, cfg.amplitude)
    """

    def __init__(self, config_path: str) -> None:
        self._raw = ConfigObj(config_path)

        # --- Hardware --------------------------------------------------------
        hw = _cfg_section(self._raw, "Hardware")
        self.scope_id: str = str(hw["scope_id"])
        self.awg_id: str = str(hw["awg_id"])

        # --- Channel ---------------------------------------------------------
        ch = _cfg_section(self._raw, "Channel")
        self.channel: int = int(ch["channel"])
        self.pulse_type: str = str(ch["pulse_type"])

        # --- Pulse paths -----------------------------------------------------
        self.pulse_paths: Dict[str, str] = cast(
            Dict[str, str], self._raw.get("Pulse_paths", {})
        )

        # --- Optimisation parameters -----------------------------------------
        opt = _cfg_section(self._raw, "Optimization")
        self.amplitude: float = float(opt["amplitude"])

        # Iterative feedback
        self.max_iterations: int = int(opt.get("max_iterations", "10"))
        self.error_threshold: float = float(opt.get("error_threshold", "1e-4"))
        self.gain: float = float(opt.get("gain", "0.5"))

        # M-LOOP
        self.max_num_runs: int = int(opt.get("max_num_runs", "100"))
        self.num_fourier_coeffs: int = int(opt.get("num_fourier_coeffs", "15"))

        # Memory polynomial
        self.poly_degree: int = int(opt.get("poly_degree", "5"))
        self.mem_depth: int = int(opt.get("mem_depth", "3"))

        # --- Oscilloscope ----------------------------------------------------
        osc = _cfg_section(self._raw, "Oscilloscope")
        self.trigger_channel: int = int(osc["trigger_channel"])
        self.trigger_level: float = float(osc["trigger_level"])
        self.samp_rate: float = float(osc["samp_rate"])
        self.timebase_start: float = float(osc["timebase_start"])
        self.timebase_stop: float = float(osc["timebase_stop"])
        self.data_channel: int = int(osc["data_channel"])

        # Build channel_map from channel_N_lower / channel_N_upper keys
        self.channel_map: Dict[int, Tuple[float, float]] = {}
        for key in self._raw["Oscilloscope"]:
            if key.startswith("channel_") and key.endswith("_lower"):
                ch_num = int(key.split("_")[1])
                lower = float(osc[f"channel_{ch_num}_lower"])
                upper = float(osc[f"channel_{ch_num}_upper"])
                self.channel_map[ch_num] = (lower, upper)
        if not self.channel_map:
            self.channel_map = {1: (-0.5, 0.5)}


        # --- Measurement -----------------------------------------------------
        meas = _cfg_section(self._raw, "Measurement")
        self.num_measurements: int = int(meas["num_measurements"])
        self.trigger_delay: float = float(meas.get("trigger_delay", "0"))

        # --- Paths -----------------------------------------------------------
        paths = _cfg_section(self._raw, "Paths")
        base_output = Path(paths["output_dir"])
        # Append timestamped subdirectory: yyyy-mm-dd/HH-MM/
        timestamp = datetime.now()
        self.output_dir: Path = (
            base_output
            / timestamp.strftime("%Y-%m-%d")
            / timestamp.strftime("%H-%M")
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.awg_config_path: str = paths["config_awg_path"]
        self.save_optimized_to: Optional[str] = paths.get("save_optimized_to")

    # ----- convenience -------------------------------------------------------

    def get_theoretical_signal_path(self) -> str:
        """Return the CSV path for the configured pulse type."""
        path = self.pulse_paths.get(self.pulse_type)
        if path is None:
            raise KeyError(
                f"Pulse type '{self.pulse_type}' not found in [Pulse_paths]. "
                f"Available: {list(self.pulse_paths.keys())}"
            )
        return str(path)


# =========================================================================
# PulseShapeExperimentResult
# =========================================================================

class PulseShapeExperimentResult:
    """
    Container for all data produced by a single pulse-shape experiment run.

    Attributes:
        waveform_sent       – the waveform that was uploaded to the AWG
        measured_signal     – scope-measured voltage (resampled to waveform length)
        theoretical_signal  – the target / desired waveform
        time_array          – time axis in seconds
        measured_std        – per-sample standard deviation from the scope
        mse, rmse, mae      – error metrics (measured vs theoretical)
        signed_error        – element-wise (measured − theoretical)
    """

    def __init__(
        self,
        waveform_sent: np.ndarray,
        measured_signal: np.ndarray,
        theoretical_signal: np.ndarray,
        time_array: np.ndarray,
        measured_std: Optional[np.ndarray],
        metrics: Dict[str, float],
    ) -> None:
        # Keep raw copies for optimisation maths
        self._raw_waveform_sent = waveform_sent.copy()
        self._raw_measured_signal = measured_signal.copy()
        self._raw_theoretical_signal = theoretical_signal.copy()

        # Normalise all signals to [0, 1]
        self.waveform_sent = self._normalise_01(waveform_sent)
        self.measured_signal = self._normalise_01(measured_signal)
        self.theoretical_signal = self._normalise_01(theoretical_signal)

        self.time_array = time_array
        self.measured_std = measured_std

        self.mse: float = metrics["mse"]
        self.rmse: float = metrics["rmse"]
        self.mae: float = metrics["mae"]

        self.signed_error: np.ndarray = self.measured_signal - self.theoretical_signal

    @staticmethod
    def _normalise_01(signal: np.ndarray) -> np.ndarray:
        """Scale *signal* so its values lie in [0, 1]."""
        sig = np.asarray(signal, dtype=float)
        smin, smax = sig.min(), sig.max()
        if smax - smin == 0:
            return np.zeros_like(sig)
        return (sig - smin) / (smax - smin)

    # ----- plotting ----------------------------------------------------------

    def plot(
        self,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        """
        Plot the AWG-sent signal, scope-measured signal, and theoretical
        signal on the same axes (all scaled for visibility).

        Args:
            output_dir: Directory to save the figure in.  Ignored when
                        *filename* is ``None``.
            filename:   If given, save the plot to this file name inside
                        *output_dir*.
            title:      Custom plot title.  Defaults to an informative string
                        including the MSE.
        """
        # Signals are already normalised to [0, 1]
        fig, ax = plt.subplots(figsize=(11, 6))

        ax.plot(
            self.time_array, self.waveform_sent, linewidth=1.2, color="blue",
            label="AWG input (sent)",
        )
        ax.plot(
            self.time_array, self.measured_signal, linewidth=1.5, color="green",
            label="Scope measurement",
        )
        ax.plot(
            self.time_array, self.theoretical_signal, linewidth=1.5,
            linestyle="--", color="red", label="Theoretical (desired)",
        )

        if self.measured_std is not None and self._raw_measured_signal.max() != 0:
            raw_max = self._raw_measured_signal.max()
            raw_min = self._raw_measured_signal.min()
            denom = raw_max - raw_min if raw_max != raw_min else 1.0
            std_norm = self.measured_std / denom
            ax.fill_between(
                self.time_array,
                self.measured_signal - std_norm,
                self.measured_signal + std_norm,
                color="green", alpha=0.2, label="Measurement std",
            )

        if title is None:
            title = f"Pulse Shape Experiment — MSE = {self.mse:.4e}"
        ax.set_title(title)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Normalised amplitude")
        ax.legend(loc="best")
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

        fig.tight_layout()

        if filename and output_dir:
            save_path = Path(output_dir) / filename
            save_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            logger.info(f"Saved plot: {save_path}")

        plt.show(block=False)
        plt.pause(1)
        plt.close(fig)

    def save_to_csv(self, csv_path: str, to_save = "measured") -> None:
        """Save the measured signal to a headerless CSV file."""
        if to_save == "measured":
            signal_to_save = self.measured_signal
        elif to_save == "theoretical":
            signal_to_save = self.theoretical_signal
        elif to_save == "sent":
            signal_to_save = self.waveform_sent
        else:
            raise ValueError(f"Invalid to_save value: {to_save}. Must be 'measured', 'theoretical', or 'sent'.")
        np.savetxt(csv_path, signal_to_save, delimiter=",")
        logger.info(f"Saved measured signal to CSV: {csv_path}")


# =========================================================================
# PulseShapeExperimentRunner
# =========================================================================

class PulseShapeExperimentRunner:
    """
    Runs a single pulse-shape experiment: programs the AWG, measures the
    scope response, and returns a :class:`PulseShapeExperimentResult`.

    Args:
        config:   A :class:`PulseShapeConfig` describing the hardware setup.
        waveform: 1-D numpy array — the waveform to play on the AWG channel.
    """

    # Map channel name strings to integers (matching awg_control2 convention)
    _CH_MAP: Dict[str, int] = {
        'channel1': 1, 'channel2': 2, 'channel3': 3, 'channel4': 4,
        'ch1': 1, 'ch2': 2, 'ch3': 3, 'ch4': 4,
        '1': 1, '2': 2, '3': 3, '4': 4,
    }

    def __init__(self, config: PulseShapeConfig, waveform: np.ndarray) -> None:
        self.config = config
        self.waveform = waveform

        self.scope: Optional[OscilloscopeManager] = None
        self._owns_scope: bool = False
        self.awg: Optional[AWGManager] = None
        self.awg_config_obj: Optional[AwgConfiguration] = None
        self.waveform_duration_s: float = 0.0

    # ----- helpers -----------------------------------------------------------

    @classmethod
    def _ch_int(cls, ch) -> int:
        """Convert a channel identifier (string or int) to an integer 1–4."""
        if isinstance(ch, int):
            return ch
        key = str(ch).lower().strip()
        if key in cls._CH_MAP:
            return cls._CH_MAP[key]
        raise ValueError(f"Unknown AWG channel identifier: {ch!r}")

    # ----- hardware helpers --------------------------------------------------

    def _connect_awg(self) -> AWGManager:
        """Return the existing AWGManager or create a new connection."""
        if self.awg is not None:
            try:
                if self.awg.is_connected():
                    return self.awg
            except Exception:
                pass
        logger.info("Connecting to AWG...")
        self.awg = AWGManager()  # auto-detects by manufacturer ID
        return self.awg

    def _connect_scope(self) -> OscilloscopeManager:
        """Connect to oscilloscope using the ID from config."""
        logger.info(f"Connecting to scope: {self.config.scope_id}")
        self.scope = OscilloscopeManager(self.config.scope_id)
        self._owns_scope = True
        return self.scope

    def _load_awg_config(self) -> AwgConfiguration:
        """Load the AWG configuration from the .ini path in config."""
        logger.info(f"Loading AWG config from {self.config.awg_config_path}")
        cfg = ConfigObj(self.config.awg_config_path)
        cfg_d = cast(Dict[str, Any], cfg)

        waveforms_section = cast(Dict[str, Dict[str, Any]], cfg_d["waveforms"])

        waveforms: List[Waveform] = []
        for _key, v in waveforms_section.items():
            _phases = [(float(p), i) for i, p in enumerate(v["phases"])]
            waveforms.append(
                Waveform(
                    fname=v["filename"],
                    mod_frequency=float(v["modulation frequency"]),
                    phases=_phases,
                )
            )

        awg_config = AwgConfiguration(
            sample_rate=float(cfg_d["sample rate"]),
            burst_count=int(cfg_d["burst count"]),
            waveform_output_channels=list(cfg_d["waveform output channels"]),
            waveform_output_channel_lags=list(
                map(float, cfg_d["waveform output channel lags"])
            ),
            marked_channels=list(cfg_d["marked channels"]),
            marker_width=eval(cfg_d["marker width"]),
            waveform_sequence=list(eval(cfg_d["waveform sequence"])),
            waveforms=waveforms,
            waveform_stitch_delays=list(eval(cfg_d["waveform stitch delays"])),
            interleave_waveforms=cfg_d.get("interleave waveforms", "false").lower()
            in ("true", "t", "yes", "y"),
        )

        self.awg_config_obj = awg_config
        logger.info("AWG configuration loaded")
        return self.awg_config_obj

    def _program_awg(self, signal: np.ndarray, label: str = "signal") -> None:
        """
        Upload *signal* to the AWG on the configured channel and arm.

        Uses :class:`AWGManager` directly to:
        1. Abort & disable all channels (safe state during programming).
        2. Clear waveform memory, set sample rate, output mode, coupling.
        3. Build per-channel waveform arrays from the AwgConfiguration,
           substituting the target channel's waveform with *signal*.
        4. Align all channels to the same length (multiple-of-16).
        5. Upload waveforms, configure triggers, burst count and amplitude.
        6. Configure marker pulses on marked channels.
        7. Enable channel outputs and arm for trigger.
        """
        if self.awg_config_obj is None:
            self._load_awg_config()
        cfg = cast(AwgConfiguration, self.awg_config_obj)

        # Save CSV for record-keeping
        self._save_waveform_csv(signal, label)

        # --- Validate target channel -----------------------------------------
        ch_idx = self.config.channel - 1
        print(f"Config AWG channel: {self.config.channel} (index {ch_idx})")
        if ch_idx >= len(cfg.waveform_sequence):
            raise ValueError(
                f"Channel {self.config.channel} not in AWG waveform_sequence "
                f"({len(cfg.waveform_sequence)} channels configured)"
            )
        wf_ids = cfg.waveform_sequence[ch_idx]
        if not wf_ids:
            raise ValueError(f"No waveforms configured for channel {self.config.channel}")

        # Replace the first waveform on the target channel with our signal
        target_wf_id = wf_ids[0]
        cfg.waveforms[target_wf_id].data = signal.tolist()

        logger.info(
            f"Programming AWG ch{self.config.channel} with '{label}' "
            f"({len(signal)} samples, wf_id={target_wf_id})"
        )

        # --- Connect to AWG --------------------------------------------------
        awg = self._connect_awg()
        awg.reset()

        ch_names = cfg.waveform_output_channels
        ch_ints = [1]#[self._ch_int(c) for c in ch_names]

        # 1. Safe state: stop output and disable all channels
        #awg.abort() # I don't think you need to do this
        awg.disable_all_channels(ch_ints)
        awg.clear_all()

        # 2. Global configuration
        awg.configure_sample_rate(cfg.sample_rate)
        awg.set_output_mode("USER")           # arbitrary waveform mode
        awg.enable_coupling()

        # Configure trigger
        print("Configuring trigger settings for all channels")
        for ch_int in ch_ints:
            awg.select_channel(ch_int)
            awg.set_burst_count(cfg.burst_count)
            awg.set_continuous(True)#False)# in future we'll want this to be false
            awg.set_trigger_level(1.6)  # volts, adjust as needed
            awg.set_trigger_source("EXT")  # external trigger
            awg.set_trigger_slope("POS")  # trigger on rising edge

        opc = awg.wait_opc()
        print("channel triggers configured")

        #awg.set_trace_mode("SING")

        # --- Compute channel timing offsets ----------------------------------
        lags = np.asarray(cfg.waveform_output_channel_lags, dtype=float)
        raw_offsets = np.rint(lags * cfg.sample_rate * 1e-6).astype(int)
        abs_offsets = raw_offsets - raw_offsets.min()

        # --- Calculate stitch delays for interleaved waveforms ---------------
        if cfg.interleave_waveforms:
            stitch_delays: List[int] = []
            for direction, target_wf_ids in cfg.waveform_stitch_delays:
                ids = target_wf_ids or []
                total = sum(cfg.waveforms[wid].get_n_samples() for wid in ids)
                stitch_delays.append(int(direction) * total)
        else:
            stitch_delays = [0] * len(ch_names)

        # --- Build per-channel waveform arrays -------------------------------
        all_channel_data: List[np.ndarray] = []
        for i, (ch_name, s_delay, ch_offset) in enumerate(
            zip(ch_names, stitch_delays, abs_offsets)
        ):
            ch_wf_ids = cfg.waveform_sequence[i]
            waveforms = [cfg.waveforms[wid] for wid in ch_wf_ids]

            raw_chunks = [
                np.array(w.get(sample_rate=cfg.sample_rate)) for w in waveforms
            ]
            full_wf = np.concatenate(raw_chunks)

            # Stitch-delay padding
            pad_l = abs(s_delay) if s_delay < 0 else 0
            pad_r = abs(s_delay) if s_delay > 0 else 0
            full_wf = np.pad(full_wf, (pad_l, pad_r), "constant")

            # Channel timing-offset padding (shift waveform right)
            full_wf = np.pad(full_wf, (ch_offset, 0), "constant")

            all_channel_data.append(full_wf)

        # --- Align all channels to the same length (mult of 16) --------------
        max_len = max(len(d) for d in all_channel_data)
        if max_len % 16 != 0:
            max_len += 16 - (max_len % 16)
        aligned: List[np.ndarray] = [
            np.pad(d, (0, max_len - len(d)), "constant") for d in all_channel_data
        ]
        print(f"Aligned all channels to {max_len} samples (multiple of 16)")
        #print(f"Configuring trigger mode")
        #awg.configure_trigger(mode="EXT", level=1.6, slope="POS")
        #print(f"Setting burst count to {cfg.burst_count}")
        #awg.set_burst_count(cfg.burst_count)
        
        # --- Upload waveforms and configure per-channel settings --------------
        for ch_int, data in zip(ch_ints, aligned):
            print(f"Uploading to channel {ch_int} (length {len(data)} samples)")

            awg.upload_waveform(data, segment=1, channel=ch_int)
            awg.wait_opc()
            print(f"Uploaded waveform to channel {ch_int}, segment 1")

        awg.set_amplitude(1, 0.3)  # volts, adjust as needed
        awg.set_offset(1, 0.0)     # volts, adjust as needed

        print("All waveforms uploaded and amplitudes set")
        # # --- Configure markers -----------------------------------------------
        # #marker_wid = int(cfg.marker_width * 1e-6 * cfg.sample_rate)
        # # NOTE: marker width not being used currently
        # marked_ch_ints = {self._ch_int(c) for c in cfg.marked_channels if c}
        # for ch_int in ch_ints:
        #     if ch_int in marked_ch_ints:
        #         print(f"Configuring marker on channel {ch_int} with width {10} samples")
        #         awg.configure_marker(
        #             marker=1,
        #             position=0,
        #             width=10,
        #             high_level=1.2,
        #             low_level=0.0
        #         )
        #         awg.wait_opc()

        # --- Enable outputs and arm ------------------------------------------
        for ch_int in ch_ints:
            print(f"Enabling output for channel {ch_int}")
            awg.enable_channel(ch_int)
        print("AWG outputs enabled, initiating...")
        awg.initiate()
        awg.trigger()
        awg.select_channel(1)
        awg.inst.write(":TRAC:SEL 1")
        print("AWG running...")

        self.waveform_duration_s = max_len / cfg.sample_rate
        logger.info(
            f"AWG armed — waveform duration {self.waveform_duration_s * 1e6:.1f} µs"
        )

    def _save_waveform_csv(self, signal: np.ndarray, label: str) -> Path:
        """Write waveform to a timestamped CSV in the output directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = self.config.output_dir / f"awg_{label}_{timestamp}.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(signal)
        logger.info(f"Saved waveform CSV: {csv_path}")
        return csv_path

    def _build_scope_acq(self) -> "_ScopeAcquisition":
        """Build a scope acquisition helper. Returns acq."""
        acq = _ScopeAcquisition(
            self.scope,
            {
                "data_channel": self.config.data_channel,
                "channel_map": self.config.channel_map,
                "samp_rate": self.config.samp_rate,
                "timebase_range": (
                    self.config.timebase_start,
                    self.config.timebase_stop,
                ),
            },
        )
        return acq
    
    def _timebase_align(self, measured_voltage: np.ndarray, measured_std: Optional[np.ndarray],
                     theoretical_signal: np.ndarray) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        
        
        start_time = time.time()
        # begin by interpolating so scope and AWG have the same sample rate
        awg_sr = self.awg_config_obj.sample_rate # type: ignore[union-attr]
        scope_sr = self.config.samp_rate
        print(scope_sr, awg_sr)

        theoretical_points = len(theoretical_signal)
        theoretical_duration = theoretical_points / awg_sr
        
        scope_points = len(measured_voltage)
        scope_duration = scope_points / scope_sr



        awg_points = len(self.waveform)
        awg_duration = awg_points / awg_sr


        if scope_sr != awg_sr:
            # Create time axes for interpolation
            t_scope_sr = np.linspace(0, scope_duration, int(scope_duration*scope_sr))
            t_awg_sr = np.linspace(0, scope_duration, int(scope_duration*awg_sr))
            
            voltage_interp = np.interp(t_awg_sr, t_scope_sr, measured_voltage)
            if measured_std is not None:
                std_interp = np.interp(t_awg_sr, t_scope_sr, measured_std)
            else:
                std_interp = None
        else:
            voltage_interp = measured_voltage
            std_interp = measured_std
        
        # We want the measured signal to have the same number of points as the theoretical signal, and to be aligned in time.
        points_difference = len(voltage_interp) - theoretical_points
        print(f"Scope duration: {scope_duration*1e6:.2f} µs, AWG duration: {awg_duration*1e6:.2f} µs, theoretical duration: {theoretical_duration*1e6:.2f} µs.")

        print(f"Measured signal has {len(voltage_interp)} points, theoretical signal has {theoretical_points} points.")



        # if points_difference > theoretical_points*2:
        #     raise ValueError(f"The scope has {points_difference} more points than the target length, which is excessive. "
        #                      f"Check the scope timebase settings and sampling rate.")
        
        # find the optimal cropping location that minimises the MSE between the cropped measured signal and the theoretical signal
        if points_difference > 0:
            print("points_difference:", points_difference)
            # We have more points than needed, find the best crop
            best_mse = float('inf')
            best_start_idx = 0
            for start_idx in range(points_difference + 1):
                end_idx = start_idx + theoretical_points
                cropped_measured = voltage_interp[start_idx:end_idx]
                #print(len(cropped_measured), len(theoretical_signal))
                mse = np.mean((cropped_measured - theoretical_signal) ** 2)
                if mse < best_mse:
                    best_mse = mse
                    best_start_idx = start_idx

            
            voltage_crop = voltage_interp[best_start_idx:best_start_idx + theoretical_points]
            if std_interp is not None:
                std_crop = std_interp[best_start_idx:best_start_idx + theoretical_points]
            else:
                std_crop = None

        end_time = time.time()
        print(f"Timebase alignment and resampling took {end_time - start_time:.2f} seconds.")

        return voltage_crop, std_crop

    # ----- public API --------------------------------------------------------

    def run(self, scope: Optional[OscilloscopeManager] = None) -> PulseShapeExperimentResult:
        """
        Execute the physical experiment.

        1. Connect to oscilloscope (or reuse *scope* if provided).
        2. Load AWG config and program the AWG with ``self.waveform``.
        3. Measure the scope response (hardware-averaged).
        4. Resample measured signal to match waveform length.
        5. Compute error metrics against the theoretical signal.
        6. Return a :class:`PulseShapeExperimentResult`.

        Args:
            scope: Optional pre-connected :class:`OscilloscopeManager`.
                   If ``None``, a new connection is opened using
                   ``config.scope_id``.

        Returns:
            A :class:`PulseShapeExperimentResult` with all data and metrics.
        """
        # 1. Scope
        if scope is not None:
            self.scope = scope
            self._owns_scope = False
        elif self.scope is None:
            self._connect_scope()

        # 2. AWG
        self._load_awg_config()
        self._program_awg(self.waveform, label="experiment")

        # Small delay to let the AWG settle
        time.sleep(0.5)

        # 3. Scope acquisition
        acq: _ScopeAcquisition = self._build_scope_acq()
        trig_ch, trig_level = self.config.trigger_channel, self.config.trigger_level

        acq.configure(trig_ch, trig_level)
        mean_df, std_df = acq.acquire_data(
            [self.config.data_channel], self.config.num_measurements
        )

        # Extract voltage columns
        voltage_col = [c for c in mean_df.columns if "Voltage" in c][0]
        print(f"Extracted voltage column from scope data: '{voltage_col}'")
        measured_voltage = mean_df[voltage_col].values

        std_col = [c for c in std_df.columns if "Voltage" in c]
        measured_std = (
            std_df[std_col[0]].values if std_col and len(std_df) > 0 else None
        )

        theo_path = self.config.get_theoretical_signal_path()
        theoretical_signal = load_signal_from_path(theo_path, self.config.amplitude)

        # 4. time align the measured signal and resample to match the length of the AWG waveform
        measured_voltage, measured_std = self._timebase_align(measured_voltage, measured_std, theoretical_signal)


        # Build time array
        assert self.awg_config_obj is not None
        total_length_s = (1.0 / self.awg_config_obj.sample_rate) * len(self.waveform)
        time_array = np.linspace(0, total_length_s, len(self.waveform), endpoint=True)

        # 5. Compute theoretical signal & error metrics

        # Ensure matching lengths
        min_len = min(len(measured_voltage), len(theoretical_signal), len(self.waveform))
        measured_voltage = measured_voltage[:min_len]
        theoretical_signal = theoretical_signal[:min_len]
        time_array = time_array[:min_len]
        if measured_std is not None:
            measured_std = measured_std[:min_len]

        metrics = compute_error_metrics(measured_voltage, theoretical_signal, time_array)

        # 6. Build result
        return PulseShapeExperimentResult(
            waveform_sent=self.waveform[:min_len],
            measured_signal=measured_voltage,
            theoretical_signal=theoretical_signal,
            time_array=time_array,
            measured_std=measured_std,
            metrics=metrics,
        )

    def close(self) -> None:
        """Release hardware connections opened by this runner."""
        if self.awg is not None:
            try:
                self.awg.abort()
                self.awg.close()
            except Exception:
                pass
            self.awg = None
        if self.scope is not None and self._owns_scope:
            try:
                self.scope.quit()
            except Exception:
                pass
            self.scope = None


# =========================================================================
# Internal scope helper  (replaces ScopeDataAcquisition from core)
# =========================================================================

class _ScopeAcquisition:
    """Thin wrapper around OscilloscopeManager for configure → acquire."""

    def __init__(self, osc_manager: Any, scope_config: Dict) -> None:
        self.osc = osc_manager
        self.scope_config = scope_config

    def configure(
        self,
        trigger_channel: int,
        trigger_level: float,
        trigger_slope: str = "+",
    ) -> None:
        """Configure scope channels, timebase, and trigger."""
        self.osc.configure_scope(
            self.scope_config["channel_map"],
            samp_rate=self.scope_config["samp_rate"],
            timebase_range=self.scope_config["timebase_range"],
        )
        self.osc.configure_trigger(trigger_channel, trigger_level, trigger_slope)

    def acquire_data(
        self, channels: List[int], num_measurements: int = 50
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Hardware-averaged acquisition; returns (mean_df, std_df)."""
        logger.info(
            f"Acquiring {num_measurements}-average waveform on channels {channels}"
        )
        mean_df = self.osc.read_slow_return_data_avgd(
            channels, averages=num_measurements
        )
        if mean_df is None:
            raise RuntimeError("Averaged acquisition returned no data")

        # Build a zero-std DataFrame for interface compatibility
        std_df = mean_df.copy()
        for col in std_df.columns:
            if col != "Time (s)":
                std_df[col] = 0.0

        return mean_df, std_df
