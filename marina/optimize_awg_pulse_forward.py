"""
AWG Pulse Optimization - Forward Approach

This module implements forward optimization of AWG output pulses:
1. Send theoretical signal to AWG
2. Measure scope response
3. Use NLMS filter to find optimal input that produces desired output
4. Iterate over window sizes and learning parameters

Usage:
    python optimize_awg_pulse_forward.py

Configuration:
    Edit config_forward.ini to set:
    - AWG/scope hardware parameters
    - Channel selection (1=Stokes, 2=Pump, 3=P1, 4=P2)
    - Pulse amplitude
    - Window and learning parameters

@author: Refactored for updated codebase
"""

import numpy as np
import pandas as pd
import time
import csv
import logging
from pathlib import Path
from typing import Dict, Tuple
from datetime import datetime
from configobj import ConfigObj
import pyvisa as visa

from instruments.Oscilloscopes.agilent_mso9254A import OscilloscopeManager
from instruments.WX218x.awg_control2 import configure_awg
from classes.ExperimentalConfigs import AwgConfiguration, Waveform

from pulse_optimizer_core import (
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class ForwardOptimizer:
    """
    Forward approach: optimize AWG input to get desired output.
    
    Process:
    1. Load theoretical signal
    2. Send it to AWG
    3. Measure scope response
    4. Apply NLMS filter window by window to find optimal input
    5. Send optimized input and measure → should match theoretical
    """
    
    def __init__(self, config_path: str):
        """
        Initialize optimizer from config file.
        
        Config sections needed:
        - [Hardware]: scope_id, awg_id
        - [Channel]: channel (1-4), pulse_type (stokes/pump/P1/P2)
        - [Optimization]: amplitude, window_min, window_max, step_mu, max_mu
        - [Paths]: output_dir, config_awg_path
        """
        self.config = ConfigObj(config_path)
        self.channel = int(self.config['Channel']['channel'])
        self.pulse_type = self.config['Channel']['pulse_type']
        self.amplitude = float(self.config['Optimization']['amplitude'])
        
        # Parse optimization parameters
        self.window_min = int(self.config['Optimization']['window_min'])
        self.window_max = int(self.config['Optimization']['window_max'])
        self.window_step = int(self.config['Optimization']['window_step'])
        self.mu_min = float(self.config['Optimization']['mu_min'])
        self.mu_max = float(self.config['Optimization']['mu_max'])
        
        # Hardware paths
        self.output_dir = Path(self.config['Paths']['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.awg_config_path = self.config['Paths']['config_awg_path']
        
        # Parse pulse paths from config
        self.pulse_paths = dict(self.config.get('Pulse_paths', {}))
        
        # Initialize hardware
        self.scope = None
        self._owns_scope = False  # Track if we created the scope connection
        self.awg = None
        self.awg_config_obj = None  # AwgConfiguration loaded from ini
        self.plotter = SignalPlotter(str(self.output_dir))
        
        self.results = []
        logger.info(f"Initialized ForwardOptimizer for channel {self.channel}, pulse {self.pulse_type}")
    
    def connect_scope(self) -> OscilloscopeManager:
        """Connect to Agilent 9000 series oscilloscope."""
        scope_id = self.config['Hardware']['scope_id']
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

        # --- Parse waveforms ---
        waveforms = []
        for _key, v in cfg['waveforms'].items():
            _phases = [(float(p), i) for i, p in enumerate(v['phases'])]
            waveforms.append(Waveform(
                fname=v['filename'],
                mod_frequency=float(v['modulation frequency']),
                phases=_phases,
            ))

        awg_config = AwgConfiguration(
            sample_rate=float(cfg['sample rate']),
            burst_count=int(cfg['burst count']),
            waveform_output_channels=list(cfg['waveform output channels']),
            waveform_output_channel_lags=list(map(float, cfg['waveform output channel lags'])),
            marked_channels=list(cfg['marked channels']),
            marker_width=eval(cfg['marker width']),
            waveform_sequence=list(eval(cfg['waveform sequence'])),
            waveforms=waveforms,
            waveform_stitch_delays=list(eval(cfg['waveform stitch delays'])),
            interleave_waveforms=cfg.get('interleave waveforms', 'false').lower()
                                 in ('true', 't', 'yes', 'y'),
        )

        self.awg_config_obj = awg_config
        logger.info("AWG configuration loaded")
        return self.awg_config_obj

    def programme_awg(self, signal: np.ndarray, label: str = "signal"):
        """
        Programme the AWG with the given waveform on the configured channel.

        Replaces the waveform data for self.channel in the loaded AwgConfiguration,
        then calls configure_awg() to upload and arm.

        Args:
            signal: Waveform array (normalised, will be written as-is).
            label:  Human-readable label for logging.
        """
        if self.awg_config_obj is None:
            self.load_awg_config()

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
        target_wf.n_samples = len(signal)

        logger.info(f"Programming AWG channel {self.channel} with '{label}' waveform "
                     f"({len(signal)} samples, wf_id={target_wf_id})")

        # Close previous AWG session if open
        if self.awg is not None:
            try:
                self.awg.abort_generation()
                self.awg.close()
            except Exception:
                pass

        self.awg, duration_s = configure_awg(
            self.awg_config_obj,
            marked_wfs=[1] if len(wf_ids) > 1 else [0],
            dev_mode=False,
            plot=False,
            optimised=True
        )
        logger.info(f"AWG armed — waveform duration {duration_s * 1e6:.1f} µs")

    def send_signal_to_awg(self, signal: np.ndarray, signal_type: str = "theoretical"):
        """
        Write signal to AWG CSV and configure AWG to use it.
        
        Args:
            signal: Waveform array to send
            signal_type: Label for the signal (used in filename)
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
        trigger_channel = int(self.config['Oscilloscope']['trigger_channel'])
        trigger_level = float(self.config['Oscilloscope']['trigger_level'])

        channel_map = {}
        for key in self.config['Oscilloscope']:
            if key.startswith('channel_') and key.endswith('_lower'):
                ch_num = int(key.split('_')[1])
                lower = float(self.config['Oscilloscope'][f'channel_{ch_num}_lower'])
                upper = float(self.config['Oscilloscope'][f'channel_{ch_num}_upper'])
                channel_map[ch_num] = (lower, upper)
        if not channel_map:
            channel_map = {1: (-0.5, 0.5)}

        acq = ScopeDataAcquisition(self.scope, {
            'channel_map': channel_map,
            'samp_rate': float(self.config['Oscilloscope']['samp_rate']),
            'timebase_range': (
                float(self.config['Oscilloscope']['timebase_start']),
                float(self.config['Oscilloscope']['timebase_stop'])
            )
        })
        return acq, trigger_channel, trigger_level

    def measure_scope_response(self, signal: np.ndarray, label: str = "signal") -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Programme the AWG with the given waveform and measure the scope response.

        Steps:
            1. Programme the AWG (upload waveform, arm for trigger)
            2. Configure scope channels / trigger
            3. Hardware-average num_measurements triggers and read once

        Args:
            signal: Waveform array to send to the AWG.
            label:  Human-readable label used in filenames / logs.

        Returns:
            Tuple of (mean_response_df, std_response_df)
        """
        logger.info(f"Measuring scope response for '{label}'...")

        # 1. Programme AWG
        self.programme_awg(signal, label)

        # Small delay to let the AWG settle
        time.sleep(0.5)

        # 2. Configure scope
        acq, trigger_channel, trigger_level = self._build_scope_acq()
        acq.configure(trigger_channel, trigger_level)

        # 3. Hardware-averaged acquisition
        num_measurements = int(self.config['Measurement']['num_measurements'])
        mean_response, std_response = acq.acquire_data([1], num_measurements)
        logger.info(f"Acquired hardware-averaged waveform ({num_measurements} averages) for '{label}'")
        return mean_response, std_response

    def measure_theoretical_response(self, theoretical_signal: np.ndarray,
                                    time_array: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Legacy wrapper — measures the response when the theoretical signal is on the AWG."""
        return self.measure_scope_response(theoretical_signal, label="theoretical")

    def optimize_window(self, measured_signal: np.ndarray, theoretical_signal: np.ndarray,
                       window_size: int) -> Dict:
        """
        Optimize for a single window size using NLMS filter.
        
        The NLMS filter learns weights w such that w·measured ≈ theoretical.
        This models the system transfer.  The corrected AWG input is then
        computed as:  corrected = theoretical × (theoretical / filtered_output)
        i.e. a ratio-based pre-distortion that compensates for the system response.
        
        Args:
            measured_signal: Measured scope response (voltage)
            theoretical_signal: Target output signal (voltage)
            window_size: NLMS filter order
        
        Returns:
            Dictionary with optimization results
        """
        logger.info(f"\nOptimizing for window size {window_size}...")
        
        # Normalize signals
        measured_norm, theoretical_norm = normalize_signals_to_max(measured_signal, theoretical_signal)
        
        # Create input array: each row is a window of the measured signal
        n_windows = len(measured_signal) - window_size
        if n_windows < 1:
            logger.warning(f"Window {window_size} too large for signal length {len(measured_signal)}")
            return {'window': window_size, 'mse': float('inf')}
        
        X = np.array([measured_norm[i:i + window_size] for i in range(n_windows)])
        desired = theoretical_norm[window_size:]
        
        # Truncate desired to match X length
        min_len = min(len(desired), len(X))
        desired = desired[:min_len]
        X = X[:min_len]
        
        # Find optimal learning rate
        best_mu, best_error = find_optimal_mu(
            window_size, desired, X,
            mu_range=(self.mu_min, self.mu_max),
            n_points=15
        )
        
        # Run filter with optimal mu
        filt = PositiveNLMS(window_size, mu=best_mu)
        y_filtered, error, weights = filt.run(desired, X)
        
        # Compute corrected AWG input via ratio-based pre-distortion:
        #   Where the filter output (modelled system response) is lower than
        #   desired, boost the input; where it overshoots, reduce the input.
        #   corrected = theoretical * (desired / y_filtered)
        # Guard against division by near-zero filter output
        eps = 1e-10 * np.max(np.abs(y_filtered)) if np.max(np.abs(y_filtered)) > 0 else 1e-10
        correction_ratio = np.where(
            np.abs(y_filtered) > eps,
            desired / y_filtered,
            1.0
        )
        # Clip extreme corrections to avoid instability
        correction_ratio = np.clip(correction_ratio, 0.0, 3.0)
        
        # Apply correction to the measured signal (the current AWG→scope response)
        measured_trimmed = measured_norm[window_size:window_size + min_len]
        predicted_input = measured_trimmed * correction_ratio
        
        # Compute error metrics
        metrics = compute_error_metrics(y_filtered, desired)
        
        result = {
            'window': window_size,
            'mu': best_mu,
            'mse': metrics['mse'],
            'rmse': metrics['rmse'],
            'mae': metrics['mae'],
            'error_array': error,
            'output': y_filtered,
            'desired': desired,
            'predicted_input': predicted_input,
            'correction_ratio': correction_ratio,
        }
        
        return result
    
    def run(self):
        """Execute full forward optimization workflow."""
        logger.info("=" * 60)
        logger.info("FORWARD AWG PULSE OPTIMIZATION")
        logger.info("=" * 60)
        
        try:
            # 1. Connect hardware (only if not already connected)
            if self.scope is None:
                self.connect_scope()
            logger.info("Hardware connected")

            # Load AWG configuration
            self.load_awg_config()

            # 2. Load theoretical signal
            signal_path = self.pulse_paths[self.pulse_type]
            len_awg = int(self.config['Optimization']['len_awg'])
            
            original_sig, theoretical_sig, time_array = load_theoretical_signal(
                signal_path,
                amplitude=self.amplitude,
                target_length=6000,
                total_length_ns=float(len_awg)
            )
            
            logger.info(f"Loaded theoretical signal: {len(original_sig)} → {len(theoretical_sig)} samples")
            
            # 3. Measure theoretical response
            measured_mean, measured_std = self.measure_theoretical_response(theoretical_sig, time_array)
            
            # Scope returns 'Channel N Voltage (V)' columns
            voltage_col = [c for c in measured_mean.columns if 'Voltage' in c][0]
            measured_voltage = measured_mean[voltage_col].values
            
            # Resample measured to match theoretical length if needed
            if len(measured_voltage) != len(theoretical_sig):
                measured_voltage = resample_signal(measured_voltage, len(measured_voltage), len(theoretical_sig))
            
            # Plot initial comparison
            std_col = [c for c in measured_std.columns if 'Voltage' in c]
            std_values = measured_std[std_col[0]].values[:len(theoretical_sig)] if std_col and len(measured_std) > 0 else None
            self.plotter.plot_signal_comparison(
                measured_voltage, time_array[:len(theoretical_sig)], theoretical_sig,
                std=std_values,
                title="Theoretical Signal Response (Before Optimization)",
                filename="01_initial_response.png"
            )
            
            # 4. Compute baseline error
            baseline_metrics = compute_error_metrics(measured_voltage, theoretical_sig, time_array[:len(theoretical_sig)])
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
                result = self.optimize_window(measured_voltage, theoretical_sig, window)
                self.results.append(result)
                
                # Save per-window comparison plot
                if 'output' in result and len(result['output']) > 0:
                    self.plotter.plot_window_result(
                        measured_voltage, theoretical_sig, result['output'],
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
            
            # 6. Re-run optimization with best window to get the corrected input
            logger.info(f"\nBest window: {best_window} (MSE: {best_error:.4f})")
            best_result = self.optimize_window(measured_voltage, theoretical_sig, best_window)
            
            # Resample corrected input to AWG length
            optimized_input = resample_signal(
                best_result['predicted_input'],
                len(best_result['predicted_input']),
                len_awg
            )

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
            if len(val_voltage) != len(theoretical_sig):
                val_voltage = resample_signal(val_voltage, len(val_voltage), len(theoretical_sig))

            # Compute validation error
            val_metrics = compute_error_metrics(
                val_voltage, theoretical_sig, time_array[:len(theoretical_sig)]
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
            val_std_values = (val_std[val_std_col[0]].values[:len(theoretical_sig)]
                              if val_std_col and len(val_std) > 0 else None)
            self.plotter.plot_signal_comparison(
                val_voltage, time_array[:len(theoretical_sig)], theoretical_sig,
                std=val_std_values,
                title=(f"Optimised Response (window={best_window})  —  "
                       f"MSE={val_metrics['mse']:.4f}  (baseline {baseline_metrics['mse']:.4f})"),
                filename="03_validation_response.png"
            )

            # Save the optimised waveform CSV
            save_path = self.config['Paths'].get('save_optimized_to')
            if save_path:
                np.savetxt(save_path, optimized_input, delimiter=',')
                logger.info(f"Saved optimised waveform to {save_path}")

            # 8. Save all results
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
    # Resolve config path relative to this script's directory
    script_dir = Path(__file__).resolve().parent
    config_path = str(script_dir / "config_forward.ini")
    
    optimizer = ForwardOptimizer(config_path)
    optimizer.run()
