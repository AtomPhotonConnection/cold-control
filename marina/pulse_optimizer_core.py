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
from typing import Tuple, Dict, List, Optional, Union
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =========================================================================
# Physical Constants & Conversion Functions
# =========================================================================

class PhysicalConstants:
    """Container for atomic physics constants used in laser power calculations."""
    
    # D1 transition (787 nm)
    GAMMA_D1 = 5.746 * np.pi  # rad/s
    D_D1 = 2.537e-29  # C*m (dipole moment)
    
    # D2 transition (780 nm)
    GAMMA_D2 = 6 * np.pi  # rad/s
    D_D2 = 2.853e-29  # C*m
    
    # V-STIRAP coefficients
    CG_D2_STOKES = np.sqrt(1/30)
    CG_D2_PUMP = -np.sqrt(5/24)
    RABI_STIRAP_D1 = 41 * 2 * np.pi
    RABI_STIRAP_D2 = 49 * 2 * np.pi
    
    # Optical pumping coefficients
    CG_D2_P1 = np.sqrt(1/24)
    CG_D2_P2 = np.sqrt(1/8)
    RABI_P1_D1 = 34 * 2 * np.pi
    RABI_P1_D2 = 57.5 * 2 * np.pi
    RABI_P2_D1 = 24 * 2 * np.pi
    RABI_P2_D2 = 25.5 * 2 * np.pi


def rabi_to_laserpower(omega_mhz: float, dipole_moment: float, 
                       cg_coefficient: float, beam_waist_um: float) -> float:
    """
    Convert Rabi frequency to laser power.
    
    Args:
        omega_mhz: Rabi frequency in MHz
        dipole_moment: Dipole moment in C*m
        cg_coefficient: Clebsch-Gordan coefficient
        beam_waist_um: Beam waist in micrometers
    
    Returns:
        Laser power in mW
    """
    efield = (hbar * (omega_mhz * 1e6)) / (dipole_moment * cg_coefficient)
    intensity = (efield**2 * epsilon_0 * c) / 2
    return (intensity * np.pi * (beam_waist_um * 1e-6)**2) * 1e3


def laserpower_to_rabi(power_mw: float, dipole_moment: float,
                       cg_coefficient: float, beam_waist_um: float) -> float:
    """
    Convert laser power to Rabi frequency.
    
    Args:
        power_mw: Power in mW
        dipole_moment: Dipole moment in C*m
        cg_coefficient: Clebsch-Gordan coefficient
        beam_waist_um: Beam waist in micrometers
    
    Returns:
        Rabi frequency in MHz
    """
    intensity = power_mw / (np.pi * (beam_waist_um * 1e-6)**2 * 1e3)
    efield = np.sqrt((2 * intensity) / (epsilon_0 * c))
    omega = (dipole_moment * cg_coefficient * efield) / (hbar * 1e6)
    return omega


# =========================================================================
# Signal Loading & Interpolation
# =========================================================================

def load_theoretical_signal(csv_path: str, amplitude: float, 
                           target_length: int, total_length_ns: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Load a theoretical waveform from CSV and interpolate to desired length.
    
    Args:
        csv_path: Path to CSV file (no header, values in first row/column)
        amplitude: Normalization amplitude for the signal
        target_length: Desired output length (samples)
        total_length_ns: Total signal duration in nanoseconds
    
    Returns:
        Tuple of (original_signal, interpolated_signal, time_array)
    """
    data = pd.read_csv(csv_path, header=None)
    signal = data.T.to_numpy().flatten()
    
    # Normalize to requested amplitude
    signal = (signal / signal.max()) * amplitude
    
    # Create time arrays for interpolation
    t_original = np.linspace(0, total_length_ns * 1e-9, len(signal), endpoint=True)
    t_interpolated = np.linspace(0, total_length_ns * 1e-9, target_length, endpoint=True)
    
    # Interpolate using cubic splines
    interpolator = interp1d(t_original, signal, kind='cubic', fill_value="extrapolate")
    signal_interp = interpolator(t_interpolated)
    
    return signal, signal_interp, t_interpolated


def get_theoretical_signal_path(pulse_type: str) -> str:
    """
    Get the path to theoretical signal CSV based on pulse type.
    
    Args:
        pulse_type: One of 'stokes', 'pump', 'P1', 'P2'
    
    Returns:
        Path to CSV file
    
    Raises:
        ValueError: If pulse_type is unknown
    """
    pulse_paths = {
        'stokes': 'calibrations/StirapDL_awg/stokes.csv',
        'pump': 'calibrations/StirapDL_awg/pump.csv',
        'P1': 'calibrations/ELYSA_fibre_branch/P1.csv',
        'P2': 'calibrations/ELYSA_fibre_branch/P2.csv',
    }
    if pulse_type not in pulse_paths:
        raise ValueError(f"Unknown pulse type: {pulse_type}. Valid: {list(pulse_paths.keys())}")
    return pulse_paths[pulse_type]


# =========================================================================
# Oscilloscope Measurement
# =========================================================================

class ScopeDataAcquisition:
    """Manages oscilloscope configuration and data acquisition."""
    
    def __init__(self, osc_manager, scope_config: Dict):
        """
        Initialize scope acquisition manager.
        
        Args:
            osc_manager: Instance of OscilloscopeManager from keysight_3104A
            scope_config: Dict with keys:
                - 'channel_map': Dict of channel number to voltage range tuples
                - 'samp_rate': Sampling rate (Hz)
                - 'timebase_range': (t_start, t_stop) in seconds
        """
        self.osc = osc_manager
        self.scope_config = scope_config
        
    def configure_and_arm(self, trigger_channel: int, trigger_level: float,
                         trigger_slope: str = "+") -> bool:
        """Configure scope triggers and arm for acquisition."""
        logger.info(f"Configuring scope: channels {self.scope_config['channel_map'].keys()}")
        self.osc.configure_scope(self.scope_config['channel_map'],
                                samp_rate=self.scope_config['samp_rate'],
                                timebase_range=self.scope_config['timebase_range'])
        
        logger.info(f"Setting trigger on channel {trigger_channel} at {trigger_level}V")
        self.osc.configure_trigger(trigger_channel, trigger_level, trigger_slope)
        self.osc.arm_scope(max_acq_wait_sec=10)
        return True
    
    def acquire_data(self, channels: List[int], num_measurements: int = 50) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Perform averaged acquisition from multiple triggers.
        
        Args:
            channels: List of channel numbers to acquire
            num_measurements: Number of triggered acquisitions to average
        
        Returns:
            Tuple of (mean_signal_df, std_signal_df)
        """
        all_measurements = []
        
        for i in range(num_measurements):
            if i % 10 == 0:
                logger.info(f"Measurement {i}/{num_measurements}")
            
            success = self.osc.wait_for_acquisition(max_acq_wait_sec=5)
            if not success:
                logger.warning(f"Acquisition {i} timed out")
                continue
            
            data = self.osc.read_slow_return_data(channels)
            if data is not None:
                all_measurements.append(data)
        
        if not all_measurements:
            raise RuntimeError("No successful measurements collected")
        
        # Concatenate and compute statistics
        combined = pd.concat(all_measurements, ignore_index=True)
        mean_signal = combined.groupby('Time (s)').mean()
        std_signal = combined.groupby('Time (s)').std()
        
        return mean_signal.reset_index(), std_signal.reset_index()


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
            'text.usetex': True,
            'text.latex.preamble': r'\usepackage{amsmath}',
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
