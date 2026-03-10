"""
Tests for the unified fluorescence analysis pipeline.

Tests cover:
- FluorescenceAnalyser: background subtraction, normalisation, and
  uncertainty propagation (eqs 1-7 from data_analysis.md)
- UnifiedFluorescenceProcessor: fluorescence value extraction from traces,
  background processing from CSV files
- AnalysisResult dataclass and results_to_dataframe conversion
- Edge cases (near-zero F_max, empty windows, etc.)

Run with:  pytest tests/test_fluorescence_analysis.py -v
"""

import numpy as np
import pandas as pd
import pytest

from data_analysis_functions.unified_fluorescence_analysis import (
    AnalysisResult,
    FluorescenceAnalyser,
    UnifiedFluorescenceProcessor,
)

# ruff: noqa: N803, N806
# N803: Argument name should be lowercase
# N806: Variable name in function should be lowercase

# ===========================================================================
# Helpers
# ===========================================================================


def _make_background_data(
    F_max_bg: float = 0.010,
    F_max_bg_sem: float = 0.001,
    F_img_bg: float = 0.005,
    F_img_bg_sem: float = 0.0005,
) -> dict:
    """Create a background data dict matching process_background() output."""
    return {
        "F_max_bg": F_max_bg,
        "F_max_bg_sem": F_max_bg_sem,
        "F_img_bg": F_img_bg,
        "F_img_bg_sem": F_img_bg_sem,
        "n_background_shots": 5,
    }


def _make_signal_df(
    rows: list[tuple[float, float, float, float]],
) -> pd.DataFrame:
    """Create a signal DataFrame matching process_all_experiments() output.

    Each row is (F_max, F_max_sem, F_img, F_img_sem).
    """
    records = []
    for i, (f_max, f_max_sem, f_img, f_img_sem) in enumerate(rows):
        records.append(
            {
                "shot_name": f"shot{i}",
                "shot_number": i,
                "parameter_folder": f"sweep_{i}",
                "num_traces": 10,
                "num_valid_traces": 10,
                "mean_drop_time": 0.001,
                "std_drop_time": 1e-5,
                "shot_path": f"/data/sweep_{i}/shot{i}",
                "F_max": f_max,
                "F_max_sem": f_max_sem,
                "F_max_n": 500,
                "F_img": f_img,
                "F_img_sem": f_img_sem,
                "F_img_n": 200,
            }
        )
    return pd.DataFrame(records)


def _make_averaged_df(
    mot_on_voltage: float = 0.100,
    img_voltage: float = 0.050,
    mot_off_voltage: float = 0.005,
    n_points: int = 50000,
    time_range: tuple[float, float] = (-0.5e-3, 4e-3),
    mot_on_window: tuple[float, float] = (-0.5e-3, 0),
    img_window: tuple[float, float] = (1.0e-3, 1.5e-3),
) -> pd.DataFrame:
    """Create a synthetic averaged DataFrame for extract_fluorescence_values tests.

    Generates a time-series with distinct voltage levels in the MOT-on,
    imaging, and MOT-off regions.
    """
    time = np.linspace(time_range[0], time_range[1], n_points)
    fluor = np.full_like(time, mot_off_voltage)

    # MOT-on region
    mot_on_mask = (time >= mot_on_window[0]) & (time <= mot_on_window[1])
    fluor[mot_on_mask] = mot_on_voltage

    # Imaging region
    img_mask = (time >= img_window[0]) & (time <= img_window[1])
    fluor[img_mask] = img_voltage

    return pd.DataFrame(
        {
            "Time (s)": time,
            "Channel 3 Voltage (V)": fluor,
        }
    )


# ===========================================================================
# Group A — FluorescenceAnalyser: single-point analysis (eqs 1-7)
# ===========================================================================


class TestAnalyseSinglePoint:
    """Tests for FluorescenceAnalyser.analyse_single_point().

    These verify the core physics: background subtraction (eqs 1-2),
    normalisation (eq 3), and uncertainty propagation (eqs 4-5, 7).
    """

    @pytest.fixture
    def analyser(self) -> FluorescenceAnalyser:
        return FluorescenceAnalyser(_make_background_data())

    def test_background_subtraction_eq1_eq2(self, analyser):
        """F_max and F_img are background-subtracted (eqs 1 & 2)."""
        r = analyser.analyse_single_point(
            F_max_act=0.100,
            F_max_act_sem=0.002,
            F_img_act=0.050,
            F_img_act_sem=0.003,
        )
        assert np.isclose(r.F_max, 0.100 - 0.010)  # eq. 1
        assert np.isclose(r.F_img, 0.050 - 0.005)  # eq. 2

    def test_normalisation_eq3(self, analyser):
        """F_norm = F_img / F_max (eq 3)."""
        r = analyser.analyse_single_point(
            F_max_act=0.100,
            F_max_act_sem=0.002,
            F_img_act=0.050,
            F_img_act_sem=0.003,
        )
        expected = (0.050 - 0.005) / (0.100 - 0.010)  # 0.5
        assert np.isclose(r.F_norm, expected)

    def test_uncertainty_f_max_eq4(self, analyser):
        """σ_F_max = sqrt(σ_act² + σ_bg²) (eq 4)."""
        r = analyser.analyse_single_point(
            F_max_act=0.100,
            F_max_act_sem=0.002,
            F_img_act=0.050,
            F_img_act_sem=0.003,
        )
        expected = np.sqrt(0.002**2 + 0.001**2)
        assert np.isclose(r.F_max_uncertainty, expected)

    def test_uncertainty_f_img_eq5(self, analyser):
        """σ_F_img = sqrt(σ_act² + σ_bg²) (eq 5)."""
        r = analyser.analyse_single_point(
            F_max_act=0.100,
            F_max_act_sem=0.002,
            F_img_act=0.050,
            F_img_act_sem=0.003,
        )
        expected = np.sqrt(0.003**2 + 0.0005**2)
        assert np.isclose(r.F_img_uncertainty, expected)

    def test_uncertainty_f_norm_eq7(self, analyser):
        """σ_F_norm = F_norm * sqrt((σ_img/F_img)² + (σ_max/F_max)²) (eq 7)."""
        r = analyser.analyse_single_point(
            F_max_act=0.100,
            F_max_act_sem=0.002,
            F_img_act=0.050,
            F_img_act_sem=0.003,
        )
        F_max = 0.090
        F_img = 0.045
        sigma_F_max = np.sqrt(0.002**2 + 0.001**2)
        sigma_F_img = np.sqrt(0.003**2 + 0.0005**2)
        F_norm = F_img / F_max
        expected = abs(F_norm) * np.sqrt((sigma_F_img / F_img) ** 2 + (sigma_F_max / F_max) ** 2)
        assert np.isclose(r.F_norm_uncertainty, expected)

    def test_diagnostic_values_are_stored(self, analyser):
        """Input values and background values are carried through for diagnostics."""
        r = analyser.analyse_single_point(
            F_max_act=0.100,
            F_max_act_sem=0.002,
            F_img_act=0.050,
            F_img_act_sem=0.003,
        )
        assert r.F_max_act == 0.100
        assert r.F_max_act_sem == 0.002
        assert r.F_img_act == 0.050
        assert r.F_img_act_sem == 0.003
        assert r.F_max_bg == 0.010
        assert r.F_max_bg_sem == 0.001
        assert r.F_img_bg == 0.005
        assert r.F_img_bg_sem == 0.0005

    def test_full_population_gives_f_norm_near_one(self):
        """When F_img_act ≈ F_max_act, F_norm should be close to 1."""
        bg = _make_background_data(F_max_bg=0.01, F_img_bg=0.01)
        analyser = FluorescenceAnalyser(bg)
        r = analyser.analyse_single_point(
            F_max_act=0.200,
            F_max_act_sem=0.001,
            F_img_act=0.200,
            F_img_act_sem=0.001,
        )
        # Both have same bg subtracted → F_norm = 1.0
        assert np.isclose(r.F_norm, 1.0)

    def test_zero_signal_gives_f_norm_zero(self):
        """When F_img = F_img_bg (no signal above background), F_norm = 0."""
        bg = _make_background_data(F_max_bg=0.01, F_img_bg=0.05)
        analyser = FluorescenceAnalyser(bg)
        r = analyser.analyse_single_point(
            F_max_act=0.200,
            F_max_act_sem=0.001,
            F_img_act=0.050,
            F_img_act_sem=0.001,
        )
        assert np.isclose(r.F_img, 0.0, atol=1e-12)
        assert np.isclose(r.F_norm, 0.0, atol=1e-12)

    def test_zero_background_reduces_to_simple_ratio(self):
        """With zero background, F_norm = F_img_act / F_max_act."""
        bg = _make_background_data(F_max_bg=0.0, F_max_bg_sem=0.0, F_img_bg=0.0, F_img_bg_sem=0.0)
        analyser = FluorescenceAnalyser(bg)
        r = analyser.analyse_single_point(
            F_max_act=0.200,
            F_max_act_sem=0.002,
            F_img_act=0.080,
            F_img_act_sem=0.003,
        )
        assert np.isclose(r.F_norm, 0.080 / 0.200)
        # With zero bg uncertainty, σ_F_max = σ_F_max_act, σ_F_img = σ_F_img_act
        assert np.isclose(r.F_max_uncertainty, 0.002)
        assert np.isclose(r.F_img_uncertainty, 0.003)


# ===========================================================================
# Group B — FluorescenceAnalyser: edge cases
# ===========================================================================


class TestAnalyseEdgeCases:
    def test_near_zero_f_max_gives_nan_with_warning(self):
        """When F_max → 0, normalisation is undefined and should warn."""
        bg = _make_background_data(F_max_bg=0.100)  # bg ≈ signal
        analyser = FluorescenceAnalyser(bg)
        with pytest.warns(UserWarning, match="near zero"):
            r = analyser.analyse_single_point(
                F_max_act=0.100,
                F_max_act_sem=0.001,
                F_img_act=0.050,
                F_img_act_sem=0.001,
            )
        assert np.isnan(r.F_norm)
        assert np.isnan(r.F_norm_uncertainty)

    def test_large_uncertainty_propagates_correctly(self):
        """Verify propagation with large SEMs doesn't blow up or produce NaN."""
        bg = _make_background_data(
            F_max_bg=0.01,
            F_max_bg_sem=0.05,
            F_img_bg=0.005,
            F_img_bg_sem=0.05,
        )
        analyser = FluorescenceAnalyser(bg)
        r = analyser.analyse_single_point(
            F_max_act=0.500,
            F_max_act_sem=0.05,
            F_img_act=0.250,
            F_img_act_sem=0.05,
        )
        assert np.isfinite(r.F_norm)
        assert np.isfinite(r.F_norm_uncertainty)
        # σ_F_norm should be larger than individual relative uncertainties
        assert r.F_norm_uncertainty > 0


# ===========================================================================
# Group C — FluorescenceAnalyser: batch analysis
# ===========================================================================


class TestAnalyseBatch:
    def test_analyse_returns_one_result_per_row(self):
        """analyse() returns a list with one AnalysisResult per DataFrame row."""
        bg = _make_background_data()
        analyser = FluorescenceAnalyser(bg)
        signal_df = _make_signal_df(
            [
                (0.100, 0.002, 0.050, 0.003),
                (0.200, 0.001, 0.080, 0.002),
                (0.150, 0.003, 0.060, 0.004),
            ]
        )
        results = analyser.analyse(signal_df)
        assert len(results) == 3
        assert all(isinstance(r, AnalysisResult) for r in results)

    def test_analyse_carries_metadata(self):
        """Metadata (shot_name, shot_number, parameter_folder) is preserved."""
        bg = _make_background_data()
        analyser = FluorescenceAnalyser(bg)
        signal_df = _make_signal_df([(0.100, 0.002, 0.050, 0.003)])
        results = analyser.analyse(signal_df)
        r = results[0]
        assert r.shot_name == "shot0"
        assert r.shot_number == 0
        assert r.parameter_folder == "sweep_0"

    def test_analyse_matches_single_point(self):
        """Batch analyse() gives the same result as calling analyse_single_point."""
        bg = _make_background_data()
        analyser = FluorescenceAnalyser(bg)

        single = analyser.analyse_single_point(
            F_max_act=0.150,
            F_max_act_sem=0.003,
            F_img_act=0.060,
            F_img_act_sem=0.004,
        )

        signal_df = _make_signal_df([(0.150, 0.003, 0.060, 0.004)])
        batch = analyser.analyse(signal_df)

        assert np.isclose(batch[0].F_norm, single.F_norm)
        assert np.isclose(batch[0].F_norm_uncertainty, single.F_norm_uncertainty)

    def test_results_to_dataframe_has_correct_columns(self):
        """results_to_dataframe() produces a DataFrame with the expected columns."""
        bg = _make_background_data()
        analyser = FluorescenceAnalyser(bg)
        signal_df = _make_signal_df([(0.100, 0.002, 0.050, 0.003)])
        results = analyser.analyse(signal_df)

        df = analyser.results_to_dataframe(results)
        expected_cols = {
            "F_norm",
            "F_norm_uncertainty",
            "F_max",
            "F_max_uncertainty",
            "F_img",
            "F_img_uncertainty",
            "F_max_act",
            "F_max_act_sem",
            "F_img_act",
            "F_img_act_sem",
            "F_max_bg",
            "F_max_bg_sem",
            "F_img_bg",
            "F_img_bg_sem",
            "parameter_folder",
            "shot_name",
            "shot_number",
        }
        assert expected_cols.issubset(set(df.columns))
        assert len(df) == 1

    def test_results_to_dataframe_values_match(self):
        """Values in the DataFrame match those in the AnalysisResult objects."""
        bg = _make_background_data()
        analyser = FluorescenceAnalyser(bg)
        signal_df = _make_signal_df([(0.100, 0.002, 0.050, 0.003)])
        results = analyser.analyse(signal_df)

        df = analyser.results_to_dataframe(results)
        r = results[0]
        assert np.isclose(df["F_norm"].iloc[0], r.F_norm)
        assert np.isclose(df["F_norm_uncertainty"].iloc[0], r.F_norm_uncertainty)


# ===========================================================================
# Group D — UnifiedFluorescenceProcessor: extract_fluorescence_values
# ===========================================================================


class TestExtractFluorescenceValues:
    """Tests for value extraction from synthetic averaged traces."""

    @pytest.fixture
    def processor(self, tmp_path) -> UnifiedFluorescenceProcessor:
        return UnifiedFluorescenceProcessor(str(tmp_path))

    def test_extracts_correct_mean_from_flat_regions(self, processor):
        """Flat-valued regions should give exact means with ~zero SEM."""
        df = _make_averaged_df(mot_on_voltage=0.100, img_voltage=0.050)
        result = processor.extract_fluorescence_values(df)

        assert np.isclose(result["F_max"], 0.100, atol=1e-6)
        assert np.isclose(result["F_img"], 0.050, atol=1e-6)
        # Flat regions → zero std → zero SEM
        assert result["F_max_sem"] < 1e-10
        assert result["F_img_sem"] < 1e-10

    def test_returns_correct_keys(self, processor):
        """The returned dict has all expected keys."""
        df = _make_averaged_df()
        result = processor.extract_fluorescence_values(df)
        expected_keys = {"F_max", "F_max_sem", "F_max_n", "F_img", "F_img_sem", "F_img_n"}
        assert expected_keys == set(result.keys())

    def test_n_counts_are_positive(self, processor):
        """The number of points in each window should be > 0."""
        df = _make_averaged_df()
        result = processor.extract_fluorescence_values(df)
        assert result["F_max_n"] > 0
        assert result["F_img_n"] > 0

    def test_custom_windows_override_defaults(self, processor):
        """Custom window arguments should be used instead of module defaults."""
        # Make trace with known values in specific regions
        df = _make_averaged_df(
            mot_on_voltage=0.200,
            img_voltage=0.080,
            mot_on_window=(-0.3e-3, -0.1e-3),
            img_window=(1.0e-3, 1.2e-3),
        )
        result = processor.extract_fluorescence_values(
            df,
            mot_on_window=(-0.3e-3, -0.1e-3),
            img_window=(1.0e-3, 1.2e-3),
        )
        assert np.isclose(result["F_max"], 0.200, atol=1e-6)
        assert np.isclose(result["F_img"], 0.080, atol=1e-6)

    def test_raises_on_empty_mot_on_window(self, processor):
        """ValueError when no data falls in the MOT-on window."""
        df = _make_averaged_df()
        with pytest.raises(ValueError, match="No data in MOT-on window"):
            processor.extract_fluorescence_values(df, mot_on_window=(99.0, 100.0))

    def test_raises_on_empty_imaging_window(self, processor):
        """ValueError when no data falls in the imaging window."""
        df = _make_averaged_df()
        with pytest.raises(ValueError, match="No data in imaging window"):
            processor.extract_fluorescence_values(df, img_window=(99.0, 100.0))

    def test_sem_increases_with_noise(self, processor):
        """Adding noise to a region should increase the SEM."""
        df_flat = _make_averaged_df(mot_on_voltage=0.100)
        result_flat = processor.extract_fluorescence_values(df_flat)

        # Add noise to the MOT-on region
        df_noisy = df_flat.copy()
        time_data = df_noisy["Time (s)"].to_numpy().copy()
        fluor_data = df_noisy["Channel 3 Voltage (V)"].to_numpy().copy()
        on_mask = (time_data >= -0.5e-3) & (time_data <= 0)
        rng = np.random.default_rng(42)
        fluor_data[on_mask] += rng.normal(0, 0.01, size=on_mask.sum())
        df_noisy["Channel 3 Voltage (V)"] = fluor_data

        result_noisy = processor.extract_fluorescence_values(df_noisy)
        assert result_noisy["F_max_sem"] > result_flat["F_max_sem"]


# ===========================================================================
# Group E — UnifiedFluorescenceProcessor: process_background with files
# ===========================================================================


class TestProcessBackground:
    """Tests for background processing from CSV files on disk."""

    @staticmethod
    def _write_iteration_csv(folder, iteration: int, time_arr, fluor_arr):
        """Write a single iteration CSV file matching the expected format."""
        df = pd.DataFrame(
            {
                "Time (s)": time_arr,
                "Channel 3 Voltage (V)": fluor_arr,
            }
        )
        fname = folder / f"iteration_{iteration}_data.csv"
        df.to_csv(fname, index=False)

    @staticmethod
    def _make_drop_trace(
        n_points: int = 1000,
        pre_drop_voltage: float = 0.050,
        post_drop_voltage: float = 0.0001,
        img_voltage: float = 0.020,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Create a synthetic oscilloscope trace with a fluorescence drop.

        The trace goes: high → drop → imaging pulse → low.
        Uses absolute time starting at 0 with a drop at ~2.5 ms.
        post_drop_voltage must be below FLUOR_DROP_VOLTAGE (0.5e-3 V)
        for drop detection to work.
        """
        time = np.linspace(0, 8e-3, n_points)
        fluor = np.full_like(time, post_drop_voltage)

        # Pre-drop: high fluorescence (0 to 2.5 ms)
        fluor[time < 2.5e-3] = pre_drop_voltage

        # Imaging pulse region (3.5 to 3.98 ms → 1.0 to 1.48 ms after drop)
        img_mask = (time >= 3.5e-3) & (time <= 3.98e-3)
        fluor[img_mask] = img_voltage

        return time, fluor

    def test_process_single_background_shot(self, tmp_path):
        """Processing a single background shot folder returns correct keys."""
        shot_dir = tmp_path / "shot0"
        shot_dir.mkdir()

        time_arr, fluor_arr = self._make_drop_trace()
        for i in range(3):
            self._write_iteration_csv(shot_dir, i + 1, time_arr, fluor_arr)

        processor = UnifiedFluorescenceProcessor(str(tmp_path))
        result = processor.process_background(str(tmp_path))

        expected_keys = {
            "F_max_bg",
            "F_max_bg_sem",
            "F_img_bg",
            "F_img_bg_sem",
            "n_background_shots",
        }
        assert expected_keys == set(result.keys())
        assert result["n_background_shots"] == 1  # one shot folder

    def test_process_background_folder_with_csvs_directly(self, tmp_path):
        """A background folder containing CSVs directly (no shot subfolder) works."""
        time_arr, fluor_arr = self._make_drop_trace()
        for i in range(3):
            self._write_iteration_csv(tmp_path, i + 1, time_arr, fluor_arr)

        processor = UnifiedFluorescenceProcessor(str(tmp_path))
        result = processor.process_background(str(tmp_path))

        assert result["n_background_shots"] == 1

    def test_process_multiple_background_shots(self, tmp_path):
        """Multiple shot folders are averaged, and SEM is computed across shots."""
        for shot_idx in range(4):
            shot_dir = tmp_path / f"shot{shot_idx}"
            shot_dir.mkdir()
            time_arr, fluor_arr = self._make_drop_trace(
                pre_drop_voltage=0.050 + shot_idx * 0.001,
            )
            for i in range(3):
                self._write_iteration_csv(shot_dir, i + 1, time_arr, fluor_arr)

        processor = UnifiedFluorescenceProcessor(str(tmp_path))
        result = processor.process_background(str(tmp_path))

        assert result["n_background_shots"] == 4
        # SEM should be > 0 since we varied the pre-drop voltage
        assert result["F_max_bg_sem"] > 0

    def test_process_background_raises_on_empty_folder(self, tmp_path):
        """ValueError when background folder has no shot folders or CSVs."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        processor = UnifiedFluorescenceProcessor(str(tmp_path))
        with pytest.raises(ValueError, match="No shot folders or CSV files"):
            processor.process_background(str(empty_dir))


# ===========================================================================
# Group F — Full pipeline integration test
# ===========================================================================


class TestFullPipelineIntegration:
    """End-to-end test: generate CSV files → extract → analyse → verify.

    These traces pass through alignment (drop detection, interpolation) and
    rolling-average smoothing, so we verify structural properties rather
    than exact numerical values.  Voltages must be above the
    FLUOR_DROP_VOLTAGE threshold (0.0197 V) in the pre-drop region.
    """

    @staticmethod
    def _make_trace(
        pre_drop: float,
        img: float,
        post_drop: float = 0.0001,
        n: int = 10000,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Create a synthetic oscilloscope trace with a clean MOT drop.

        Layout (absolute time):
            0-2.5 ms: pre-drop fluorescence (high)
            2.5-8 ms: post-drop baseline (low)
            3.5-3.98 ms: imaging pulse (overrides baseline)

        post_drop must be below FLUOR_DROP_VOLTAGE (0.5e-3 V)
        for drop detection to work.
        """
        time = np.linspace(0, 8e-3, n)
        fluor = np.full_like(time, post_drop)
        fluor[time < 2.5e-3] = pre_drop
        img_mask = (time >= 3.5e-3) & (time <= 3.98e-3)
        fluor[img_mask] = img
        return time, fluor

    @staticmethod
    def _write_csvs(folder, time_arr, fluor_arr, n_iterations: int = 5):
        """Write identical iteration CSV files into *folder*."""
        for i in range(n_iterations):
            pd.DataFrame(
                {
                    "Time (s)": time_arr,
                    "Channel 3 Voltage (V)": fluor_arr,
                }
            ).to_csv(folder / f"iteration_{i + 1}_data.csv", index=False)

    def test_pipeline_runs_end_to_end(self, tmp_path):
        """Full pipeline: files → extract → analyse → AnalysisResult."""
        # --- signal ---
        shot_dir = tmp_path / "signal" / "sweep_A" / "shot0"
        shot_dir.mkdir(parents=True)
        t, f = self._make_trace(pre_drop=0.100, img=0.060)
        self._write_csvs(shot_dir, t, f)

        # --- background (pre-drop must be > FLUOR_DROP_VOLTAGE = 0.0197 V) ---
        bg_shot = tmp_path / "background" / "shot0"
        bg_shot.mkdir(parents=True)
        t_bg, f_bg = self._make_trace(pre_drop=0.030, img=0.025)
        self._write_csvs(bg_shot, t_bg, f_bg)

        # --- run pipeline ---
        processor = UnifiedFluorescenceProcessor(str(tmp_path / "signal"))
        signal_df = processor.process_all_experiments(save_summary=False)
        bg_data = processor.process_background(str(tmp_path / "background"))
        analyser = FluorescenceAnalyser(bg_data)
        results = analyser.analyse(signal_df)

        # --- structural checks ---
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, AnalysisResult)
        assert r.shot_name == "shot0"
        assert r.parameter_folder == "sweep_A"

    def test_pipeline_f_norm_is_physical(self, tmp_path):
        """F_norm should lie in (0, 1) for signal > background."""
        shot_dir = tmp_path / "signal" / "sweep_A" / "shot0"
        shot_dir.mkdir(parents=True)
        t, f = self._make_trace(pre_drop=0.100, img=0.060)
        self._write_csvs(shot_dir, t, f)

        bg_shot = tmp_path / "background" / "shot0"
        bg_shot.mkdir(parents=True)
        t_bg, f_bg = self._make_trace(pre_drop=0.030, img=0.025)
        self._write_csvs(bg_shot, t_bg, f_bg)

        processor = UnifiedFluorescenceProcessor(str(tmp_path / "signal"))
        signal_df = processor.process_all_experiments(save_summary=False)
        bg_data = processor.process_background(str(tmp_path / "background"))
        analyser = FluorescenceAnalyser(bg_data)
        results = analyser.analyse(signal_df)

        r = results[0]
        assert 0 < r.F_norm < 1, f"F_norm = {r.F_norm} is outside (0, 1)"
        assert r.F_norm_uncertainty >= 0
        assert np.isfinite(r.F_norm)

    def test_pipeline_background_subtraction_reduces_values(self, tmp_path):
        """Background-subtracted F_max should be less than F_max_act."""
        shot_dir = tmp_path / "signal" / "sweep_A" / "shot0"
        shot_dir.mkdir(parents=True)
        t, f = self._make_trace(pre_drop=0.100, img=0.060)
        self._write_csvs(shot_dir, t, f)

        bg_shot = tmp_path / "background" / "shot0"
        bg_shot.mkdir(parents=True)
        t_bg, f_bg = self._make_trace(pre_drop=0.030, img=0.025)
        self._write_csvs(bg_shot, t_bg, f_bg)

        processor = UnifiedFluorescenceProcessor(str(tmp_path / "signal"))
        signal_df = processor.process_all_experiments(save_summary=False)
        bg_data = processor.process_background(str(tmp_path / "background"))
        analyser = FluorescenceAnalyser(bg_data)
        results = analyser.analyse(signal_df)

        r = results[0]
        assert r.F_max < r.F_max_act, "Background subtraction should reduce F_max"
        assert r.F_img < r.F_img_act, "Background subtraction should reduce F_img"
