"""
Unified Fluorescence Analysis Pipeline

This script provides a complete pipeline for analyzing fluorescence data from oscilloscope
CSV files. It:
1. Loads all CSV files from shot folders
2. Aligns traces based on MOT drop timing
3. Normalizes fluorescence based on before/after sequence values
4. Calculates normalized fluorescence during imaging pulse
5. Generates comprehensive plots

Normalized fluorescence formula:
    F_normalized = (F(t) - F_low) / (F_high - F_low)
    where F_high = fluorescence when MOT is on (before drop)
          F_low = fluorescence when MOT is off (after sequence)
"""

import pickle
import re
import warnings
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import interpolate

# ============================================================================
# CONFIGURATION PARAMETERS - Modify these for your experiment
# ============================================================================

# Data channel configuration
FLUORESCENCE_CHANNEL = 3  # Channel containing fluorescence signal
MARKER_CHANNEL = 1  # Channel containing timing marker
ROLLING_WINDOW = 64  # Window size for rolling average smoothing (None = no smoothing)

# Voltage thresholds
FLUOR_DROP_VOLTAGE = 19.7e-3  # Voltage threshold for MOT drop detection (V)

# Time windows (relative to MOT drop time, in seconds)
# These define which regions of the trace to use for normalization and analysis
TIME_BEFORE_DROP = 1.1e-3  # How far back from MOT drop to include in alignment (s)
TIME_AFTER_DROP = 5e-3  # How far forward from MOT drop to include in alignment (s)

MOT_ON_WINDOW = (-0.5e-3, 0)  # MOT on (high fluorescence) - before drop
MOT_OFF_WINDOW = (2.5e-3, 4e-3)  # MOT off (low fluorescence) - after sequence
IMAGING_WINDOW = (1.0e-3, 1.48e-3)  # Imaging pulse time window

# Interpolation settings
NUM_INTERPOLATION_POINTS = 50000  # Number of points for aligned/averaged traces

# ============================================================================


class UnifiedFluorescenceProcessor:
    """
    Unified processor for fluorescence data with alignment and normalization.
    Uses configuration parameters defined at the top of the module.
    """

    def __init__(self, root_folder: str):
        """
        Initialize the processor with configuration parameters.

        Args:
            root_folder: Root directory containing shot folders
        """
        self.root_folder = Path(root_folder)
        self.fluorescence_channel = FLUORESCENCE_CHANNEL
        self.marker_channel = MARKER_CHANNEL
        self.rolling_window = ROLLING_WINDOW

        self.time_col = "Time (s)"
        self.channel_cols = {
            1: "Channel 1 Voltage (V)",
            2: "Channel 2 Voltage (V)",
            3: "Channel 3 Voltage (V)",
            4: "Channel 4 Voltage (V)",
        }

        self.fluorescence_col = self.channel_cols[self.fluorescence_channel]
        self.results = []
        self.aligned_data_cache = {}

    def load_csv_files(self, shot_folder: Path) -> list[pd.DataFrame]:
        """
        Load all iteration CSV files from a shot folder.

        Args:
            shot_folder: Path to shot folder

        Returns:
            List of DataFrames from CSV files
        """
        file_pattern = re.compile(r"^iteration_\d+_data\.csv$", re.IGNORECASE)
        csv_files = sorted([f for f in shot_folder.glob("*.csv") if file_pattern.match(f.name)])

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
        """Apply rolling average smoothing to the fluorescence channel only."""
        df_smooth = df.copy()
        if self.fluorescence_col in df_smooth.columns:
            df_smooth[self.fluorescence_col] = (
                df_smooth[self.fluorescence_col]
                .rolling(window=window, center=True, min_periods=1)
                .mean()
            )
        return df_smooth

    def align_and_average(
        self,
        dataframes: list[pd.DataFrame],
        fluor_drop_voltage: Optional[float] = None,
        time_before_drop: Optional[float] = None,
        time_after_drop: Optional[float] = None,
        num_points: Optional[int] = None,
    ) -> tuple[pd.DataFrame, list[float]]:
        """
        Align multiple traces based on fluorescence drop timing and average them.

        Args:
            dataframes: List of DataFrames to align
            fluor_drop_voltage: Voltage threshold for MOT drop detection (uses config if None)
            time_before_drop: Time window before drop to include (uses config if None)
            time_after_drop: Time window after drop to include (uses config if None)
            num_points: Number of points in interpolated traces (uses config if None)

        Returns:
            tuple of (averaged_dataframe, list_of_drop_times)
        """
        # Use configuration values as defaults
        fluor_drop_voltage = fluor_drop_voltage or FLUOR_DROP_VOLTAGE
        time_before_drop = time_before_drop or TIME_BEFORE_DROP
        time_after_drop = time_after_drop or TIME_AFTER_DROP
        num_points = num_points or NUM_INTERPOLATION_POINTS

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

        # Compute the safe interpolation range: intersection of all traces' relative time spans
        max_start = -time_before_drop
        min_end = time_after_drop
        for df, drop_time in zip(valid_dfs, drop_times):
            rel_time = df[self.time_col].values - drop_time
            max_start = max(max_start, rel_time[0])
            min_end = min(min_end, rel_time[-1])

        if max_start >= min_end:
            raise ValueError(
                f"No overlapping time range across traces "
                f"(range would be [{max_start * 1e3:.3f}, {min_end * 1e3:.3f}] ms)"
            )

        # Create aligned time axis clipped to the safe range
        aligned_time = np.linspace(max_start, min_end, num_points)

        # Determine which channels actually exist in the data
        available_channels = [
            col_name for col_name in self.channel_cols.values() if col_name in valid_dfs[0].columns
        ]

        interpolated_data = {col_name: [] for col_name in available_channels}

        # Interpolate each trace to aligned time axis
        for df, drop_time in zip(valid_dfs, drop_times):
            relative_time = df[self.time_col].values - drop_time

            for col_name in available_channels:
                channel_data = df[col_name].values

                # Create interpolation function
                f_interp = interpolate.interp1d(
                    relative_time,
                    channel_data,
                    kind="linear",
                    bounds_error=False,
                    fill_value=np.nan,
                )

                # Interpolate to aligned time
                interp_channel = f_interp(aligned_time)
                interpolated_data[col_name].append(interp_channel)

        # Average the interpolated data
        averaged_data = {self.time_col: aligned_time}
        for col_name in available_channels:
            if interpolated_data[col_name]:
                channel_stack = np.array(interpolated_data[col_name])
                # Check if there is any non-NaN data before averaging
                if np.all(np.isnan(channel_stack)):
                    warnings.warn(f"Channel {col_name} is all NaN after interpolation, skipping.")
                else:
                    averaged_data[col_name] = np.nanmean(channel_stack, axis=0)

        averaged_df = pd.DataFrame(averaged_data)
        return averaged_df, drop_times

    def calculate_normalized_fluorescence(
        self,
        averaged_df: pd.DataFrame,
        mot_on_window: Optional[tuple[float, float]] = None,
        mot_off_window: Optional[tuple[float, float]] = None,
        img_window: Optional[tuple[float, float]] = None,
    ) -> dict:
        """
        Calculate normalized fluorescence with scaling.

        Normalization follows the formula:
        F_norm = (F(t) - F_low) / (F_high - F_low) for t in imaging window

        where:
            F_high = fluorescence when MOT is on (before drop, in mot_on_window)
            F_low = fluorescence when MOT is off (after sequence, in mot_off_window)

        Args:
            averaged_df: Aligned and averaged DataFrame
            mot_on_window: (t_start, t_end) for MOT on (high fluorescence) - uses config if None
            mot_off_window: (t_start, t_end) for MOT off (low fluorescence) - uses config if None
            img_window: (t_start, t_end) for imaging pulse region - uses config if None

        Returns:
            Dictionary with normalization metrics
        """
        # Use configuration values as defaults
        mot_on_window = mot_on_window or MOT_ON_WINDOW
        mot_off_window = mot_off_window or MOT_OFF_WINDOW
        img_window = img_window or IMAGING_WINDOW

        time_data = averaged_df[self.time_col].values
        fluor_data = averaged_df[self.fluorescence_col].values

        # Extract high fluorescence (MOT on)
        on_mask = (time_data >= mot_on_window[0]) & (time_data <= mot_on_window[1])
        on_values = fluor_data[on_mask]
        F_high = np.mean(on_values)
        F_high_std = np.std(on_values)

        print(
            f"F_high (MOT on) = {F_high:.4f} V (std: {F_high_std:.4f} V) from {len(on_values)} points"
        )

        # Extract low fluorescence (MOT off)
        off_mask = (time_data >= mot_off_window[0]) & (time_data <= mot_off_window[1])
        off_values = fluor_data[off_mask]
        F_low = np.mean(off_values)
        F_low_std = np.std(off_values)
        print(
            f"F_low (MOT off) = {F_low:.4f} V (std: {F_low_std:.4f} V) from {len(off_values)} points"
        )

        # Extract imaging region
        img_mask = (time_data >= img_window[0]) & (time_data <= img_window[1])
        img_values = fluor_data[img_mask]
        img_times = time_data[img_mask]

        if len(img_values) == 0:
            raise ValueError(f"No data in imaging window {img_window}")

        # Calculate normalization scale
        scale_factor = F_high - F_low
        if abs(scale_factor) < 1e-6:
            warnings.warn("Scale factor is very small, normalization may be unreliable")
        if scale_factor <= 0:
            raise ValueError(
                f"Invalid scale factor: F_high ({F_high}) must be greater than F_low ({F_low})"
            )

        print(f"Scale factor (F_high - F_low) = {scale_factor:.4f} V")
        img_avg = np.mean(img_values)
        print(f"Average fluorescence in imaging window = {img_avg:.4f} V")
        # Normalize fluorescence: (F(t) - F_low) / (F_high - F_low)
        normalized_values = (img_values - F_low) / scale_factor

        # Calculate metrics
        F_normalized = np.mean(normalized_values)
        F_normalized_std = np.std(normalized_values)
        print(
            f"F_normalized (imaging window) = {F_normalized:.4f} (std: {F_normalized_std:.4f}) from {len(normalized_values)} points"
        )

        # Propagate uncertainty
        # For F_norm = (F - F_low) / (F_high - F_low)
        # Uncertainty ≈ F_norm * sqrt((std_F/F)^2 + (std_high/F_high)^2 + (std_low/F_low)^2)
        if abs(F_high) > 1e-6 and abs(F_low) > 1e-6:
            rel_unc = np.sqrt((F_high_std / F_high) ** 2 + (F_low_std / F_low) ** 2)
            F_normalized_unc = abs(F_normalized * rel_unc)
        else:
            F_normalized_unc = F_normalized_std / np.sqrt(max(len(normalized_values), 1))

        # Also calculate raw integral for reference
        raw_integral = np.trapz(img_values, img_times)
        normalized_integral = np.trapz(normalized_values, img_times)

        return {
            "F_high": F_high,
            "F_high_std": F_high_std,
            "F_low": F_low,
            "F_low_std": F_low_std,
            "scale_factor": scale_factor,
            "F_normalized": F_normalized,
            "F_normalized_std": F_normalized_std,
            "F_normalized_uncertainty": F_normalized_unc,
            "raw_integral": raw_integral,
            "normalized_integral": normalized_integral,
            "num_imaging_points": len(img_values),
            "imaging_duration": img_window[1] - img_window[0],
        }

    def process_single_shot(
        self,
        shot_folder: Path,
        fluor_drop_voltage: Optional[float] = None,
        background_window: Optional[tuple[float, float]] = None,
        final_window: Optional[tuple[float, float]] = None,
        img_window: Optional[tuple[float, float]] = None,
        _cache_key: Optional[str] = None,
    ) -> dict:
        """
        Process a single shot folder.

        Args:
            shot_folder: Path to shot folder
            fluor_drop_voltage: Voltage threshold for MOT drop (uses config if None)
            background_window: Time window for background/MOT on (uses config if None)
            final_window: Time window for final/MOT off (uses config if None)
            img_window: Time window for imaging pulse (uses config if None)
            _cache_key: Internal key for aligned data cache (uses shot_folder.name if None)

        Returns:
            Dictionary with processing results
        """
        # Use configuration values as defaults
        fluor_drop_voltage = fluor_drop_voltage or FLUOR_DROP_VOLTAGE
        background_window = background_window or MOT_ON_WINDOW
        final_window = final_window or MOT_OFF_WINDOW
        img_window = img_window or IMAGING_WINDOW

        # Load CSV files
        dataframes = self.load_csv_files(shot_folder)

        # Align and average
        averaged_df, drop_times = self.align_and_average(
            dataframes,
            fluor_drop_voltage,
            TIME_BEFORE_DROP,
            TIME_AFTER_DROP,
            NUM_INTERPOLATION_POINTS,
        )

        # Calculate normalized fluorescence
        metrics = self.calculate_normalized_fluorescence(
            averaged_df, background_window, final_window, img_window
        )

        # Extract shot information
        shot_name = shot_folder.name
        shot_match = re.search(r"shot(\d+)", shot_name, re.IGNORECASE)
        shot_number = int(shot_match.group(1)) if shot_match else None

        # Extract parameter from parent folder if possible
        param_folder = shot_folder.parent.name

        result = {
            "shot_name": shot_name,
            "shot_number": shot_number,
            "parameter_folder": param_folder,
            "num_traces": len(dataframes),
            "num_valid_traces": len(drop_times),
            "mean_drop_time": np.mean(drop_times),
            "std_drop_time": np.std(drop_times),
            "shot_path": str(shot_folder),
            **metrics,
        }

        # Store averaged data for plotting using unique cache key
        key = _cache_key if _cache_key is not None else shot_name
        self.aligned_data_cache[key] = averaged_df

        return result

    def process_all_experiments(
        self,
        fluor_drop_voltage: Optional[float] = None,
        background_window: Optional[tuple[float, float]] = None,
        final_window: Optional[tuple[float, float]] = None,
        img_window: Optional[tuple[float, float]] = None,
        save_summary: bool = True,
    ) -> pd.DataFrame:
        """
        Process all experiments in the root folder using configuration parameters.

        Args:
            fluor_drop_voltage: Voltage threshold for MOT drop (uses config if None)
            background_window: Time window for background/MOT on (uses config if None)
            final_window: Time window for final/MOT off (uses config if None)
            img_window: Time window for imaging pulse (uses config if None)
            save_summary: Whether to save summary CSV

        Returns:
            DataFrame with summary results
        """
        # Use configuration values as defaults
        fluor_drop_voltage = fluor_drop_voltage or FLUOR_DROP_VOLTAGE
        background_window = background_window or MOT_ON_WINDOW
        final_window = final_window or MOT_OFF_WINDOW
        img_window = img_window or IMAGING_WINDOW
        self.results = []
        self.aligned_data_cache = {}

        # Collect unique shot folders, avoiding duplicates from rglob
        seen_folders = set()
        shot_folders = []
        for path in sorted(self.root_folder.rglob("shot*")):
            if not path.is_dir():
                continue
            resolved = path.resolve()
            if resolved in seen_folders:
                continue
            seen_folders.add(resolved)
            shot_folders.append(path)

        # Process shot folders
        for path in shot_folders:
            # Use relative path from root as unique key to avoid name collisions
            try:
                rel_path = path.relative_to(self.root_folder)
            except ValueError:
                rel_path = path
            cache_key = str(rel_path)

            try:
                print(f"Processing {cache_key}...", end=" ")
                result = self.process_single_shot(
                    path,
                    fluor_drop_voltage,
                    background_window,
                    final_window,
                    img_window,
                    _cache_key=cache_key,
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

        # Sort by parameter folder then shot number if available
        sort_cols = []
        if "parameter_folder" in summary_df.columns:
            sort_cols.append("parameter_folder")
        if "shot_number" in summary_df.columns:
            sort_cols.append("shot_number")
        if sort_cols:
            summary_df = summary_df.sort_values(sort_cols).reset_index(drop=True)

        # Save summary
        if save_summary:
            summary_path = self.root_folder / "fluorescence_analysis_summary.csv"
            summary_df.to_csv(summary_path, index=False)
            print(f"\nSummary saved to {summary_path}")

            # Also save a human-readable text version
            txt_path = self.root_folder / "fluorescence_analysis_summary.txt"
            with open(txt_path, "w") as f:
                f.write("=" * 100 + "\n")
                f.write("FLUORESCENCE ANALYSIS SUMMARY\n")
                f.write("=" * 100 + "\n\n")
                f.write(
                    summary_df[
                        [
                            "parameter_folder",
                            "shot_name",
                            "num_valid_traces",
                            "F_normalized",
                            "F_normalized_uncertainty",
                            "raw_integral",
                            "F_high",
                            "F_low",
                            "scale_factor",
                        ]
                    ].to_string()
                )
                f.write("\n")
            print(f"Summary text saved to {txt_path}")

        return summary_df

    def _save_figure(self, fig, name: str):
        """Save figure as PNG and as a pickle file for interactive re-opening.

        The pickle (.fig.pkl) can be reloaded and zoomed interactively via:
            import pickle, matplotlib.pyplot as plt
            fig = pickle.load(open('file.fig.pkl', 'rb'))
            plt.show()
        """
        save_dir = self.root_folder
        png_path = save_dir / f"{name}.png"
        svg_path = save_dir / f"{name}.svg"
        pkl_path = save_dir / f"{name}.fig.pkl"

        fig.savefig(png_path, dpi=200, bbox_inches="tight")
        fig.savefig(svg_path, bbox_inches="tight")
        with open(pkl_path, "wb") as f:
            pickle.dump(fig, f)

        print(f"  Saved: {png_path.name}, {svg_path.name}, {pkl_path.name}")

    def plot_results(self, figsize: tuple[int, int] = (14, 10), save: bool = True):
        """
        Plot processed results with multiple subplots.

        Args:
            figsize: Figure size (width, height)
            save: Whether to save the figure to disk
        """
        if not self.results:
            raise ValueError("No results to plot. Run process_all_experiments first.")

        summary_df = pd.DataFrame(self.results)

        # Sort by parameter folder then shot number if available
        sort_cols = []
        if "parameter_folder" in summary_df.columns:
            sort_cols.append("parameter_folder")
        if "shot_number" in summary_df.columns:
            sort_cols.append("shot_number")
        if sort_cols:
            summary_df = summary_df.sort_values(sort_cols).reset_index(drop=True)

        # Build composite labels for per-shot plots: "folder / shotN"
        shot_labels = [
            f"{row['parameter_folder']}/s{row['shot_number']}"
            if "parameter_folder" in row and "shot_number" in row
            else str(i)
            for i, row in summary_df.iterrows()
        ]

        fig, axes = plt.subplots(2, 2, figsize=figsize)

        # Plot 1: Normalized fluorescence vs shot, one line per parameter folder
        ax = axes[0, 0]
        if "parameter_folder" in summary_df.columns:
            groups = summary_df.groupby("parameter_folder")
            colors = plt.cm.tab10(np.linspace(0, 1, max(len(groups), 1)))
            for (pf, group), color in zip(groups, colors):
                x = group["shot_number"] if "shot_number" in group.columns else range(len(group))
                ax.errorbar(
                    x,
                    group["F_normalized"],
                    yerr=group["F_normalized_uncertainty"],
                    fmt="o-",
                    capsize=4,
                    color=color,
                    label=pf,
                )
        else:
            x_data = (
                summary_df["shot_number"]
                if "shot_number" in summary_df.columns
                else range(len(summary_df))
            )
            ax.errorbar(
                x_data,
                summary_df["F_normalized"],
                yerr=summary_df["F_normalized_uncertainty"],
                fmt="o-",
                capsize=5,
                label="Normalized Fluorescence",
            )
        ax.set_xlabel("Shot Number")
        ax.set_ylabel("Normalized Fluorescence")
        ax.set_title("Normalized Fluorescence per Shot")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize="x-small")

        # Plot 2: Raw integral vs shot, one line per parameter folder
        ax = axes[0, 1]
        if "parameter_folder" in summary_df.columns:
            groups = summary_df.groupby("parameter_folder")
            colors = plt.cm.tab10(np.linspace(0, 1, max(len(groups), 1)))
            for (pf, group), color in zip(groups, colors):
                x = group["shot_number"] if "shot_number" in group.columns else range(len(group))
                ax.plot(x, group["raw_integral"], "o-", color=color, label=pf)
        else:
            x_data = (
                summary_df["shot_number"]
                if "shot_number" in summary_df.columns
                else range(len(summary_df))
            )
            ax.plot(x_data, summary_df["raw_integral"], "o-", label="Raw Integral")
        ax.set_xlabel("Shot Number")
        ax.set_ylabel("Raw Integral (V·s)")
        ax.set_title("Raw Fluorescence Integral")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize="x-small")

        # Plot 3: Normalization factors – all shots sequential with composite labels
        ax = axes[1, 0]
        x_all = np.arange(len(summary_df))
        ax.plot(x_all, summary_df["F_high"], "o-", label="F_high (MOT on)", alpha=0.7)
        ax.plot(x_all, summary_df["F_low"], "s-", label="F_low (MOT off)", alpha=0.7)
        ax.fill_between(
            x_all,
            summary_df["F_high"] - summary_df["F_high_std"],
            summary_df["F_high"] + summary_df["F_high_std"],
            alpha=0.2,
        )
        ax.fill_between(
            x_all,
            summary_df["F_low"] - summary_df["F_low_std"],
            summary_df["F_low"] + summary_df["F_low_std"],
            alpha=0.2,
        )
        ax.set_xticks(x_all)
        ax.set_xticklabels(shot_labels, rotation=90, fontsize=6)
        ax.set_xlabel("Parameter Folder / Shot")
        ax.set_ylabel("Fluorescence (V)")
        ax.set_title("Normalization Reference Values")
        ax.grid(True, alpha=0.3)
        ax.legend()

        # Plot 4: Number of valid traces – all shots sequential with composite labels
        ax = axes[1, 1]
        ax.bar(x_all, summary_df["num_valid_traces"], alpha=0.7, label="Valid Traces")
        ax.bar(
            x_all,
            summary_df["num_traces"] - summary_df["num_valid_traces"],
            bottom=summary_df["num_valid_traces"],
            alpha=0.3,
            label="Invalid Traces",
        )
        ax.set_xticks(x_all)
        ax.set_xticklabels(shot_labels, rotation=90, fontsize=6)
        ax.set_xlabel("Parameter Folder / Shot")
        ax.set_ylabel("Number of Traces")
        ax.set_title("Trace Validity per Shot")
        ax.legend()

        fig.tight_layout()
        if save:
            self._save_figure(fig, "fluorescence_results")
        plt.show()

    def plot_averaged_traces(
        self,
        # shots: Optional[List[str]] = None,
        figsize: tuple[int, int] = (14, 6),
        save: bool = True,
    ):
        """
        Plot aligned and averaged traces for selected shots.

        Args:
            shots: List of shot cache keys to plot (None = all)
            figsize: Figure size
            save: Whether to save the figure to disk
        """
        if not self.aligned_data_cache:
            raise ValueError("No aligned data cached. Run process_all_experiments first.")

        if shots is None:
            shots = list(self.aligned_data_cache.keys())

        shots = [s for s in shots if s in self.aligned_data_cache]

        fig, axes = plt.subplots(1, 2, figsize=figsize)

        colors = plt.cm.viridis(np.linspace(0, 1, max(len(shots), 1)))

        # Plot fluorescence channel
        ax = axes[0]
        for shot_name, color in zip(shots, colors):
            df = self.aligned_data_cache[shot_name]
            if self.fluorescence_col in df.columns:
                ax.plot(
                    df[self.time_col] * 1e3,
                    df[self.fluorescence_col],
                    label=shot_name,
                    color=color,
                    linewidth=2,
                )
        ax.set_xlabel("Time relative to MOT drop (ms)")
        ax.set_ylabel(f"{self.fluorescence_col} (V)")
        ax.set_title("Aligned Fluorescence Traces")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize="x-small")

        # Plot all channels for first shot
        ax = axes[1]
        shot_name = shots[0]
        df = self.aligned_data_cache[shot_name]
        for col_name in self.channel_cols.values():
            if col_name in df.columns:
                ax.plot(df[self.time_col] * 1e3, df[col_name], label=col_name, linewidth=1.5)
        ax.set_xlabel("Time relative to MOT drop (ms)")
        ax.set_ylabel("Voltage (V)")
        ax.set_title(f"All Channels - {shot_name}")
        ax.grid(True, alpha=0.3)
        ax.legend()

        fig.tight_layout()
        if save:
            self._save_figure(fig, "fluorescence_averaged_traces")
        plt.show()


def example_usage():
    """Example usage of the UnifiedFluorescenceProcessor."""

    while True:
        user_input = input("Enter the root folder path or 'exit' to quit: ")
        if user_input.lower() in ["exit", "x", "e"]:
            break

        else:
            root_folder = user_input.strip()

        # Initialize processor
        processor = UnifiedFluorescenceProcessor(root_folder)

        # Process all experiments using configuration parameters defined at the top of the file
        # Override any parameters if needed (optional - uses config defaults if not provided)
        summary_df = processor.process_all_experiments(save_summary=True)

        # Display summary
        print("\n" + "=" * 80)
        print("ANALYSIS SUMMARY")
        print("=" * 80)
        print(
            summary_df[
                [
                    "parameter_folder",
                    "shot_name",
                    "num_valid_traces",
                    "F_normalized",
                    "F_normalized_uncertainty",
                    "raw_integral",
                ]
            ].to_string()
        )

        # Plot results
        processor.plot_results()
        processor.plot_averaged_traces()


if __name__ == "__main__":
    example_usage()
