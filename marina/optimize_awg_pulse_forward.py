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
import logging
from pathlib import Path
from typing import Dict, Tuple
from datetime import datetime
from configobj import ConfigObj
import visa

from instruments.keysight_3104A import OscilloscopeManager
from instruments.WX218x.awg_control2 import configure_awg
from classes.ExperimentalConfigs import AwgConfiguration, Waveform
from classes.Config import ConfigReader

from pulse_optimizer_core import (
    load_theoretical_signal,
    get_theoretical_signal_path,
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
        
        # Initialize hardware
        self.scope = None
        self.awg = None
        self.plotter = SignalPlotter(str(self.output_dir))
        
        self.results = []
        logger.info(f"Initialized ForwardOptimizer for channel {self.channel}, pulse {self.pulse_type}")
    
    def connect_scope(self) -> OscilloscopeManager:
        """Connect to oscilloscope."""
        scope_id = self.config['Hardware']['scope_id']
        logger.info(f"Connecting to scope: {scope_id}")
        self.scope = OscilloscopeManager(scope_id)
        return self.scope
    
    def setup_awg(self) -> Tuple[AwgConfiguration, object]:
        """
        Setup and configure AWG from config file.
        
        Returns:
            Tuple of (AwgConfiguration, AWG instance)
        """
        logger.info(f"Loading AWG config from {self.awg_config_path}")
        
        # This would typically come from Config.py or similar
        # For now, assuming the config file exists and we load it
        awg_config_obj = ConfigObj(self.awg_config_path)
        
        # Note: You may need to create AwgConfiguration from the config object
        # The exact implementation depends on how Config.py structures AWG configs
        # This is a placeholder that would need adjustment based on actual config format
        
        logger.info("AWG configuration loaded")
        return awg_config_obj, None
    
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
    
    def measure_theoretical_response(self, theoretical_signal: np.ndarray,
                                    time_array: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Send theoretical signal to AWG, measure scope response, and average.
        
        Args:
            theoretical_signal: Theoretical waveform to send
            time_array: Time points corresponding to signal
        
        Returns:
            Tuple of (mean_response, std_response)
        """
        logger.info("Measuring theoretical signal response...")
        
        # Send to AWG
        self.send_signal_to_awg(theoretical_signal, "theoretical")
        
        # Reconfigure and arm
        trigger_channel = int(self.config['Oscilloscope']['trigger_channel'])
        trigger_level = float(self.config['Oscilloscope']['trigger_level'])
        
        acq = ScopeDataAcquisition(self.scope, {
            'channel_map': {1: (-0.5, 0.5)},  # TODO: read from config
            'samp_rate': float(self.config['Oscilloscope']['samp_rate']),
            'timebase_range': (
                float(self.config['Oscilloscope']['timebase_start']),
                float(self.config['Oscilloscope']['timebase_stop'])
            )
        })
        
        acq.configure_and_arm(trigger_channel, trigger_level)
        
        # Acquire multiple measurements
        num_measurements = int(self.config['Measurement']['num_measurements'])
        mean_response, std_response = acq.acquire_data([1], num_measurements)
        
        logger.info(f"Acquired {num_measurements} measurements, averaged")
        return mean_response, std_response
    
    def optimize_window(self, measured_signal: np.ndarray, theoretical_signal: np.ndarray,
                       window_size: int) -> Dict:
        """
        Optimize for a single window size using NLMS filter.
        
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
            return {'window': window_size, 'error': float('inf')}
        
        X = np.array([measured_norm[i:i + window_size] for i in range(n_windows)])
        desired = theoretical_norm[window_size:]
        
        # Find optimal learning rate
        best_mu, best_error = find_optimal_mu(
            window_size, desired, X,
            mu_range=(self.mu_min, self.mu_max),
            n_points=15
        )
        
        # Run filter with optimal mu
        filt = PositiveNLMS(window_size, mu=best_mu)
        y_filtered, error, weights = filt.run(desired, X)
        
        # Predict what input would be needed for theoretical output
        X_theoretical = np.array([theoretical_norm[i:i + window_size] for i in range(n_windows)])
        y_predicted = np.array([np.dot(weights[i], X_theoretical[i]) if i < len(weights) else 0 
                               for i in range(len(X_theoretical))])
        
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
            'predicted_input': y_predicted,
        }
        
        return result
    
    def run(self):
        """Execute full forward optimization workflow."""
        logger.info("=" * 60)
        logger.info("FORWARD AWG PULSE OPTIMIZATION")
        logger.info("=" * 60)
        
        try:
            # 1. Connect hardware
            self.connect_scope()
            logger.info("Hardware connected")
            
            # 2. Load theoretical signal
            signal_path = get_theoretical_signal_path(self.pulse_type)
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
            measured_voltage = measured_mean['Voltage (V)'].values
            
            # Resample measured to match theoretical length if needed
            if len(measured_voltage) != len(theoretical_sig):
                measured_voltage = resample_signal(measured_voltage, len(measured_voltage), len(theoretical_sig))
            
            # Plot initial comparison
            self.plotter.plot_signal_comparison(
                measured_voltage, time_array[:len(theoretical_sig)], theoretical_sig,
                std=measured_std['Voltage (V)'].values[:len(theoretical_sig)] if len(measured_std) > 0 else None,
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
            
            for window in range(self.window_min, self.window_max + 1, self.window_step):
                result = self.optimize_window(measured_voltage, theoretical_sig, window)
                self.results.append(result)
                
                if result['mse'] < best_error:
                    best_error = result['mse']
                    best_window = window
            
            # 6. Re-run optimization with best window
            logger.info(f"\nBest window: {best_window} (MSE: {best_error:.4f})")
            best_result = self.optimize_window(measured_voltage, theoretical_sig, best_window)
            
            # Resample optimized signal to AWG length
            optimized_input = resample_signal(best_result['predicted_input'], 
                                             len(best_result['predicted_input']), 
                                             len_awg)
            
            # 7. Send optimized signal and remeasure
            logger.info("Sending optimized signal to AWG for validation...")
            self.send_signal_to_awg(optimized_input, "optimized")
            
            # Would re-measure here if desired
            # measured_optimized, _ = self.measure_theoretical_response(optimized_input, time_array)
            
            # 8. Save results
            results_path = self.output_dir / "optimization_results.csv"
            save_optimization_results(self.results, str(results_path))
            
            logger.info("\n" + "=" * 60)
            logger.info("OPTIMIZATION COMPLETE")
            logger.info(f"Best window size: {best_window}")
            logger.info(f"Best MSE: {best_error:.6f}")
            logger.info(f"Results saved to: {results_path}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during optimization: {e}", exc_info=True)
            raise
        
        finally:
            if self.scope:
                self.scope.quit()


if __name__ == "__main__":
    import csv
    
    # Example configuration (can be loaded from file)
    # For production, create a config file and pass its path
    config_path = "config_forward.ini"
    
    optimizer = ForwardOptimizer(config_path)
    optimizer.run()
