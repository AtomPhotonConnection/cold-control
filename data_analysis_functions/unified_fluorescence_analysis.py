"""
Unified Fluorescence Analysis Pipeline

This script provides a complete pipeline for analyzing fluorescence data from oscilloscope 
CSV files. It:
1. Loads all CSV files from shot folders
2. Aligns traces based on MOT drop timing
3. Normalizes fluorescence based on before/after sequence values
4. Calculates normalized fluorescence during imaging pulse
5. Generates comprehensive plots

Usage:
    processor = UnifiedFluorescenceProcessor(root_folder)
    processor.process_all_experiments(
        fluor_drop_voltage=19.7e-3,
        mot_drop_time=600e-6,
        img_window=(1.6e-3, 2.1e-3),  # Imaging pulse time window
        background_window=(-0.5e-3, 0),  # Before MOT drop
        final_window=(4e-3, 5e-3)  # After sequence
    )
    processor.plot_results()
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import re
import warnings
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from scipy import interpolate


class UnifiedFluorescenceProcessor:
    """
    Unified processor for fluorescence data with alignment and normalization.
    """
    
    def __init__(self, root_folder: str, fluorescence_channel: int = 4, 
                 marker_channel: int = 2, rolling_window: Optional[int] = None):
        """
        Initialize the processor.
        
        Args:
            root_folder: Root directory containing shot folders
            fluorescence_channel: Channel number containing fluorescence data (default 4)
            marker_channel: Channel number containing timing marker (default 2)
            rolling_window: Optional window size for rolling average smoothing
        """
        self.root_folder = Path(root_folder)
        self.fluorescence_channel = fluorescence_channel
        self.marker_channel = marker_channel
        self.rolling_window = rolling_window
        
        self.time_col = "Time (s)"
        self.channel_cols = {
            1: "Channel 1 Voltage (V)",
            2: "Channel 2 Voltage (V)",
            3: "Channel 3 Voltage (V)",
            4: "Channel 4 Voltage (V)"
        }
        
        self.fluorescence_col = self.channel_cols[fluorescence_channel]
        self.results = []
        self.aligned_data_cache = {}
        
    def load_csv_files(self, shot_folder: Path) -> List[pd.DataFrame]:
        """
        Load all iteration CSV files from a shot folder.
        
        Args:
            shot_folder: Path to shot folder
            
        Returns:
            List of DataFrames from CSV files
        """
        file_pattern = re.compile(r"^iteration_\d+_data\.csv$", re.IGNORECASE)
        csv_files = sorted([f for f in shot_folder.glob("*.csv") 
                           if file_pattern.match(f.name)])
        
        if not csv_files:
            raise ValueError(f"No CSV files found in {shot_folder}")
        
        dataframes = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file)
                if self.rolling_window:
                    df = self._apply_rolling_average(df, self.rolling_window)
                dataframes.append(df)
            except Exception as e:
                warnings.warn(f"Could not load {csv_file}: {e}")
        
        return dataframes
    
    def _apply_rolling_average(self, df: pd.DataFrame, window: int) -> pd.DataFrame:
        """Apply rolling average smoothing to voltage channels."""
        df_smooth = df.copy()
        for col_name in self.channel_cols.values():
            if col_name in df_smooth.columns:
                df_smooth[col_name] = df_smooth[col_name].rolling(
                    window=window, center=True, min_periods=1
                ).mean()
        return df_smooth
    
    def align_and_average(self, dataframes: List[pd.DataFrame],
                         fluor_drop_voltage: float,
                         time_before_drop: float = 1.1e-3,
                         time_after_drop: float = 5e-3,
                         num_points: int = 50000) -> Tuple[pd.DataFrame, List[float]]:
        """
        Align multiple traces based on fluorescence drop timing and average them.
        
        Args:
            dataframes: List of DataFrames to align
            fluor_drop_voltage: Voltage threshold for MOT drop detection
            time_before_drop: Time window before drop to include (seconds)
            time_after_drop: Time window after drop to include (seconds)
            num_points: Number of points in interpolated traces
            
        Returns:
            Tuple of (averaged_dataframe, list_of_drop_times)
        """
        valid_dfs = []
        drop_times = []
        
        # Find drop times for each trace
        for df in dataframes:
            fluor_data = df[self.fluorescence_col].values
            time_data = df[self.time_col].values
            
            # Find first crossing below threshold
            drop_indices = fluor_data < fluor_drop_voltage
            if not drop_indices.any():
                continue
            
            first_drop_idx = int(np.argmax(drop_indices))
            drop_time = time_data[first_drop_idx]
            
            valid_dfs.append(df)
            drop_times.append(drop_time)
        
        if not valid_dfs:
            raise ValueError(f"No traces crossed drop voltage {fluor_drop_voltage}")
        
        print(f"Aligning {len(valid_dfs)}/{len(dataframes)} traces")
        
        # Create aligned time axis (relative to drop time = 0)
        aligned_time = np.linspace(-time_before_drop, time_after_drop, num_points)
        interpolated_data = {self.time_col: aligned_time}
        
        for col_name in self.channel_cols.values():
            if col_name in valid_dfs[0].columns:
                interpolated_data[col_name] = []
        
        # Interpolate each trace to aligned time axis
        for df, drop_time in zip(valid_dfs, drop_times):
            relative_time = df[self.time_col].values - drop_time
            
            for col_name in self.channel_cols.values():
                if col_name not in df.columns:
                    continue
                
                channel_data = df[col_name].values
                
                # Create interpolation function
                f_interp = interpolate.interp1d(
                    relative_time, channel_data,
                    kind='linear', bounds_error=False, fill_value=np.nan
                )
                
                # Interpolate to aligned time
                interp_channel = f_interp(aligned_time)
                interpolated_data[col_name].append(interp_channel)
        
        # Average the interpolated data
        averaged_data = {self.time_col: aligned_time}
        for col_name in self.channel_cols.values():
            if col_name in interpolated_data and interpolated_data[col_name]:
                channel_stack = np.array(interpolated_data[col_name])
                averaged_data[col_name] = np.nanmean(channel_stack, axis=0)
        
        averaged_df = pd.DataFrame(averaged_data)
        return averaged_df, drop_times
    
    def calculate_normalized_fluorescence(self, averaged_df: pd.DataFrame,
                                         background_window: Tuple[float, float],
                                         final_window: Tuple[float, float],
                                         img_window: Tuple[float, float]) -> Dict:
        """
        Calculate normalized fluorescence with scaling.
        
        Normalization follows the formula:
        F_norm = mean((F(t) - F_background) / (F_final - F_background)) for t in img_window
        
        Args:
            averaged_df: Aligned and averaged DataFrame
            background_window: (t_start, t_end) for background (MOT on, before drop)
            final_window: (t_start, t_end) for final reference (after sequence)
            img_window: (t_start, t_end) for imaging pulse region
            
        Returns:
            Dictionary with normalization metrics
        """
        time_data = averaged_df[self.time_col].values
        fluor_data = averaged_df[self.fluorescence_col].values
        
        # Extract background (MOT on)
        bg_mask = (time_data >= background_window[0]) & (time_data <= background_window[1])
        bg_values = fluor_data[bg_mask]
        F_background = np.mean(bg_values)
        F_bg_std = np.std(bg_values)
        
        # Extract final reference (after sequence)
        final_mask = (time_data >= final_window[0]) & (time_data <= final_window[1])
        final_values = fluor_data[final_mask]
        F_final = np.mean(final_values)
        F_final_std = np.std(final_values)
        
        # Extract imaging region
        img_mask = (time_data >= img_window[0]) & (time_data <= img_window[1])
        img_values = fluor_data[img_mask]
        img_times = time_data[img_mask]
        
        if len(img_values) == 0:
            raise ValueError(f"No data in imaging window {img_window}")
        
        # Calculate normalization scale
        scale_factor = F_final - F_background
        if abs(scale_factor) < 1e-6:
            warnings.warn("Scale factor is very small, normalization may be unreliable")
            scale_factor = 1.0
        
        # Normalize fluorescence
        normalized_values = (img_values - F_background) / scale_factor
        
        # Calculate metrics
        F_normalized = np.mean(normalized_values)
        F_normalized_std = np.std(normalized_values)
        
        # Propagate uncertainty
        # For F_norm = (F - F_bg) / (F_final - F_bg)
        # Uncertainty ≈ F_norm * sqrt((std_F/F)^2 + (std_final/F_final)^2 + (std_bg/F_bg)^2)
        if abs(F_background) > 1e-6 and abs(F_final) > 1e-6:
            rel_unc = np.sqrt((F_bg_std/F_background)**2 + (F_final_std/F_final)**2)
            F_normalized_unc = F_normalized * rel_unc
        else:
            F_normalized_unc = F_normalized_std / np.sqrt(len(normalized_values))
        
        # Also calculate raw integral for reference
        img_times_expanded = img_times if len(img_times) > 1 else img_values
        raw_integral = np.trapz(img_values, img_times)
        normalized_integral = np.trapz(normalized_values, img_times)
        
        return {
            'F_background': F_background,
            'F_background_std': F_bg_std,
            'F_final': F_final,
            'F_final_std': F_final_std,
            'scale_factor': scale_factor,
            'F_normalized': F_normalized,
            'F_normalized_std': F_normalized_std,
            'F_normalized_uncertainty': F_normalized_unc,
            'raw_integral': raw_integral,
            'normalized_integral': normalized_integral,
            'num_imaging_points': len(img_values),
            'imaging_duration': img_window[1] - img_window[0]
        }
    
    def process_single_shot(self, shot_folder: Path,
                           fluor_drop_voltage: float,
                           background_window: Tuple[float, float],
                           final_window: Tuple[float, float],
                           img_window: Tuple[float, float],
                           alignment_params: Optional[Dict] = None) -> Dict:
        """
        Process a single shot folder.
        
        Args:
            shot_folder: Path to shot folder
            fluor_drop_voltage: Voltage threshold for MOT drop
            background_window: Time window for background (MOT on)
            final_window: Time window for final reference
            img_window: Time window for imaging pulse
            alignment_params: Optional dict with alignment parameters
            
        Returns:
            Dictionary with processing results
        """
        if alignment_params is None:
            alignment_params = {
                'time_before_drop': 1.1e-3,
                'time_after_drop': 5e-3,
                'num_points': 50000
            }
        
        # Load CSV files
        dataframes = self.load_csv_files(shot_folder)
        
        # Align and average
        averaged_df, drop_times = self.align_and_average(
            dataframes, fluor_drop_voltage, **alignment_params
        )
        
        # Calculate normalized fluorescence
        metrics = self.calculate_normalized_fluorescence(
            averaged_df, background_window, final_window, img_window
        )
        
        # Extract shot information
        shot_name = shot_folder.name
        shot_match = re.search(r'shot(\d+)', shot_name, re.IGNORECASE)
        shot_number = int(shot_match.group(1)) if shot_match else None
        
        # Extract parameter from parent folder if possible
        param_folder = shot_folder.parent.name
        
        result = {
            'shot_name': shot_name,
            'shot_number': shot_number,
            'parameter_folder': param_folder,
            'num_traces': len(dataframes),
            'num_valid_traces': len(drop_times),
            'mean_drop_time': np.mean(drop_times),
            'std_drop_time': np.std(drop_times),
            'shot_path': str(shot_folder),
            **metrics
        }
        
        # Store averaged data for plotting
        self.aligned_data_cache[shot_name] = averaged_df
        
        return result
    
    def process_all_experiments(self,
                               fluor_drop_voltage: float,
                               background_window: Tuple[float, float] = (-0.5e-3, 0),
                               final_window: Tuple[float, float] = (4e-3, 5e-3),
                               img_window: Tuple[float, float] = (1.6e-3, 2.1e-3),
                               alignment_params: Optional[Dict] = None,
                               save_summary: bool = True) -> pd.DataFrame:
        """
        Process all experiments in the root folder.
        
        Args:
            fluor_drop_voltage: Voltage threshold for MOT drop detection
            background_window: Time window for background normalization
            final_window: Time window for final reference
            img_window: Time window for imaging pulse
            alignment_params: Optional alignment parameters
            save_summary: Whether to save summary CSV
            
        Returns:
            DataFrame with summary results
        """
        self.results = []
        
        # Process shot folders
        for path in sorted(self.root_folder.rglob("shot*")):
            if not path.is_dir():
                continue
            
            try:
                print(f"Processing {path.name}...", end=" ")
                result = self.process_single_shot(
                    path,
                    fluor_drop_voltage,
                    background_window,
                    final_window,
                    img_window,
                    alignment_params
                )
                self.results.append(result)
                print("✓")
            except Exception as e:
                print(f"✗ ({e})")
                continue
        
        # Create summary DataFrame
        if not self.results:
            raise ValueError("No shots were successfully processed")
        
        summary_df = pd.DataFrame(self.results)
        
        # Sort by shot number if available
        if 'shot_number' in summary_df.columns:
            summary_df = summary_df.sort_values('shot_number')
        
        # Save summary
        if save_summary:
            summary_path = self.root_folder / "fluorescence_analysis_summary.csv"
            summary_df.to_csv(summary_path, index=False)
            print(f"\nSummary saved to {summary_path}")
        
        return summary_df
    
    def plot_results(self, figsize: Tuple[int, int] = (14, 10)):
        """
        Plot processed results with multiple subplots.
        
        Args:
            figsize: Figure size (width, height)
        """
        if not self.results:
            raise ValueError("No results to plot. Run process_all_experiments first.")
        
        summary_df = pd.DataFrame(self.results)
        
        # Sort by shot number if available
        if 'shot_number' in summary_df.columns:
            summary_df = summary_df.sort_values('shot_number').reset_index(drop=True)
        
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        
        # Plot 1: Normalized fluorescence vs shot
        ax = axes[0, 0]
        x_data = summary_df['shot_number'] if 'shot_number' in summary_df.columns else range(len(summary_df))
        ax.errorbar(x_data, summary_df['F_normalized'], 
                   yerr=summary_df['F_normalized_uncertainty'],
                   fmt='o-', capsize=5, label='Normalized Fluorescence')
        ax.set_xlabel('Shot Number')
        ax.set_ylabel('Normalized Fluorescence')
        ax.set_title('Normalized Fluorescence per Shot')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Plot 2: Raw integral vs shot
        ax = axes[0, 1]
        ax.plot(x_data, summary_df['raw_integral'], 'o-', label='Raw Integral')
        ax.set_xlabel('Shot Number')
        ax.set_ylabel('Raw Integral (V·s)')
        ax.set_title('Raw Fluorescence Integral')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Plot 3: Normalization factors
        ax = axes[1, 0]
        ax.plot(x_data, summary_df['F_background'], 'o-', label='Background (MOT on)', alpha=0.7)
        ax.plot(x_data, summary_df['F_final'], 's-', label='Final (After sequence)', alpha=0.7)
        ax.fill_between(x_data, 
                        summary_df['F_background'] - summary_df['F_background_std'],
                        summary_df['F_background'] + summary_df['F_background_std'],
                        alpha=0.2)
        ax.fill_between(x_data,
                        summary_df['F_final'] - summary_df['F_final_std'],
                        summary_df['F_final'] + summary_df['F_final_std'],
                        alpha=0.2)
        ax.set_xlabel('Shot Number')
        ax.set_ylabel('Fluorescence (V)')
        ax.set_title('Normalization Reference Values')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Plot 4: Number of valid traces
        ax = axes[1, 1]
        ax.bar(x_data, summary_df['num_valid_traces'], alpha=0.7, label='Valid Traces')
        ax.bar(x_data, summary_df['num_traces'] - summary_df['num_valid_traces'], 
               bottom=summary_df['num_valid_traces'], alpha=0.3, label='Invalid Traces')
        ax.set_xlabel('Shot Number')
        ax.set_ylabel('Number of Traces')
        ax.set_title('Trace Validity per Shot')
        ax.legend()
        
        fig.tight_layout()
        plt.show()
    
    def plot_averaged_traces(self, shots: Optional[List[str]] = None, figsize: Tuple[int, int] = (14, 6)):
        """
        Plot aligned and averaged traces for selected shots.
        
        Args:
            shots: List of shot names to plot (None = all)
            figsize: Figure size
        """
        if not self.aligned_data_cache:
            raise ValueError("No aligned data cached. Run process_all_experiments first.")
        
        if shots is None:
            shots = list(self.aligned_data_cache.keys())
        
        shots = [s for s in shots if s in self.aligned_data_cache]
        
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        colors = plt.cm.viridis(np.linspace(0, 1, len(shots)))
        
        # Plot fluorescence channel
        ax = axes[0]
        for shot_name, color in zip(shots, colors):
            df = self.aligned_data_cache[shot_name]
            ax.plot(df[self.time_col] * 1e3, df[self.fluorescence_col], 
                   label=shot_name, color=color, linewidth=2)
        ax.set_xlabel('Time relative to MOT drop (ms)')
        ax.set_ylabel(f'{self.fluorescence_col} (V)')
        ax.set_title('Aligned Fluorescence Traces')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Plot all channels
        ax = axes[1]
        shot_name = shots[0]
        df = self.aligned_data_cache[shot_name]
        for col_name in self.channel_cols.values():
            if col_name in df.columns:
                ax.plot(df[self.time_col] * 1e3, df[col_name], label=col_name, linewidth=1.5)
        ax.set_xlabel('Time relative to MOT drop (ms)')
        ax.set_ylabel('Voltage (V)')
        ax.set_title(f'All Channels - {shot_name}')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        fig.tight_layout()
        plt.show()


def example_usage():
    """Example usage of the UnifiedFluorescenceProcessor."""
    
    # Set up parameters - modify these for your experiment
    root_folder = r"d:\pulse_shaping_data\2025-06-12\16-04-01\sweeped_pump_optimised_stokes_optimised_126_80"
    
    # Initialize processor
    processor = UnifiedFluorescenceProcessor(
        root_folder,
        fluorescence_channel=4,
        marker_channel=2,
        rolling_window=None  # Set to e.g. 64 for smoothing
    )
    
    # Process all experiments
    summary_df = processor.process_all_experiments(
        fluor_drop_voltage=19.7e-3,  # Voltage threshold for MOT drop
        background_window=(-0.5e-3, 0),  # Before MOT drop
        final_window=(4e-3, 5e-3),  # After sequence
        img_window=(1.6e-3, 2.1e-3),  # Imaging pulse
        alignment_params={
            'time_before_drop': 1.1e-3,
            'time_after_drop': 5e-3,
            'num_points': 50000
        },
        save_summary=True
    )
    
    # Display summary
    print("\n" + "="*80)
    print("ANALYSIS SUMMARY")
    print("="*80)
    print(summary_df[['shot_name', 'num_valid_traces', 'F_normalized', 
                      'F_normalized_uncertainty', 'raw_integral']].to_string())
    
    # Plot results
    processor.plot_results()
    processor.plot_averaged_traces()


if __name__ == "__main__":
    example_usage()
