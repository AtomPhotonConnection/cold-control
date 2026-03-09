"""
Unified Fluorescence Analysis Pipeline

This script provides a complete pipeline for analysing fluorescence data from oscilloscope
CSV files. It is split into two clear stages:

STAGE 1 — DATA EXTRACTION (UnifiedFluorescenceProcessor)
    Loads CSV files from shot folders, aligns traces based on MOT drop timing,
    averages them, and extracts raw fluorescence values (mean ± SEM) from
    configurable time windows. Also handles background data extraction.

STAGE 2 — DATA ANALYSIS (FluorescenceAnalyser)
    Performs background subtraction and calculates normalised fluorescence using
    the formulas from data_analysis.md:

        F_max = F_max_act - F_max_bg                                  (eq. 1)
        F_img = F_img_act - F_img_bg                                  (eq. 2)
        F_norm = F_img / F_max                                        (eq. 3)

    With uncertainty propagation:
        σ_F_max = sqrt(σ_F_max_act² + σ_F_max_bg²)                   (eq. 4)
        σ_F_img = sqrt(σ_F_img_act² + σ_F_img_bg²)                   (eq. 5)
        σ_F_norm = F_norm * sqrt((σ_F_img/F_img)² + (σ_F_max/F_max)²) (eq. 7)

    All individual uncertainties are the standard error of the mean (σ/√n).
"""

from __future__ import annotations

import pickle
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import interpolate

# ============================================================================
# MARK:CONFIG PARAMETERS
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
# STAGE 1: MARK:DATA EXTRACTION
# ============================================================================


class UnifiedFluorescenceProcessor:
    """
    Loads, aligns, and averages oscilloscope fluorescence traces, then extracts
    raw fluorescence values from configurable time windows.

    This class handles data *extraction* only — it does not perform background
    subtraction or normalisation. For the physics analysis, pass the extracted
    values to :class:`FluorescenceAnalyser`.
    """

    def __init__(self, root_folder: str):
        """
        Initialise the processor.

        Args:
            root_folder: Root directory containing shot folders.
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
        self.results: list[dict] = []
        self.aligned_data_cache: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------

    def load_csv_files(self, shot_folder: Path) -> list[pd.DataFrame]:
        """
        Load all ``iteration_*_data.csv`` files from a shot folder.

        Args:
            shot_folder: Path to shot folder.

        Returns:
            List of DataFrames from CSV files.
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
                warnings.warn(f"Could not load {csv_file}: {e}", stacklevel=2)

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

    # ------------------------------------------------------------------
    # Alignment and averaging
    # ------------------------------------------------------------------

    def align_and_average(
        self,
        dataframes: list[pd.DataFrame],
        fluor_drop_voltage: float | None = None,
        time_before_drop: float | None = None,
        time_after_drop: float | None = None,
        num_points: int | None = None,
    ) -> tuple[pd.DataFrame, list[float]]:
        """
        Align multiple traces based on fluorescence drop timing and average them.

        Args:
            dataframes: List of DataFrames to align.
            fluor_drop_voltage: Voltage threshold for MOT drop detection (uses config if None).
            time_before_drop: Time window before drop to include (uses config if None).
            time_after_drop: Time window after drop to include (uses config if None).
            num_points: Number of points in interpolated traces (uses config if None).

        Returns:
            Tuple of (averaged_dataframe, list_of_drop_times).
        """
        fluor_drop_voltage = fluor_drop_voltage or FLUOR_DROP_VOLTAGE
        time_before_drop = time_before_drop or TIME_BEFORE_DROP
        time_after_drop = time_after_drop or TIME_AFTER_DROP
        num_points = num_points or NUM_INTERPOLATION_POINTS

        valid_dfs = []
        drop_times: list[float] = []

        for df in dataframes:
            fluor_data = df[self.fluorescence_col].to_numpy()
            time_data = df[self.time_col].to_numpy()

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

        aligned_time = np.linspace(max_start, min_end, num_points)

        available_channels = [
            col_name for col_name in self.channel_cols.values() if col_name in valid_dfs[0].columns
        ]

        interpolated_data: dict[str, list] = {col_name: [] for col_name in available_channels}

        for df, drop_time in zip(valid_dfs, drop_times):
            relative_time = df[self.time_col].values - drop_time

            for col_name in available_channels:
                channel_data = df[col_name].values
                f_interp = interpolate.interp1d(
                    relative_time,
                    channel_data,
                    kind="linear",
                    bounds_error=False,
                    fill_value=np.nan,
                )
                interp_channel = f_interp(aligned_time)
                interpolated_data[col_name].append(interp_channel)

        averaged_data: dict[str, np.ndarray] = {self.time_col: aligned_time}
        for col_name in available_channels:
            if interpolated_data[col_name]:
                channel_stack = np.array(interpolated_data[col_name])
                if np.all(np.isnan(channel_stack)):
                    warnings.warn(
                        f"Channel {col_name} is all NaN after interpolation, skipping.",
                        stacklevel=2,
                    )
                else:
                    averaged_data[col_name] = np.nanmean(channel_stack, axis=0)

        averaged_df = pd.DataFrame(averaged_data)
        return averaged_df, drop_times

    # ------------------------------------------------------------------
    # Fluorescence value extraction
    # ------------------------------------------------------------------

    def extract_fluorescence_values(
        self,
        averaged_df: pd.DataFrame,
        mot_on_window: tuple[float, float] | None = None,
        img_window: tuple[float, float] | None = None,
    ) -> dict:
        """
        Extract raw fluorescence values and standard errors from an averaged trace.

        This method performs **data extraction only** — no normalisation or
        background subtraction.  It returns the mean fluorescence and its
        standard error of the mean (SEM = σ/√n) for two time windows:

        * ``F_max`` — the fluorescence during the MOT-on window (before drop).
        * ``F_img`` — the fluorescence during the imaging pulse window.

        These values are intended to be passed to :class:`FluorescenceAnalyser`
        for background subtraction and normalisation.

        Args:
            averaged_df: Aligned and averaged DataFrame.
            mot_on_window: (t_start, t_end) for MOT on region — uses ``MOT_ON_WINDOW`` if None.
            img_window: (t_start, t_end) for imaging pulse region — uses ``IMAGING_WINDOW`` if None.

        Returns:
            Dictionary with keys:
                ``F_max``, ``F_max_sem``, ``F_max_n``,
                ``F_img``, ``F_img_sem``, ``F_img_n``.
        """
        mot_on_window = mot_on_window or MOT_ON_WINDOW
        img_window = img_window or IMAGING_WINDOW

        time_data = averaged_df[self.time_col].to_numpy()
        fluor_data = averaged_df[self.fluorescence_col].to_numpy()

        # --- F_max: MOT on (high fluorescence, before drop) ---
        on_mask = (time_data >= mot_on_window[0]) & (time_data <= mot_on_window[1])
        on_values = fluor_data[on_mask]
        if len(on_values) == 0:
            raise ValueError(f"No data in MOT-on window {mot_on_window}")
        f_max = float(np.mean(on_values))
        f_max_sem = float(np.std(on_values, ddof=1) / np.sqrt(len(on_values)))

        print(f"  F_max (MOT on) = {f_max:.6f} V  (SEM: {f_max_sem:.6f} V, n={len(on_values)})")

        # --- F_img: imaging pulse window ---
        img_mask = (time_data >= img_window[0]) & (time_data <= img_window[1])
        img_values = fluor_data[img_mask]
        if len(img_values) == 0:
            raise ValueError(f"No data in imaging window {img_window}")
        f_img = float(np.mean(img_values))
        f_img_sem = float(np.std(img_values, ddof=1) / np.sqrt(len(img_values)))

        print(f"  F_img (imaging) = {f_img:.6f} V  (SEM: {f_img_sem:.6f} V, n={len(img_values)})")

        return {
            "F_max": f_max,
            "F_max_sem": f_max_sem,
            "F_max_n": len(on_values),
            "F_img": f_img,
            "F_img_sem": f_img_sem,
            "F_img_n": len(img_values),
        }

    # ------------------------------------------------------------------
    # Single-shot processing
    # ------------------------------------------------------------------

    def process_single_shot(
        self,
        shot_folder: Path,
        fluor_drop_voltage: float | None = None,
        mot_on_window: tuple[float, float] | None = None,
        img_window: tuple[float, float] | None = None,
        _cache_key: str | None = None,
    ) -> dict:
        """
        Process a single shot folder: load, align, average, and extract values.

        Args:
            shot_folder: Path to shot folder.
            fluor_drop_voltage: Voltage threshold for MOT drop (uses config if None).
            mot_on_window: Time window for MOT on / F_max (uses config if None).
            img_window: Time window for imaging pulse (uses config if None).
            _cache_key: Internal key for aligned data cache (uses shot_folder.name if None).

        Returns:
            Dictionary with extracted fluorescence values and metadata.
        """
        fluor_drop_voltage = fluor_drop_voltage or FLUOR_DROP_VOLTAGE
        mot_on_window = mot_on_window or MOT_ON_WINDOW
        img_window = img_window or IMAGING_WINDOW

        dataframes = self.load_csv_files(shot_folder)

        averaged_df, drop_times = self.align_and_average(
            dataframes,
            fluor_drop_voltage,
            TIME_BEFORE_DROP,
            TIME_AFTER_DROP,
            NUM_INTERPOLATION_POINTS,
        )

        extracted = self.extract_fluorescence_values(averaged_df, mot_on_window, img_window)

        shot_name = shot_folder.name
        shot_match = re.search(r"shot(\d+)", shot_name, re.IGNORECASE)
        shot_number = int(shot_match.group(1)) if shot_match else None
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
            **extracted,
        }

        key = _cache_key if _cache_key is not None else shot_name
        self.aligned_data_cache[key] = averaged_df

        return result

    # ------------------------------------------------------------------
    # Batch processing (all shots)
    # ------------------------------------------------------------------

    def process_all_experiments(
        self,
        fluor_drop_voltage: float | None = None,
        mot_on_window: tuple[float, float] | None = None,
        img_window: tuple[float, float] | None = None,
        save_summary: bool = True,
    ) -> pd.DataFrame:
        """
        Process all shot folders under ``root_folder``.

        Returns a DataFrame with one row per shot containing the extracted
        fluorescence values (F_max, F_img and their SEMs).  No normalisation
        is performed here — use :class:`FluorescenceAnalyser` for that.

        Args:
            fluor_drop_voltage: Voltage threshold for MOT drop (uses config if None).
            mot_on_window: Time window for MOT on / F_max (uses config if None).
            img_window: Time window for imaging pulse (uses config if None).
            save_summary: Whether to save summary CSV.

        Returns:
            DataFrame with extracted fluorescence values per shot.
        """
        fluor_drop_voltage = fluor_drop_voltage or FLUOR_DROP_VOLTAGE
        mot_on_window = mot_on_window or MOT_ON_WINDOW
        img_window = img_window or IMAGING_WINDOW
        self.results = []
        self.aligned_data_cache = {}

        seen_folders: set[Path] = set()
        shot_folders: list[Path] = []
        for path in sorted(self.root_folder.rglob("shot*")):
            if not path.is_dir():
                continue
            resolved = path.resolve()
            if resolved in seen_folders:
                continue
            seen_folders.add(resolved)
            shot_folders.append(path)

        for path in shot_folders:
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
                    mot_on_window,
                    img_window,
                    _cache_key=cache_key,
                )
                self.results.append(result)
                print("✓")
            except Exception as e:
                print(f"✗ ({e})")
                continue

        if not self.results:
            raise ValueError("No shots were successfully processed")

        summary_df = pd.DataFrame(self.results)

        sort_cols = []
        if "parameter_folder" in summary_df.columns:
            sort_cols.append("parameter_folder")
        if "shot_number" in summary_df.columns:
            sort_cols.append("shot_number")
        if sort_cols:
            summary_df = summary_df.sort_values(sort_cols).reset_index(drop=True)

        if save_summary:
            summary_path = self.root_folder / "fluorescence_extraction_summary.csv"
            summary_df.to_csv(summary_path, index=False)
            print(f"\nExtraction summary saved to {summary_path}")

        return summary_df

    # ------------------------------------------------------------------
    # Background data processing
    # ------------------------------------------------------------------

    def process_background(
        self,
        background_folder: str | Path,
        fluor_drop_voltage: float | None = None,
        mot_on_window: tuple[float, float] | None = None,
        img_window: tuple[float, float] | None = None,
    ) -> dict:
        """
        Process background data (acquired with MOT repumping off).

        Loads all shot folders from ``background_folder``, extracts F_max and
        F_img from each, and returns the **averaged** background values with
        standard errors of the mean.

        If only a single shot folder exists (or ``background_folder`` itself
        contains CSV files), it processes that directly. If multiple shot
        folders are found, the per-shot means are averaged and the SEM is
        computed across shots.

        Args:
            background_folder: Path to background data directory.
            fluor_drop_voltage: Voltage threshold for MOT drop (uses config if None).
            mot_on_window: Time window for F_max_bg extraction (uses config if None).
            img_window: Time window for F_img_bg extraction (uses config if None).

        Returns:
            Dictionary with keys:
                ``F_max_bg``, ``F_max_bg_sem``,
                ``F_img_bg``, ``F_img_bg_sem``,
                ``n_background_shots``.
        """
        background_folder = Path(background_folder)
        fluor_drop_voltage = fluor_drop_voltage or FLUOR_DROP_VOLTAGE
        mot_on_window = mot_on_window or MOT_ON_WINDOW
        img_window = img_window or IMAGING_WINDOW

        print(f"\n{'=' * 60}")
        print(f"Processing BACKGROUND data from: {background_folder}")
        print(f"{'=' * 60}")

        # Find shot folders within the background directory
        shot_folders = sorted(p for p in background_folder.rglob("shot*") if p.is_dir())

        # If no shot* subfolders, treat background_folder itself as a shot folder
        if not shot_folders:
            csv_pattern = re.compile(r"^iteration_\d+_data\.csv$", re.IGNORECASE)
            has_csvs = any(csv_pattern.match(f.name) for f in background_folder.glob("*.csv"))
            if has_csvs:
                shot_folders = [background_folder]
            else:
                raise ValueError(
                    f"No shot folders or CSV files found in background directory: "
                    f"{background_folder}"
                )

        f_max_values: list[float] = []
        f_img_values: list[float] = []

        for shot_folder in shot_folders:
            print(f"\n  Background shot: {shot_folder.name}")
            try:
                dataframes = self.load_csv_files(shot_folder)
                averaged_df, _ = self.align_and_average(
                    dataframes,
                    fluor_drop_voltage,
                    TIME_BEFORE_DROP,
                    TIME_AFTER_DROP,
                    NUM_INTERPOLATION_POINTS,
                )
                extracted = self.extract_fluorescence_values(averaged_df, mot_on_window, img_window)
                f_max_values.append(extracted["F_max"])
                f_img_values.append(extracted["F_img"])
            except Exception as e:
                print(f"    ✗ Failed: {e}")
                continue

        if not f_max_values:
            raise ValueError("No background shots were successfully processed")

        f_max_arr = np.array(f_max_values)
        f_img_arr = np.array(f_img_values)
        n = len(f_max_arr)

        # If only one shot, SEM comes from the within-shot extraction
        # (already σ/√n of the time-series points).
        # If multiple shots, compute SEM across shots.
        if n == 1:
            # Re-extract to get the SEM from the single shot
            dataframes = self.load_csv_files(shot_folders[0])
            averaged_df, _ = self.align_and_average(
                dataframes,
                fluor_drop_voltage,
                TIME_BEFORE_DROP,
                TIME_AFTER_DROP,
                NUM_INTERPOLATION_POINTS,
            )
            single = self.extract_fluorescence_values(averaged_df, mot_on_window, img_window)
            f_max_bg_sem = single["F_max_sem"]
            f_img_bg_sem = single["F_img_sem"]
        else:
            f_max_bg_sem = float(np.std(f_max_arr, ddof=1) / np.sqrt(n))
            f_img_bg_sem = float(np.std(f_img_arr, ddof=1) / np.sqrt(n))

        result = {
            "F_max_bg": float(np.mean(f_max_arr)),
            "F_max_bg_sem": f_max_bg_sem,
            "F_img_bg": float(np.mean(f_img_arr)),
            "F_img_bg_sem": f_img_bg_sem,
            "n_background_shots": n,
        }

        print(f"\n  Background summary:")
        print(f"    F_max_bg = {result['F_max_bg']:.6f} ± {result['F_max_bg_sem']:.6f} V")
        print(f"    F_img_bg = {result['F_img_bg']:.6f} ± {result['F_img_bg_sem']:.6f} V")
        print(f"    n_background_shots = {n}")

        return result

    # ------------------------------------------------------------------
    # Plotting helpers (trace-level)
    # ------------------------------------------------------------------

    def _save_figure(self, fig, name: str):
        """Save figure as PNG and as a pickle file for interactive re-opening."""
        save_dir = self.root_folder
        png_path = save_dir / f"{name}.png"
        svg_path = save_dir / f"{name}.svg"
        pkl_path = save_dir / f"{name}.fig.pkl"

        fig.savefig(png_path, dpi=200, bbox_inches="tight")
        fig.savefig(svg_path, bbox_inches="tight")
        with pkl_path.open("wb") as f:
            pickle.dump(fig, f)

        print(f"  Saved: {png_path.name}, {svg_path.name}, {pkl_path.name}")

    def plot_averaged_traces(
        self,
        shots: list[str] | None = None,
        figsize: tuple[int, int] = (14, 6),
        save: bool = True,
    ):
        """
        Plot aligned and averaged traces for selected shots.

        Args:
            shots: List of shot cache keys to plot (None = all).
            figsize: Figure size.
            save: Whether to save the figure to disk.
        """
        if not self.aligned_data_cache:
            raise ValueError("No aligned data cached. Run process_all_experiments first.")

        if shots is None:
            shots = list(self.aligned_data_cache.keys())

        shots = [s for s in shots if s in self.aligned_data_cache]

        fig, axes = plt.subplots(1, 2, figsize=figsize)

        virid_cmap = mpl.colormaps["viridis"]
        colors = virid_cmap(np.linspace(0, 1, max(len(shots), 1)))

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


# ============================================================================
# STAGE 2: MARK:DATA ANALYSIS
# ============================================================================
#
# The analysis is implemented here as a separate class so that:
#   1. It is easy to find and review the physics calculations.
#   2. It can be tested independently of the data extraction.
#   3. The formulas can be modified without touching the extraction code.
#
# Equations from data_analysis.md:
#
#   F_max = F_max_act - F_max_bg                                    (eq. 1)
#   F_img = F_img_act - F_img_bg                                    (eq. 2)
#   F_norm = F_img / F_max                                          (eq. 3)
#
#   σ_F_max = sqrt(σ_F_max_act² + σ_F_max_bg²)                     (eq. 4)
#   σ_F_img = sqrt(σ_F_img_act² + σ_F_img_bg²)                     (eq. 5)
#   σ_F_norm = F_norm * sqrt((σ_F_img/F_img)² + (σ_F_max/F_max)²)  (eq. 7)
#
# All individual uncertainties (σ_F_max_act, σ_F_max_bg, etc.) are the
# standard error of the mean: σ / √n.
# ============================================================================


@dataclass
class AnalysisResult:
    """Result of the fluorescence analysis for a single sweep point."""

    # Background-subtracted values
    F_max: float  # F_max_act - F_max_bg                     (eq. 1)
    F_max_uncertainty: float  # σ_F_max                      (eq. 4)
    F_img: float  # F_img_act - F_img_bg                     (eq. 2)
    F_img_uncertainty: float  # σ_F_img                      (eq. 5)

    # Normalised fluorescence
    F_norm: float  # F_img / F_max                           (eq. 3)
    F_norm_uncertainty: float  # σ_F_norm                    (eq. 7)

    # Input values (for diagnostics)
    F_max_act: float = 0.0
    F_max_act_sem: float = 0.0
    F_img_act: float = 0.0
    F_img_act_sem: float = 0.0
    F_max_bg: float = 0.0
    F_max_bg_sem: float = 0.0
    F_img_bg: float = 0.0
    F_img_bg_sem: float = 0.0

    # Metadata carried through from extraction
    shot_name: str = ""
    shot_number: int | None = None
    parameter_folder: str = ""


class FluorescenceAnalyser:
    """
    Performs background subtraction and normalisation on extracted fluorescence
    data using the formulas from data_analysis.md.

    This class is pure computation — no file I/O or plotting. It takes the raw
    extracted values from :class:`UnifiedFluorescenceProcessor` and background
    data, and produces normalised fluorescence with full uncertainty propagation.

    Usage::

        analyser = FluorescenceAnalyser(background_data)
        results = analyser.analyse(signal_df)
        # results is a list of AnalysisResult, one per sweep point

    The analysis formulas are implemented in :meth:`analyse_single_point` so
    they can be reviewed and modified in one place.
    """

    def __init__(self, background_data: dict):
        """
        Initialise with background measurement data.

        Args:
            background_data: Dictionary from
                ``UnifiedFluorescenceProcessor.process_background()`` containing
                ``F_max_bg``, ``F_max_bg_sem``, ``F_img_bg``, ``F_img_bg_sem``.
        """
        self.F_max_bg: float = background_data["F_max_bg"]
        self.F_max_bg_sem: float = background_data["F_max_bg_sem"]
        self.F_img_bg: float = background_data["F_img_bg"]
        self.F_img_bg_sem: float = background_data["F_img_bg_sem"]

    def analyse_single_point(
        self,
        F_max_act: float,
        F_max_act_sem: float,
        F_img_act: float,
        F_img_act_sem: float,
    ) -> AnalysisResult:
        """
        Perform background subtraction and normalisation for a single data point.

        **This method implements the core physics from data_analysis.md — edit
        this to change the analysis.**

        Args:
            F_max_act: Mean fluorescence in MOT-on window (actual/signal data).
            F_max_act_sem: Standard error of the mean for F_max_act.
            F_img_act: Mean fluorescence in imaging window (actual/signal data).
            F_img_act_sem: Standard error of the mean for F_img_act.

        Returns:
            :class:`AnalysisResult` with background-subtracted and normalised
            fluorescence values and uncertainties.
        """
        # ---- Background subtraction (eqs. 1 & 2) ----
        F_max = F_max_act - self.F_max_bg  # eq. 1
        F_img = F_img_act - self.F_img_bg  # eq. 2

        # ---- Uncertainty on subtracted values (eqs. 4 & 5) ----
        sigma_F_max = np.sqrt(F_max_act_sem**2 + self.F_max_bg_sem**2)  # eq. 4
        sigma_F_img = np.sqrt(F_img_act_sem**2 + self.F_img_bg_sem**2)  # eq. 5

        # ---- Normalised fluorescence (eq. 3) ----
        if abs(F_max) < 1e-10:
            warnings.warn(
                f"F_max is near zero ({F_max:.2e}), normalisation is unreliable.",
                stacklevel=2,
            )
            F_norm = np.nan
            sigma_F_norm = np.nan
        else:
            F_norm = F_img / F_max  # eq. 3

            # ---- Uncertainty on F_norm (eq. 7) ----
            # σ_F_norm = F_norm * sqrt((σ_F_img/F_img)² + (σ_F_max/F_max)²)
            rel_img = (sigma_F_img / F_img) ** 2 if abs(F_img) > 1e-10 else 0.0
            rel_max = (sigma_F_max / F_max) ** 2
            sigma_F_norm = abs(F_norm) * np.sqrt(rel_img + rel_max)  # eq. 7

        return AnalysisResult(
            F_max=F_max,
            F_max_uncertainty=sigma_F_max,
            F_img=F_img,
            F_img_uncertainty=sigma_F_img,
            F_norm=F_norm,
            F_norm_uncertainty=sigma_F_norm,
            F_max_act=F_max_act,
            F_max_act_sem=F_max_act_sem,
            F_img_act=F_img_act,
            F_img_act_sem=F_img_act_sem,
            F_max_bg=self.F_max_bg,
            F_max_bg_sem=self.F_max_bg_sem,
            F_img_bg=self.F_img_bg,
            F_img_bg_sem=self.F_img_bg_sem,
        )

    def analyse(self, signal_df: pd.DataFrame) -> list[AnalysisResult]:
        """
        Analyse all sweep points in the extraction summary DataFrame.

        Args:
            signal_df: DataFrame from
                ``UnifiedFluorescenceProcessor.process_all_experiments()``.
                Must contain columns ``F_max``, ``F_max_sem``, ``F_img``,
                ``F_img_sem``.

        Returns:
            List of :class:`AnalysisResult`, one per row in ``signal_df``.
        """
        results: list[AnalysisResult] = []

        for _, row in signal_df.iterrows():
            ar = self.analyse_single_point(
                F_max_act=row["F_max"],
                F_max_act_sem=row["F_max_sem"],
                F_img_act=row["F_img"],
                F_img_act_sem=row["F_img_sem"],
            )
            # Carry metadata through
            ar.shot_name = row.get("shot_name", "")
            ar.shot_number = row.get("shot_number", None)
            ar.parameter_folder = row.get("parameter_folder", "")
            results.append(ar)

        return results

    def results_to_dataframe(self, results: list[AnalysisResult]) -> pd.DataFrame:
        """Convert a list of AnalysisResult to a DataFrame for saving/display."""
        records = []
        for r in results:
            records.append(
                {
                    "parameter_folder": r.parameter_folder,
                    "shot_name": r.shot_name,
                    "shot_number": r.shot_number,
                    "F_norm": r.F_norm,
                    "F_norm_uncertainty": r.F_norm_uncertainty,
                    "F_max": r.F_max,
                    "F_max_uncertainty": r.F_max_uncertainty,
                    "F_img": r.F_img,
                    "F_img_uncertainty": r.F_img_uncertainty,
                    "F_max_act": r.F_max_act,
                    "F_max_act_sem": r.F_max_act_sem,
                    "F_img_act": r.F_img_act,
                    "F_img_act_sem": r.F_img_act_sem,
                    "F_max_bg": r.F_max_bg,
                    "F_max_bg_sem": r.F_max_bg_sem,
                    "F_img_bg": r.F_img_bg,
                    "F_img_bg_sem": r.F_img_bg_sem,
                }
            )
        return pd.DataFrame(records)


# ============================================================================
# MARK:PLOTTING
# ============================================================================


def plot_normalised_results(
    results: list[AnalysisResult],
    save_path: str | Path | None = None,
    figsize: tuple[int, int] = (14, 10),
):
    """
    Plot the analysed (background-subtracted, normalised) fluorescence results.

    Generates a 2×2 figure:
      - Top-left: F_norm vs shot (with error bars), grouped by parameter folder.
      - Top-right: F_max and F_img (background-subtracted) vs shot.
      - Bottom-left: Raw actual vs background values for diagnostics.
      - Bottom-right: Relative uncertainties for diagnostics.

    Args:
        results: List of :class:`AnalysisResult` from
            ``FluorescenceAnalyser.analyse()``.
        save_path: Directory in which to save figures (None = don't save).
        figsize: Figure size (width, height).
    """
    if not results:
        raise ValueError("No results to plot.")

    df = pd.DataFrame(
        [
            {
                "parameter_folder": r.parameter_folder,
                "shot_number": r.shot_number,
                "F_norm": r.F_norm,
                "F_norm_uncertainty": r.F_norm_uncertainty,
                "F_max": r.F_max,
                "F_max_uncertainty": r.F_max_uncertainty,
                "F_img": r.F_img,
                "F_img_uncertainty": r.F_img_uncertainty,
                "F_max_act": r.F_max_act,
                "F_img_act": r.F_img_act,
                "F_max_bg": r.F_max_bg,
                "F_img_bg": r.F_img_bg,
            }
            for r in results
        ]
    )

    shot_labels = [f"{r.parameter_folder}/s{r.shot_number}" for r in results]

    fig, axes = plt.subplots(2, 2, figsize=figsize)
    cmap = mpl.colormaps["tab10"]

    # ---- Plot 1: F_norm vs shot (grouped by parameter folder) ----
    ax = axes[0, 0]
    if "parameter_folder" in df.columns and df["parameter_folder"].nunique() > 1:
        groups = df.groupby("parameter_folder")
        colors = cmap(np.linspace(0, 1, max(len(groups), 1)))
        for (pf, group), color in zip(groups, colors):
            x = group["shot_number"] if "shot_number" in group.columns else range(len(group))
            ax.errorbar(
                x,
                group["F_norm"],
                yerr=group["F_norm_uncertainty"],
                fmt="o-",
                capsize=4,
                color=color,
                label=pf,
            )
    else:
        x_data = df["shot_number"] if "shot_number" in df.columns else range(len(df))
        ax.errorbar(
            x_data,
            df["F_norm"],
            yerr=df["F_norm_uncertainty"],
            fmt="o-",
            capsize=5,
            label="F_norm",
        )
    ax.set_xlabel("Shot Number")
    ax.set_ylabel("$F_{\\mathrm{norm}}$")
    ax.set_title("Normalised Fluorescence (background-subtracted)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize="x-small")

    # ---- Plot 2: F_max and F_img (bg-subtracted) ----
    ax = axes[0, 1]
    x_all = np.arange(len(df))
    ax.errorbar(
        x_all,
        df["F_max"],
        yerr=df["F_max_uncertainty"],
        fmt="o-",
        capsize=3,
        label="$F_{\\mathrm{max}}$",
        alpha=0.8,
    )
    ax.errorbar(
        x_all,
        df["F_img"],
        yerr=df["F_img_uncertainty"],
        fmt="s-",
        capsize=3,
        label="$F_{\\mathrm{img}}$",
        alpha=0.8,
    )
    ax.set_xticks(x_all)
    ax.set_xticklabels(shot_labels, rotation=90, fontsize=6)
    ax.set_xlabel("Parameter / Shot")
    ax.set_ylabel("Background-subtracted fluorescence (V)")
    ax.set_title("$F_{\\mathrm{max}}$ and $F_{\\mathrm{img}}$ (bg-subtracted)")
    ax.grid(True, alpha=0.3)
    ax.legend()

    # ---- Plot 3: Raw actual vs background (diagnostics) ----
    ax = axes[1, 0]
    ax.plot(x_all, df["F_max_act"], "o-", label="$F_{\\mathrm{max,act}}$", alpha=0.7)
    ax.plot(x_all, df["F_img_act"], "s-", label="$F_{\\mathrm{img,act}}$", alpha=0.7)
    ax.axhline(
        df["F_max_bg"].iloc[0],
        color="C0",
        ls="--",
        alpha=0.5,
        label=f"$F_{{\\mathrm{{max,bg}}}}$ = {df['F_max_bg'].iloc[0]:.4f}",
    )
    ax.axhline(
        df["F_img_bg"].iloc[0],
        color="C1",
        ls="--",
        alpha=0.5,
        label=f"$F_{{\\mathrm{{img,bg}}}}$ = {df['F_img_bg'].iloc[0]:.4f}",
    )
    ax.set_xticks(x_all)
    ax.set_xticklabels(shot_labels, rotation=90, fontsize=6)
    ax.set_xlabel("Parameter / Shot")
    ax.set_ylabel("Fluorescence (V)")
    ax.set_title("Raw values and background levels")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize="x-small")

    # ---- Plot 4: Relative uncertainties ----
    ax = axes[1, 1]
    rel_F_max = np.where(
        np.abs(df["F_max"]) > 1e-10,
        df["F_max_uncertainty"] / np.abs(df["F_max"]) * 100,
        np.nan,
    )
    rel_F_img = np.where(
        np.abs(df["F_img"]) > 1e-10,
        df["F_img_uncertainty"] / np.abs(df["F_img"]) * 100,
        np.nan,
    )
    rel_F_norm = np.where(
        np.abs(df["F_norm"]) > 1e-10,
        df["F_norm_uncertainty"] / np.abs(df["F_norm"]) * 100,
        np.nan,
    )
    ax.plot(x_all, rel_F_max, "o-", label="$F_{\\mathrm{max}}$ rel. unc. (%)")
    ax.plot(x_all, rel_F_img, "s-", label="$F_{\\mathrm{img}}$ rel. unc. (%)")
    ax.plot(x_all, rel_F_norm, "^-", label="$F_{\\mathrm{norm}}$ rel. unc. (%)")
    ax.set_xticks(x_all)
    ax.set_xticklabels(shot_labels, rotation=90, fontsize=6)
    ax.set_xlabel("Parameter / Shot")
    ax.set_ylabel("Relative uncertainty (%)")
    ax.set_title("Uncertainty diagnostics")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize="x-small")

    fig.tight_layout()

    if save_path is not None:
        save_path = Path(save_path)
        png_path = save_path / "fluorescence_analysis_results.png"
        svg_path = save_path / "fluorescence_analysis_results.svg"
        pkl_path = save_path / "fluorescence_analysis_results.fig.pkl"
        fig.savefig(png_path, dpi=200, bbox_inches="tight")
        fig.savefig(svg_path, bbox_inches="tight")
        with pkl_path.open("wb") as f:
            pickle.dump(fig, f)
        print(f"  Saved: {png_path.name}, {svg_path.name}, {pkl_path.name}")

    plt.show()


# ============================================================================
# EXAMPLE USAGE
# ============================================================================


def example_usage():
    """
    Example usage of the full analysis pipeline.

    Workflow:
    1. Extract fluorescence values from signal data (with MOT on).
    2. Extract background values from background data (repumping off, no MOT).
    3. Analyse: background subtraction + normalisation (eqs. 1-7).
    4. Plot results.
    """

    while True:
        print("\n" + "=" * 60)
        print("FLUORESCENCE ANALYSIS PIPELINE")
        print("=" * 60)

        signal_path = input(
            "\nEnter the SIGNAL data root folder path (or 'exit' to quit): "
        ).strip()
        if signal_path.lower() in ["exit", "x", "e"]:
            break

        background_path = input("Enter the BACKGROUND data folder path: ").strip()

        # --- Stage 1: Extract data ---
        print("\n--- STAGE 1: DATA EXTRACTION ---")

        processor = UnifiedFluorescenceProcessor(signal_path)
        signal_df = processor.process_all_experiments(save_summary=True)

        print("\nExtracted signal data:")
        print(
            signal_df[
                [
                    "parameter_folder",
                    "shot_name",
                    "num_valid_traces",
                    "F_max",
                    "F_max_sem",
                    "F_img",
                    "F_img_sem",
                ]
            ].to_string()
        )

        background_data = processor.process_background(background_path)

        # --- Stage 2: Analyse ---
        print("\n--- STAGE 2: DATA ANALYSIS ---")

        analyser = FluorescenceAnalyser(background_data)
        results = analyser.analyse(signal_df)

        results_df = analyser.results_to_dataframe(results)
        print("\nAnalysis results:")
        print(
            results_df[
                ["parameter_folder", "shot_name", "F_norm", "F_norm_uncertainty", "F_max", "F_img"]
            ].to_string()
        )

        # Save analysis results
        results_csv = Path(signal_path) / "fluorescence_analysis_results.csv"
        results_df.to_csv(results_csv, index=False)
        print(f"\nAnalysis results saved to {results_csv}")

        # --- Stage 3: Plot ---
        print("\n--- STAGE 3: PLOTTING ---")

        plot_normalised_results(results, save_path=signal_path)
        processor.plot_averaged_traces()


if __name__ == "__main__":
    example_usage()
