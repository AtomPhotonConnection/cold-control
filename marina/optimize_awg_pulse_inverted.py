"""
AWG Pulse Optimization - Inverted Approach

This module implements inverted optimization of AWG output pulses:
1. Use NLMS filter in "inverted" mode: find input that would produce desired output
2. Send measured signal as input, desired as desired
3. Filter finds the input waveform that best produces the desired output

Usage:
    python optimize_awg_pulse_inverted.py

Configuration:
    Edit config_inverted.ini to set:
    - AWG/scope hardware parameters
    - Channel selection (1=Stokes, 2=Pump, 3=P1, 4=P2)
    - Pulse amplitude
    - Window and learning parameters

@author: Refactored for updated codebase
"""

import numpy as np
import pandas as pd
import time
import logging
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, cast
from datetime import datetime
from configobj import ConfigObj
import csv
import pyvisa as visa

from instruments.Oscilloscopes.agilent_mso9254A import OscilloscopeManager
from instruments.WX218x.awg_control2 import configure_awg
from classes.ExperimentalConfigs import AwgConfiguration, Waveform

from pulse_optimizer_core import (
    load_signal_from_path,
    ScopeDataAcquisition,
    PositiveNLMS,
    find_optimal_mu,
    compute_error_metrics,
    normalize_signals_to_max,
    SignalPlotter,
    save_optimization_results,
    resample_signal,
    logger
)
from scipy.signal import resample as scipy_resample



# Configure logging, save to a file with the current date in the filename
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=f"C:\\pulse_shaping_data\\logging\\{datetime.now().strftime('%Y-%m-%d')}.log",
    filemode='a'
)

def _cfg_section(cfg: ConfigObj, key: str) -> Dict[str, str]:
    """Extract a config section, with a runtime guard that survives -O."""
    section = cfg[key]
    if not isinstance(section, dict):
        raise TypeError(f"Config key '{key}' must be a section, got scalar: {section!r}")
    return section


class InvertedOptimizer:
    """
    Inverted approach: find input that produces desired output.
    
    Process:
    1. Load theoretical signal
    2. Send it to AWG
    3. Measure scope response
    4. Apply NLMS filter window by window (inverted):
       - Input: windows from desired signal
       - Desired: measured response
       - Output: predicted input waveform needed
    5. Send predicted input → should produce desired output
    """
    
    def __init__(self, config_path: str):
        """
        Initialize optimizer from config file.
        
        Config sections needed:
        - [Hardware]: scope_id, awg_id
        - [Channel]: channel (1-4), pulse_type (stokes/pump/P1/P2)
        - [Optimization]: amplitude, window_min, window_max, step_mu, max_mu, method, n_passes
        - [Paths]: output_dir, config_awg_path
        """
        self.config = ConfigObj(config_path)

        channel_cfg = _cfg_section(self.config, 'Channel')
        self.channel = int(channel_cfg['channel'])
        self.pulse_type = str(channel_cfg['pulse_type'])

        
        # Parse optimization parameters
        optimisation_cfg = _cfg_section(self.config, 'Optimization')
        self.amplitude = float(optimisation_cfg['amplitude'])
        self.window_min = int(optimisation_cfg['window_min'])
        self.window_max = int(optimisation_cfg['window_max'])
        self.window_step = int(optimisation_cfg['window_step'])
        self.mu_min = float(optimisation_cfg['mu_min'])
        self.mu_max = float(optimisation_cfg['mu_max'])
        self.mu_pts = int(optimisation_cfg['mu_pts'])
        self.method = str(optimisation_cfg['method'])
        if self.method == "multi_pass":
            self.n_passes = int(optimisation_cfg['n_passes'])
        else:
            self.n_passes = None  # Not used for non-multi_pass methods
        
        # Hardware paths
        paths_cfg = _cfg_section(self.config, 'Paths')
        self.output_dir = Path(paths_cfg['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.awg_config_path = paths_cfg['config_awg_path']

        # Parse pulse paths from config
        self.pulse_paths = cast(Dict[str, str], self.config.get('Pulse_paths', {}))
        
        # Initialize hardware
        self.scope = None
        self._owns_scope = False  # Track if this class is responsible for closing the scope
        self.awg = None
        self.awg_config_obj = None
        self.plotter = SignalPlotter(str(self.output_dir))
        
        self.results = []
        logger.info(f"Initialized InvertedOptimizer for channel {self.channel}, pulse {self.pulse_type}")
    
    def connect_scope(self) -> OscilloscopeManager:
        """Connect to Agilent 9000 series oscilloscope."""
        scope_id = str(self.config['Hardware']['scope_id']) # type: ignore
        logger.info(f"Connecting to Agilent 9000 scope: {scope_id}")
        self.scope = OscilloscopeManager(scope_id)
        self._owns_scope = True
        return self.scope

    def load_awg_config(self) -> AwgConfiguration:
        """
        Load the AWG configuration from the ini file into an AwgConfiguration object.

        The AWG config ini has top-level keys (sample rate, burst count, etc.)
        and a [waveforms] section — the same layout used by
        ExperimentConfigReader.get_photon_production_configuration() but without
        the outer [AWG] grouping.

        Returns:
            AwgConfiguration ready to be passed to configure_awg().
        """
        logger.info(f"Loading AWG config from {self.awg_config_path}")
        cfg = ConfigObj(self.awg_config_path)
        cfg_d = cast(Dict[str, Any], cfg)

        waveforms_section = cast(Dict[str, Dict[str, Any]], cfg_d['waveforms'])

        # --- Parse waveforms ---
        waveforms = []
        for _key, v in waveforms_section.items():
            _phases = [(float(p), i) for i, p in enumerate(v['phases'])]
            waveforms.append(Waveform(
                fname=v['filename'],
                mod_frequency=float(v['modulation frequency']),
                phases=_phases,
            ))

        awg_config = AwgConfiguration(
            sample_rate=float(cfg_d['sample rate']),
            burst_count=int(cfg_d['burst count']),
            waveform_output_channels=list(cfg_d['waveform output channels']),
            waveform_output_channel_lags=list(map(float, cfg_d['waveform output channel lags'])),
            marked_channels=list(cfg_d['marked channels']),
            marker_width=eval(cfg_d['marker width']),
            waveform_sequence=list(eval(cfg_d['waveform sequence'])),
            waveforms=waveforms,
            waveform_stitch_delays=list(eval(cfg_d['waveform stitch delays'])),
            interleave_waveforms=cfg_d.get('interleave waveforms', 'false').lower()
                                 in ('true', 't', 'yes', 'y'),
        )

        self.awg_config_obj = awg_config
        logger.info("AWG configuration loaded")
        return self.awg_config_obj

    def program_awg(self, signal: np.ndarray, label: str = "signal"):
        """
        program the AWG with the given waveform on the configured channel.

        Replaces the waveform data for self.channel in the loaded AwgConfiguration,
        then calls configure_awg() to upload and arm.

        Args:
            signal: Waveform array (normalised, will be written as-is).
            label:  Human-readable label for logging.
        """
        if self.awg_config_obj is None:
            self.load_awg_config()

        self.awg_config_obj = cast(AwgConfiguration, self.awg_config_obj)  # For type checker

        # Save waveform CSV for record-keeping
        csv_path = self.send_signal_to_awg(signal, label)

        # Find the waveform index used by our channel in the sequence.
        # Channel index is 0-based in the sequence list.
        ch_idx = self.channel - 1
        if ch_idx >= len(self.awg_config_obj.waveform_sequence):
            raise ValueError(f"Channel {self.channel} not found in AWG waveform_sequence "
                             f"(only {len(self.awg_config_obj.waveform_sequence)} channels configured)")

        # Get the waveform IDs for this channel and replace the first one
        wf_ids = self.awg_config_obj.waveform_sequence[ch_idx]
        if not wf_ids:
            raise ValueError(f"No waveforms configured for channel {self.channel}")

        target_wf_id = wf_ids[0]
        target_wf = self.awg_config_obj.waveforms[target_wf_id]

        # Replace the waveform data — store raw samples so get() returns them directly
        target_wf.data = signal.tolist()

        logger.info(f"Programming AWG channel {self.channel} with '{label}' waveform "
                     f"({len(signal)} samples, wf_id={target_wf_id})")

        # Close previous AWG session if open
        if self.awg is not None:
            try:
                self.awg.abort_generation()
                self.awg.close()
            except Exception:
                pass

        assert self.awg_config_obj is not None, "AWG config must be loaded before programming"
        self.awg, duration_s = configure_awg(
            self.awg_config_obj,
            marked_wfs=[1] if len(wf_ids) > 1 else [0],
            dev_mode=False,
            plot=False,
            optimised=True
        )
        logger.info(f"AWG armed — waveform duration {duration_s * 1e6:.1f} µs")

    
    def send_signal_to_awg(self, signal: np.ndarray, signal_type: str = "theoretical") -> Path:
        """
        Write signal to AWG CSV and configure AWG to use it.
        
        Args:
            signal: Waveform array to send
            signal_type: Label for the signal (used in filename)
        
        Returns:
            Path to created CSV file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = self.output_dir / f"awg_{signal_type}_{timestamp}.csv"
        
        # Write signal to CSV
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(signal)
        
        logger.info(f"Saved signal to AWG CSV: {csv_path}")
        return csv_path
    
    def _build_scope_acq(self) -> Tuple['ScopeDataAcquisition', int, float]:
        """Build a ScopeDataAcquisition from config. Returns (acq, trigger_ch, trigger_level)."""
        osc_cfg = _cfg_section(self.config, 'Oscilloscope')

        trigger_channel = int(osc_cfg['trigger_channel'])
        trigger_level = float(osc_cfg['trigger_level'])

        channel_map = {}
        for key in self.config['Oscilloscope']:
            if key.startswith('channel_') and key.endswith('_lower'):
                ch_num = int(key.split('_')[1])
                lower = float(osc_cfg[f'channel_{ch_num}_lower'])
                upper = float(osc_cfg[f'channel_{ch_num}_upper'])
                channel_map[ch_num] = (lower, upper)
        if not channel_map:
            channel_map = {1: (-0.5, 0.5)}

        acq = ScopeDataAcquisition(self.scope, {
            'channel_map': channel_map,
            'samp_rate': float(osc_cfg['samp_rate']),
            'timebase_range': (
                float(osc_cfg['timebase_start']),
                float(osc_cfg['timebase_stop'])
            )
        })
        return acq, trigger_channel, trigger_level

    def measure_scope_response(self, signal: np.ndarray, label: str = "signal") -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        program the AWG with the given waveform and measure the scope response.

        Steps:
            1. program the AWG (upload waveform, arm for trigger)
            2. Configure scope channels / trigger
            3. Hardware-average num_measurements triggers and read once

        Args:
            signal: Waveform array to send to the AWG.
            label:  Human-readable label used in filenames / logs.

        Returns:
            Tuple of (mean_response_df, std_response_df)
        """
        logger.info(f"Measuring scope response for '{label}'...")

        # 1. program AWG
        self.program_awg(signal, label)

        # Small delay to let the AWG settle
        time.sleep(0.5)

        # 2. Configure scope
        acq, trigger_channel, trigger_level = self._build_scope_acq()
        acq.configure(trigger_channel, trigger_level)

        # 3. Hardware-averaged acquisition
        meas_cfg = _cfg_section(self.config, 'Measurement')
        num_measurements = int(meas_cfg['num_measurements'])
        mean_response, std_response = acq.acquire_data([1], num_measurements)
        logger.info(f"Acquired hardware-averaged waveform ({num_measurements} averages) for '{label}'")
        return mean_response, std_response
    

    def optimize_window(self, measured_signal: np.ndarray, theoretical_signal: np.ndarray,
                       window_size: int, upsample_factor: int = 1,
                       method: str = "multi_pass", n_passes: Optional[int] = 10) -> Dict:
        """
        Optimize for a single window size using a global inverse filter.

        The filter analyses the *entire* measured waveform against the theoretical
        waveform to learn a single set of weights, then applies those converged
        weights uniformly to the theoretical signal to produce the pre-distorted
        AWG input.

        Two methods are available:

        ``"multi_pass"`` (default)
            Run the NLMS filter over the full signal ``n_passes`` times.  After
            several passes the weights converge to a stable solution that
            represents the global inverse system.  The final, converged weights
            are then applied to every window of the theoretical signal.

        ``"wiener"``
            Compute the optimal Wiener (least-squares) FIR inverse filter in one
            shot via the normal equations:  w = (X^T X)^{-1} X^T d.
            This is the closed-form solution that the NLMS filter converges
            towards.

        Args:
            measured_signal: Measured scope response (voltage).
            theoretical_signal: Target output signal (voltage).
            window_size: FIR filter order (number of taps).
            upsample_factor: Upsample both signals by this factor before
                filtering (≥ 1).  The result is downsampled back to the
                original length.
            method: ``"multi_pass"`` or ``"wiener"``.
            n_passes: Number of NLMS passes (only used when method="multi_pass").

        Returns:
            Dictionary with optimization results.
        """
        logger.info(f"\nOptimizing window={window_size}, method={method}, "
                     f"upsample={upsample_factor}x"
                     + (f", passes={n_passes}" if method == "multi_pass" else ""))

        original_length = len(theoretical_signal)

        # --- Optional upsampling ---------------------------------------------
        if upsample_factor > 1:

            up_len = original_length * upsample_factor
            measured_up = scipy_resample(measured_signal, up_len)
            theoretical_up = scipy_resample(theoretical_signal, up_len)
            measured_up = cast(np.ndarray, measured_up)
            theoretical_up = cast(np.ndarray, theoretical_up)
            logger.info(f"  Upsampled {original_length} → {up_len} samples")
        else:
            measured_up = measured_signal
            theoretical_up = theoretical_signal

        # Normalize both signals to the same scale
        measured_norm, theoretical_norm = normalize_signals_to_max(
            measured_up, theoretical_up
        )

        n_samples = len(measured_norm)
        n_windows = n_samples - window_size
        if n_windows < 1:
            logger.warning(f"Window {window_size} too large for signal length "
                           f"{n_samples}")
            return {'window': window_size, 'mse': float('inf'),
                    'upsample_factor': upsample_factor, 'method': method}

        if n_windows < 2 * window_size and method == "multi_pass":
            raise ValueError(f"Multi-pass method requires at least 2*window_size windows "
                             f"(n_windows={n_windows}, window_size={window_size})")

        # Build Toeplitz-style input matrix from MEASURED signal
        # X[i] = measured_norm[i : i + window_size]
        X_measured = np.array([measured_norm[i:i + window_size]
                               for i in range(n_windows)])

        # Desired output = theoretical signal (aligned with windows)
        desired = theoretical_norm[window_size:]

        # Truncate to matching lengths
        min_len = min(len(desired), len(X_measured))
        desired = desired[:min_len]
        X_measured = X_measured[:min_len]

        # -----------------------------------------------------------------
        # Step 1: Learn a GLOBAL set of filter weights from the whole signal
        # -----------------------------------------------------------------
        if method == "wiener":
            global_weights, best_mu = self._solve_wiener(
                X_measured, desired, window_size
            )
            # Compute filtered output for error metrics
            y_filtered = X_measured @ global_weights
            error = desired - y_filtered

        elif method == "multi_pass":
            assert n_passes is not None, "n_passes must be specified for multi_pass method"
            global_weights, best_mu, y_filtered, error = self._solve_multi_pass(
                X_measured, desired, window_size, n_passes
            )
        else:
            raise ValueError(f"Unknown method '{method}'. Use 'wiener' or 'multi_pass'.")

        logger.info(f"  Converged weights: min={global_weights.min():.4f}, "
                     f"max={global_weights.max():.4f}, "
                     f"mean={global_weights.mean():.4f}")

        # -----------------------------------------------------------------
        # Step 2: Apply the SAME global weights to the THEORETICAL signal
        #         to produce the pre-distorted AWG input
        # -----------------------------------------------------------------
        X_theoretical = np.array([theoretical_norm[i:i + window_size]
                                  for i in range(n_windows)])[:min_len]

        # Single matrix-vector product — same weights for every sample
        predicted_core = X_theoretical @ global_weights

        # Pad to full (upsampled) length — prepend unfiltered head
        predicted_input = np.concatenate([
            theoretical_norm[:window_size],
            predicted_core
        ])

        # --- Downsample back to original length if upsampled -----------------
        if upsample_factor > 1:

            predicted_input = scipy_resample(predicted_input, original_length)
            y_filtered_full = scipy_resample(
                np.concatenate([np.zeros(window_size), y_filtered]),
                original_length
            )
            y_filtered_full = cast(np.ndarray, y_filtered_full)
            error_full = scipy_resample(
                np.concatenate([np.zeros(window_size), error]),
                original_length
            )

            # Recompute metrics at original resolution
            _, theoretical_norm_orig = normalize_signals_to_max(
                measured_signal, theoretical_signal
            )
            metrics = compute_error_metrics(
                y_filtered_full[:len(theoretical_norm_orig)],
                theoretical_norm_orig[:len(y_filtered_full)]
            )
        else:
            y_filtered_full = np.concatenate([np.zeros(window_size), y_filtered])
            error_full = np.concatenate([np.zeros(window_size), error])
            metrics = compute_error_metrics(y_filtered, desired)

        result = {
            'window': window_size,
            'mu': best_mu,
            'mse': metrics['mse'],
            'rmse': metrics['rmse'],
            'mae': metrics['mae'],
            'error_array': error_full,
            'output': y_filtered_full,
            'predicted_input': predicted_input,
            'global_weights': global_weights,
            'upsample_factor': upsample_factor,
            'method': method,
        }

        return result

    def _solve_wiener(self, X: np.ndarray, desired: np.ndarray,
                      window_size: int) -> Tuple[np.ndarray, float]:
        """
        Compute the optimal Wiener (least-squares) FIR inverse filter.

        Solves:  w = (X^T X + eps I)^{-1} X^T d

        This is the closed-form solution that NLMS converges towards.  A small
        Tikhonov regularisation (eps) prevents numerical issues when X^T X is
        near-singular.

        Returns:
            (weights, mu) where mu is set to 0.0 (not applicable for Wiener).
        """
        logger.info("  Solving Wiener (least-squares) inverse filter...")
        eps = 1e-6  # Tikhonov regularisation
        XtX = X.T @ X + eps * np.eye(window_size)
        Xtd = X.T @ desired
        global_weights = np.linalg.solve(XtX, Xtd)

        # Clamp to non-negative if PositiveNLMS semantics are required
        # global_weights = np.clip(global_weights, 0, None)

        residual_mse = float(np.mean((X @ global_weights - desired) ** 2))
        logger.info(f"  Wiener solution residual MSE = {residual_mse:.6e}")
        return global_weights, 0.0

    def _solve_multi_pass(self, X: np.ndarray, desired: np.ndarray,
                          window_size: int, n_passes: int
                          ) -> Tuple[np.ndarray, float, np.ndarray, np.ndarray]:
        """
        Run the NLMS filter over the full signal multiple times until the
        weights converge to a stable global solution.

        After ``n_passes`` the weights represent the global inverse system.

        Returns:
            (global_weights, best_mu, y_filtered, error)
            where y_filtered and error are from the *final* pass.
        """
        # Find optimal learning rate on a single pass first
        best_mu, _ = find_optimal_mu(
            window_size, desired, X,
            mu_range=(self.mu_min, self.mu_max),
            n_points=self.mu_pts
        )
        logger.info(f"  Best mu = {best_mu:.4f}, running {n_passes} passes...")

        filt = PositiveNLMS(window_size, mu=best_mu)

        for pass_idx in range(n_passes):
            y_filtered, error, weights = filt.run(desired, X)
            pass_mse = float(np.mean(error ** 2))
            logger.info(f"    Pass {pass_idx + 1}/{n_passes}: MSE = {pass_mse:.6e}")

            # Check for convergence — if MSE barely changes, stop early
            if pass_idx > 0 and abs(prev_mse - pass_mse) / (prev_mse + 1e-12) < 1e-4:
                logger.info(f"    Converged after {pass_idx + 1} passes")
                break
            prev_mse = pass_mse

        # Use the final weights (last time step of last pass) as the global filter
        global_weights = weights[-1]
        logger.info(f"  Final pass MSE = {pass_mse:.6e}")

        return global_weights, best_mu, y_filtered, error

    def auto_upsample_factor(self, signal_length: int, window_size: int,
                              min_ratio: int = 3) -> int:
        """
        Compute the minimum upsample factor that gives at least
        min_ratio * window_size training samples.

        Args:
            signal_length: Number of samples in the original signal.
            window_size: NLMS filter order.
            min_ratio: Minimum desired ratio of training samples to
                       window_size (default 3).

        Returns:
            Integer upsample factor (≥ 1).
        """
        # n_windows after upsampling = signal_length * us - window_size
        # We want: signal_length * us - window_size >= min_ratio * window_size
        # => us >= (min_ratio + 1) * window_size / signal_length
        required = (min_ratio + 1) * window_size / signal_length
        us = max(1, int(np.ceil(required)))
        if us > 1:
            logger.info(f"Auto upsample: factor={us} for window={window_size}, "
                         f"signal_length={signal_length}")
        return us
    
    def run(self):
        """Execute full inverted optimization workflow."""
        logger.info("=" * 60)
        logger.info("INVERTED AWG PULSE OPTIMIZATION")
        logger.info("=" * 60)
        
        try:
            # 1. Connect hardware
            self.connect_scope()
            logger.info("Hardware connected")

            self.load_awg_config()
            
            # 2. Load theoretical signal
            signal_path = self.pulse_paths[self.pulse_type] # type: ignore

            assert type(signal_path) is str, f"Signal path for pulse '{self.pulse_type}' must be a string in config"

            scaled_sig = load_signal_from_path(
                signal_path,
                amplitude=self.amplitude
            )

            len_awg = len(scaled_sig)  # Assuming the loaded signal is already at the desired length for the AWG
            assert self.awg_config_obj is not None, "AWG config must be loaded to determine sample rate"
            total_length_s = 1/self.awg_config_obj.sample_rate *len_awg

            time_array = np.linspace(0, total_length_s, len_awg, endpoint=True)
            print(f"Loaded theoretical signal: {len(scaled_sig)} samples, duration {total_length_s*1e6:.1f} µs")
            print(f"time array inital value: {time_array[0]*1e6:.6f} us, final value: {time_array[-1]*1e6:.6f} us")
            print(f"time array num points: {len(time_array)}")
            
            logger.info(f"Loaded theoretical signal: {len(scaled_sig)} samples")
            
            # 3. Measure theoretical response
            measured_mean, measured_std = self.measure_scope_response(scaled_sig, label="theoretical")
            
            # Scope returns 'Channel N Voltage (V)' columns
            voltage_col = [c for c in measured_mean.columns if 'Voltage' in c][0]
            measured_voltage = measured_mean[voltage_col].values
            
            # Resample measured to match theoretical length if needed
            if len(measured_voltage) != len(scaled_sig):
                measured_voltage = resample_signal(measured_voltage, len(measured_voltage), len(scaled_sig))
            
            # Plot initial comparison
            std_col = [c for c in measured_std.columns if 'Voltage' in c]
            std_values = measured_std[std_col[0]].values[:len(scaled_sig)] if std_col and len(measured_std) > 0 else None
            self.plotter.plot_signal_comparison(
                measured_voltage, time_array[:len(scaled_sig)], scaled_sig,
                std=std_values,
                title="Measured vs Theoretical Signal (Before Optimization)",
                filename="01_initial_comparison.png"
            )
            
            # 4. Compute baseline error
            baseline_metrics = compute_error_metrics(measured_voltage, scaled_sig, time_array[:len(scaled_sig)])
            self.results.append({
                'window': 'baseline',
                'mse': baseline_metrics['mse'],
                'rmse': baseline_metrics['rmse'],
                'mae': baseline_metrics['mae'],
            })
            logger.info(f"Baseline MSE: {baseline_metrics['mse']:.4f}")
            
            # 5. Optimize over window sizes
            best_window = self.window_min
            best_error = float('inf')
            sweep_windows = []
            sweep_mses = []
            
            for window in range(self.window_min, self.window_max + 1, self.window_step):
                us = self.auto_upsample_factor(len(measured_voltage), window)
                result = self.optimize_window(
                    measured_voltage,
                    scaled_sig,
                    window,
                    upsample_factor=us,
                    method=self.method,
                    n_passes=self.n_passes)
                self.results.append(result)
                
                # Save per-window comparison plot
                if 'output' in result and len(result['output']) > 0:
                    self.plotter.plot_window_result(
                        measured_voltage,
                        scaled_sig,
                        result['output'],
                        predicted_input=result.get('predicted_input'),
                        window_size=window,
                        time_array=time_array,
                        filename=f"window_{window:03d}_comparison.png"
                    )
                    sweep_windows.append(window)
                    sweep_mses.append(result['mse'])
                

                if result['mse'] < best_error:
                    best_error = result['mse']
                    best_window = window

            # Plot MSE vs window size summary
            if sweep_windows:
                self.plotter.plot_mse_vs_window(
                    sweep_windows, sweep_mses,
                    filename="02_mse_vs_window.png"
                )
            
            # 6. Re-run optimization with best window
            logger.info(f"\nBest window: {best_window} (MSE: {best_error:.4f})")
            us = self.auto_upsample_factor(len(measured_voltage), best_window)
            best_result = self.optimize_window(
                    measured_voltage,
                    scaled_sig,
                    best_window,
                    upsample_factor=us,
                    method=self.method,
                    n_passes=self.n_passes)
            
            # Resample optimized signal to AWG length
            optimized_input = resample_signal(best_result['predicted_input'], 
                                             len(best_result['predicted_input']), 
                                             len_awg)

            # Renormalize to target amplitude (as in original finding_amplitude_inv.py)
            if np.max(np.abs(optimized_input)) > 0:
                optimized_input = optimized_input / np.max(np.abs(optimized_input)) * self.amplitude

            # ============================================================
            # 7. VALIDATION: send corrected input → measure → compare
            # ============================================================
            logger.info("=" * 60)
            logger.info("VALIDATION — sending optimised waveform to AWG")
            logger.info("=" * 60)

            val_mean, val_std = self.measure_scope_response(optimized_input, label="optimized")

            val_voltage_col = [c for c in val_mean.columns if 'Voltage' in c][0]
            val_voltage = val_mean[val_voltage_col].values

            # Resample to theoretical length for fair comparison
            if len(val_voltage) != len(scaled_sig):
                val_voltage = resample_signal(val_voltage, len(val_voltage), len(scaled_sig))

            # Compute validation error
            val_metrics = compute_error_metrics(
                val_voltage, scaled_sig, time_array[:len(scaled_sig)]
            )
            self.results.append({
                'window': f'validation_w{best_window}',
                'mse': val_metrics['mse'],
                'rmse': val_metrics['rmse'],
                'mae': val_metrics['mae'],
            })

            logger.info(f"Validation MSE:  {val_metrics['mse']:.6f}  "
                         f"(baseline was {baseline_metrics['mse']:.6f})")

            # Plot validation comparison
            val_std_col = [c for c in val_std.columns if 'Voltage' in c]
            val_std_values = (val_std[val_std_col[0]].values[:len(scaled_sig)]
                              if val_std_col and len(val_std) > 0 else None)
            self.plotter.plot_signal_comparison(
                val_voltage, time_array[:len(scaled_sig)], scaled_sig,
                std=val_std_values,
                title=(f"Optimised Response (window={best_window})  —  "
                       f"MSE={val_metrics['mse']:.4f}  (baseline {baseline_metrics['mse']:.4f})"),
                filename="03_validation_response.png"
            )

            # Save the optimised waveform CSV
            save_path = self.config['Paths'].get('save_optimized_to') # type: ignore
            if save_path:
                np.savetxt(save_path, optimized_input, delimiter=',')
                logger.info(f"Saved optimised waveform to {save_path}")

            
            # 8. Save results
            results_path = self.output_dir / "optimization_results.csv"
            save_optimization_results(self.results, str(results_path))
            
            logger.info("\n" + "=" * 60)
            logger.info("OPTIMIZATION COMPLETE")
            logger.info(f"Best window size: {best_window}")
            logger.info(f"Baseline MSE:    {baseline_metrics['mse']:.6f}")
            logger.info(f"Validation MSE:  {val_metrics['mse']:.6f}")
            logger.info(f"Results saved to: {results_path}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during optimization: {e}", exc_info=True)
            raise
        
        finally:
            # Close AWG if we opened it
            if self.awg is not None:
                try:
                    self.awg.abort_generation()
                    self.awg.close()
                except Exception:
                    pass
            # Only close the scope if we created it
            if self.scope and self._owns_scope:
                self.scope.quit()


if __name__ == "__main__":
    # Example configuration (can be loaded from file)
    # For production, create a config file and pass its path
    config_path = "config_inverted.ini"
    
    optimizer = InvertedOptimizer(config_path)
    optimizer.run()
