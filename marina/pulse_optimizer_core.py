"""
Core utilities for AWG pulse optimization using adaptive filtering and oscilloscope feedback.

This module provides shared functionality for optimizing AWG output pulses by:
1. Measuring scope responses to theoretical signals
2. Applying NLMS adaptive filtering to find optimal AWG input
3. Evaluating errors and generating plots

Dependencies:
- keysight_3104A.OscilloscopeManager for oscilloscope communication
- awg_control2.configure_awg for AWG configuration
- scipy for signal processing and optimization

@author: Refactored for updated codebase
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from scipy.interpolate import interp1d
from scipy.constants import c, epsilon_0, hbar
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict, List, Optional, Union, cast
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Note: Oscilloscope manager imported dynamically for flexibility
# Uses agilent_9000.OscilloscopeManager for Agilent Infiniium 9000 series





# =========================================================================
# Signal Loading & Scaling
# =========================================================================

def load_signal_from_path(csv_path: str, amplitude: float) -> np.ndarray:
    """
    Load a waveform from CSV and interpolate to desired length.
    
    Args:
        csv_path: Path to CSV file (no header, values in first row/column)
        amplitude: Normalization amplitude for the signal
    
    Returns:
        Normalized signal as a numpy array
    """
    data = pd.read_csv(csv_path, header=None)
    signal = data.T.to_numpy().flatten()
    
    # Normalize to requested amplitude
    signal = (signal / signal.max()) * amplitude
    
    
    return signal



# =========================================================================
# Oscilloscope Measurement
# =========================================================================

class ScopeDataAcquisition:
    """Manages oscilloscope configuration and data acquisition."""
    
    def __init__(self, osc_manager, scope_config: Dict):
        """
        Initialize scope acquisition manager.
        
        Args:
            osc_manager: Instance of OscilloscopeManager from agilent_9000
            scope_config: Dict with keys:
                - 'channel_map': Dict of channel number to voltage range tuples
                - 'samp_rate': Sampling rate (Hz)
                - 'timebase_range': (t_start, t_stop) in seconds
        """
        self.osc = osc_manager
        self.scope_config = scope_config
        
    def configure(self, trigger_channel: int, trigger_level: float,
                  trigger_slope: str = "+") -> bool:
        """Configure scope channels and trigger (does NOT arm)."""
        logger.info(f"Configuring scope: channels {list(self.scope_config['channel_map'].keys())}")
        self.osc.configure_scope(self.scope_config['channel_map'],
                                samp_rate=self.scope_config['samp_rate'],
                                timebase_range=self.scope_config['timebase_range'])
        
        logger.info(f"Setting trigger on channel {trigger_channel} at {trigger_level}V")
        self.osc.configure_trigger(trigger_channel, trigger_level, trigger_slope)
        return True

    # Keep old name as alias for backwards compatibility
    def configure_and_arm(self, trigger_channel: int, trigger_level: float,
                         trigger_slope: str = "+") -> bool:
        """Configure scope and arm (legacy interface). Prefer configure()."""
        self.configure(trigger_channel, trigger_level, trigger_slope)
        self.osc.arm_scope(max_acq_wait_sec=10)
        return True
    
    def acquire_averaged(self, channels: List[int],
                         num_averages: int = 50) -> pd.DataFrame:
        """
        Acquire hardware-averaged waveform from the scope.

        Workflow:
            1. Scope is set to averaging mode with *num_averages* count.
            2. Scope free-runs (:RUN), accumulating triggered acquisitions.
            3. :DIGITIZE blocks until the requested averages are collected.
            4. The single (already averaged) waveform is read back.

        Args:
            channels: List of scope channel numbers to read.
            num_averages: Number of hardware averages.

        Returns:
            DataFrame with 'Time (s)' and 'Channel N Voltage (V)' columns.
        """
        logger.info(f"Acquiring {num_averages}-average waveform on channels {channels}")
        data = self.osc.read_slow_return_data_avgd(channels, averages=num_averages)
        if data is None:
            raise RuntimeError("Averaged acquisition returned no data")
        logger.info(f"Averaged acquisition complete — {len(data)} samples")
        return data

    def acquire_data(self, channels: List[int],
                     num_measurements: int = 50) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Acquire data using hardware averaging (single read).

        This replaces the old arm-wait-read loop.  The scope's built-in
        averaging mode collects *num_measurements* triggered waveforms and
        returns the mean in one shot.  Because the averaging is done in
        hardware there is no per-shot std; a zero-filled std DataFrame is
        returned for interface compatibility.

        Args:
            channels: Scope channel numbers to read.
            num_measurements: Number of hardware averages.

        Returns:
            Tuple of (mean_signal_df, std_signal_df)
        """
        mean_df = self.acquire_averaged(channels, num_averages=num_measurements)

        # Build a matching zero-std DataFrame for interface compatibility
        std_df = mean_df.copy()
        for col in std_df.columns:
            if col != 'Time (s)':
                std_df[col] = 0.0

        return mean_df, std_df


# =========================================================================
# NLMS Adaptive Filtering
# =========================================================================

class PositiveNLMS:
    """Normalized Least Mean Squares (NLMS) filter with positive constraint."""
    
    def __init__(self, order: int, mu: float = 0.1, min_value: float = 0.0):
        """
        Initialize NLMS filter.
        
        Args:
            order: Filter order (window size)
            mu: Step size (learning rate), typically 0.1-1.9
            min_value: Minimum output value constraint
        """
        self.order = order
        self.mu = mu
        self.min_value = min_value
        self.w = np.zeros(order)  # Filter coefficients
    
    def run(self, desired: np.ndarray, input_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray]]:
        """
        Run NLMS filter on input data.
        
        Args:
            desired: Desired signal (length N)
            input_data: Input signal array, shape (N, order) where N is number of windows
        
        Returns:
            Tuple of (output, error, filter_weights_history)
        """
        n_samples = len(desired)
        output = np.zeros(n_samples)
        error = np.zeros(n_samples)
        weights_history = []
        
        for k in range(n_samples):
            # Get input vector (window)
            x_k = input_data[k]
            
            # Calculate output
            y_k = np.dot(self.w, x_k)
            
            # Calculate error
            e_k = desired[k] - y_k
            
            # Normalize step size by input power
            x_power = np.sum(x_k ** 2)
            if x_power > 1e-10:  # Avoid division by zero
                step = (self.mu * e_k * x_k) / (x_power + 1e-10)
            else:
                step = 0
            
            # Update weights
            self.w = self.w + step
            
            # Apply constraint
            self.w = np.maximum(self.w, self.min_value)
            
            # Store results
            output[k] = y_k
            error[k] = e_k
            weights_history.append(self.w.copy())
        
        return output, error, weights_history


def find_optimal_mu(window_size: int, desired: np.ndarray, input_data: np.ndarray,
                   mu_range: Tuple[float, float] = (0.1, 1.9), n_points: int = 20) -> Tuple[float, float]:
    """
    Find optimal learning rate (mu) for NLMS filter via grid search.
    
    Args:
        window_size: Filter order
        desired: Desired signal
        input_data: Input signal array
        mu_range: (min_mu, max_mu) to test
        n_points: Number of points in grid
    
    Returns:
        Tuple of (best_mu, lowest_error)
    """
    mu_values = np.linspace(*mu_range, n_points)
    best_mu = mu_values[0]
    best_error = float('inf')
    
    for mu in mu_values:
        filt = PositiveNLMS(window_size, mu)
        output, error, _ = filt.run(desired, input_data)
        mse = np.mean(error ** 2)
        
        if mse < best_error:
            best_error = mse
            best_mu = mu
    best_error = cast(float, best_error)
    logger.info(f"Optimal mu for window {window_size}: {best_mu:.3f} (MSE: {best_error:.2e})")
    return best_mu, best_error


# =========================================================================
# Error Metrics & Comparison
# =========================================================================

def compute_error_metrics(measured: np.ndarray, theoretical: np.ndarray,
                         time_array: Optional[np.ndarray] = None) -> Dict[str, float]:
    """
    Compute various error metrics between measured and theoretical signals.
    
    Args:
        measured: Measured signal
        theoretical: Theoretical signal
        time_array: Optional time array for integral-based metrics
    
    Returns:
        Dictionary with 'mse', 'rmse', 'mae', and optionally 'trapz_error'
    """
    measured = np.asarray(measured)
    theoretical = np.asarray(theoretical)
    
    # Ensure same length
    min_len = min(len(measured), len(theoretical))
    measured = measured[:min_len]
    theoretical = theoretical[:min_len]
    
    # Compute metrics
    mse = np.mean((measured - theoretical) ** 2) / np.mean(theoretical ** 2)
    rmse = np.sqrt(mse)
    mae = np.mean(np.abs(measured - theoretical))
    
    metrics = {
        'mse': mse,
        'rmse': rmse,
        'mae': mae,
    }
    
    # Trapezoid integral-based error if time array provided
    if time_array is not None and len(time_array) == len(theoretical):
        trapz_error = np.trapz(np.abs(measured - theoretical), time_array) / np.trapz(np.abs(theoretical), time_array)
        metrics['trapz_error'] = trapz_error
    
    return metrics


def normalize_signals_to_max(measured: np.ndarray, theoretical: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Normalize both signals to the minimum of their maxima."""
    min_max = min(measured.max(), theoretical.max())
    return measured / measured.max() * min_max, theoretical / theoretical.max() * min_max


# =========================================================================
# Plotting & Visualization
# =========================================================================

class SignalPlotter:
    """Utilities for plotting optimization progress and results."""
    
    def __init__(self, output_dir: str):
        """Initialize plotter with output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure matplotlib
        plt.rcParams.update({
            'font.family': 'serif',
            'font.size': 11,
            'axes.labelsize': 12,
            'axes.titlesize': 13,
            'legend.fontsize': 10,
        })
    
    def plot_signal_comparison(self, measured: np.ndarray, time_array: np.ndarray,
                              theoretical: np.ndarray, std: Optional[np.ndarray] = None,
                              title: str = "Signal Comparison", filename: Optional[str] = None):
        """Plot measured vs theoretical signal with optional error band."""
        measured_norm, theoretical_norm = normalize_signals_to_max(measured, theoretical)
        
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.plot(time_array, measured_norm, linewidth=1.5, label='Measured', color='blue')
        
        if std is not None:
            std_norm = std / measured.max() * measured_norm.max()
            ax.fill_between(time_array, measured_norm - std_norm, measured_norm + std_norm,
                           color='blue', alpha=0.3, label='Std Dev')
        
        ax.plot(time_array, theoretical_norm, linewidth=1.5, linestyle='--', 
               color='red', label='Theoretical')
        
        ax.set_xlabel(r'Time (s)')
        ax.set_ylabel(r'Amplitude (a.u)')
        ax.set_title(title)
        ax.legend(loc='best')
        ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)
        
        if filename:
            filepath = self.output_dir / filename
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"Saved plot: {filepath}")
        
        plt.show(block=False)
        plt.pause(1)
        plt.close()
    
    def plot_filter_adaptation(self, desired: np.ndarray, output: np.ndarray,
                              error: np.ndarray, time_array: np.ndarray,
                              title: str = "NLMS Adaptation", filename: Optional[str] = None):
        """Plot NLMS filter adaptation process."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8))
        
        # Top: signals
        ax1.plot(time_array[:len(desired)], desired, 'b-', label='Desired', linewidth=1.5)
        ax1.plot(time_array[:len(output)], output, 'g--', label='Output', linewidth=1.5)
        ax1.set_ylabel('Amplitude (a.u)')
        ax1.set_title(title)
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)
        
        # Bottom: error in dB
        error_db = 10 * np.log10(np.abs(error) ** 2 + 1e-12)
        ax2.plot(error_db, 'r-', linewidth=1)
        ax2.set_xlabel('Sample')
        ax2.set_ylabel('Error (dB)')
        ax2.set_title('Adaptation Error')
        ax2.grid(True, alpha=0.3)
        
        fig.tight_layout()
        
        if filename:
            filepath = self.output_dir / filename
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"Saved plot: {filepath}")
        
        plt.show(block=False)
        plt.pause(1)
        plt.close()


    def plot_window_result(self, measured: np.ndarray, theoretical: np.ndarray,
                           filtered_output: np.ndarray, window_size: int,
                           predicted_input: Optional[np.ndarray] = None,
                           time_array: Optional[np.ndarray] = None,
                           filename: Optional[str] = None):
        """Plot measured, theoretical, NLMS-filtered output, and corrected input for a single window size."""
        n = len(filtered_output)
        has_correction = predicted_input is not None and len(predicted_input) > 0

        nrows = 2 if has_correction else 1
        fig, axes = plt.subplots(nrows, 1, figsize=(11, 5 * nrows), squeeze=False)

        if time_array is not None:
            x = time_array
            xlabel = 'Time (s)'
        else:
            x = np.arange(n)
            xlabel = 'Sample'

        # --- Top panel: filter tracking (desired vs filter output) ---
        ax_top = axes[0, 0]
        desired_slice = theoretical
        measured_slice = measured

        ax_top.plot(x, desired_slice, linewidth=1.5, linestyle='--', color='red',
                    label='Theoretical (desired)')
        ax_top.plot(x, measured_slice, linewidth=1.0, alpha=0.4, color='grey',
                    label='Measured (scope)')
        ax_top.plot(x, filtered_output, linewidth=1.5, color='green',
                    label='NLMS filter output')
        ax_top.set_xlabel(xlabel)
        ax_top.set_ylabel('Amplitude (a.u)')
        ax_top.set_title(f'Window size = {window_size} — Filter tracking')
        ax_top.legend(loc='best')
        ax_top.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

        # --- Bottom panel: corrected AWG input vs original measured ---
        if has_correction:
            predicted_input = cast(np.ndarray, predicted_input)
            ax_bot = axes[1, 0]
            n_corr = min(len(predicted_input), len(x))
            ax_bot.plot(x[:n_corr], measured_slice[:n_corr], linewidth=1.0,
                        alpha=0.5, color='grey', label='Original measured')
            ax_bot.plot(x[:n_corr], desired_slice[:n_corr], linewidth=1.5,
                        linestyle='--', color='red', label='Theoretical target')
            ax_bot.plot(x[:n_corr], predicted_input[:n_corr], linewidth=1.5,
                        color='blue', label='Corrected AWG input')
            ax_bot.set_xlabel(xlabel)
            ax_bot.set_ylabel('Amplitude (a.u)')
            ax_bot.set_title(f'Window size = {window_size} — Pre-distorted input')
            ax_bot.legend(loc='best')
            ax_bot.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

        fig.tight_layout()

        if filename:
            filepath = self.output_dir / filename
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"Saved plot: {filepath}")

        plt.close(fig)


    def plot_mse_vs_window(self, windows: List[int], mses: List[float],
                           filename: Optional[str] = None):
        """Plot MSE as a function of NLMS window size."""
        fig, ax = plt.subplots(figsize=(9, 5))

        ax.plot(windows, mses, 'o-', color='navy', linewidth=1.5, markersize=5)
        best_idx = int(np.argmin(mses))
        ax.plot(windows[best_idx], mses[best_idx], '*', color='red',
                markersize=14, label=f'Best: w={windows[best_idx]}, MSE={mses[best_idx]:.2e}')

        ax.set_xlabel('Window size')
        ax.set_ylabel('Normalised MSE')
        ax.set_title('NLMS optimisation — MSE vs window size')
        ax.legend(loc='best')
        ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

        if filename:
            filepath = self.output_dir / filename
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"Saved plot: {filepath}")

        plt.close(fig)


# =========================================================================
# Data Utilities
# =========================================================================

def save_optimization_results(results: List[Dict], output_path: str):
    """Save optimization results to CSV."""
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False)
    logger.info(f"Saved results to: {output_path}")


def resample_signal(signal: np.ndarray, original_length: int, target_length: int) -> np.ndarray:
    """Resample signal using interpolation with stride if needed."""
    if len(signal) == target_length:
        return signal
    
    if len(signal) > target_length:
        # Downsample by taking stride
        factor = len(signal) // target_length
        return signal[::factor][:target_length]
    else:
        # Upsample by padding
        padding = target_length - len(signal)
        return np.pad(signal, (padding, 0), mode='constant')
