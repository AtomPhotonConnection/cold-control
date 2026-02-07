# Unified Fluorescence Analysis - User Guide

## Overview

`unified_fluorescence_analysis.py` is a single-script data analysis pipeline for processing oscilloscope CSV files from fluorescence experiments. It automates the workflow of:

1. **Loading** multiple CSV traces from each shot
2. **Aligning** all traces to a common reference point (MOT drop event)
3. **Averaging** aligned traces to reduce noise
4. **Normalizing** fluorescence based on MOT-on/MOT-off reference values
5. **Calculating metrics** including normalized fluorescence and uncertainties
6. **Plotting** results for quick visualization

## Quick Start

```python
from unified_fluorescence_analysis import UnifiedFluorescenceProcessor

# Point to your experimental data
processor = UnifiedFluorescenceProcessor(root_folder="/path/to/experiment/data")

# Process everything using configuration parameters at top of file
summary_df = processor.process_all_experiments()

# Plot results
processor.plot_results()
processor.plot_averaged_traces()
```

## Configuration Parameters

All experiment-specific parameters are defined at the **top of the file** for easy modification:

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `FLUORESCENCE_CHANNEL` | 4 | Which channel contains fluorescence signal |
| `MARKER_CHANNEL` | 2 | Which channel contains timing marker (if used) |
| `ROLLING_WINDOW` | None | Smoothing window size (set to ~64 for noise reduction) |
| `FLUOR_DROP_VOLTAGE` | 19.7e-3 V | Voltage threshold for MOT drop detection. Make sure this isn't set too high: if it is, then noise in the photodiode reading might make it seem like the MOT has turned off before it actually has.|
| `TIME_BEFORE_DROP` | 1.1e-3 s | How far back from MOT drop to capture in alignment. If this is too long then the processor may attempt to use data outside the range that has been collected, leading to errors. |
| `TIME_AFTER_DROP` | 5e-3 s | How far forward from MOT drop to capture. As above, this value needs to be small enough that the processor never attempts to collect data outside the time range of any of the csvs. |
| `BACKGROUND_WINDOW` | (-0.5e-3, 0) s | Time window for MOT-on baseline (high fluorescence) |
| `FINAL_WINDOW` | (4e-3, 5e-3) s | Time window for MOT-off reference (low fluorescence) |
| `IMAGING_WINDOW` | (1.6e-3, 2.1e-3) s | Time window of imaging pulse |
| `NUM_INTERPOLATION_POINTS` | 50000 | Resolution of aligned/averaged traces |

All times are **relative to the MOT drop event** (t=0).

## How It Works

### 1. Data Loading
```python
processor.load_csv_files(shot_folder)
```
- Finds all `iteration_*_data.csv` files in a shot folder
- Loads each with optional rolling-window smoothing
- Returns list of DataFrames

### 2. Alignment & Averaging
```python
averaged_df, drop_times = processor.align_and_average(dataframes)
```

**Purpose:** All experimental traces have slightly different timing. We align them to the same reference point (MOT drop) so they can be meaningfully averaged.

**Process:**
1. For each trace, find the time when fluorescence first drops below `FLUOR_DROP_VOLTAGE`
2. Shift all traces relative to their individual drop times
3. Interpolate each channel to a common aligned time axis
4. Average the interpolated channels using `np.nanmean()`

**Output:** 
- `averaged_df`: DataFrame with time axis relative to MOT drop, and averaged channel values
- `drop_times`: List of actual drop times for each trace (useful for diagnostics)

### 3. Normalization
```python
metrics = processor.calculate_normalized_fluorescence(averaged_df)
```

**Formula:**
$$F_{normalized} = \frac{F(t) - F_{low}}{F_{high} - F_{low}}$$

Where:
- **F_high** = Mean fluorescence in `BACKGROUND_WINDOW` (MOT is on, strong signal)
- **F_low** = Mean fluorescence in `FINAL_WINDOW` (MOT is off, weak signal)  
- **F(t)** = Instantaneous fluorescence during imaging pulse

**Why normalize?** 
- Removes experiment-to-experiment variations in absolute fluorescence level
- Accounts for drifts in detector performance
- Makes results comparable across different days/conditions
- F_normalized = 1 means fluorescence at MOT-on level
- F_normalized = 0 means fluorescence at MOT-off level

**Uncertainty Propagation:**
Errors from both F_high and F_low are combined:
$$\sigma_{F_{norm}} = F_{norm} \cdot \sqrt{\left(\frac{\sigma_{high}}{F_{high}}\right)^2 + \left(\frac{\sigma_{low}}{F_{low}}\right)^2}$$

### 4. Metrics Calculation

For each shot, the script computes:

| Metric | Description |
|--------|-------------|
| `F_high`, `F_high_std` | MOT-on fluorescence ± std |
| `F_low`, `F_low_std` | MOT-off fluorescence ± std |
| `scale_factor` | F_high - F_low (denominator of normalization) |
| `F_normalized` | Mean normalized fluorescence during imaging |
| `F_normalized_uncertainty` | Error in normalized fluorescence (propagated) |
| `raw_integral` | Integral of raw fluorescence in imaging window |
| `normalized_integral` | Integral of normalized fluorescence |
| `num_valid_traces` | How many of the loaded traces were successfully aligned |
| `mean_drop_time`, `std_drop_time` | Timing statistics (useful for debugging) |

### 5. Output

**Summary CSV:**
- Saved to `fluorescence_analysis_summary.csv` in the root folder
- One row per shot, containing all metrics above
- Can be loaded in Excel/Python for further analysis

**In-Memory Cache:**
- `processor.aligned_data_cache` stores the averaged DataFrame for each shot
- Useful if you want to do custom plotting or re-analyze

## Extending the Script

### Adding a Custom Metric

To calculate an additional metric, override `calculate_normalized_fluorescence()`:

```python
processor = UnifiedFluorescenceProcessor(root_folder)

# Access raw data after processing
processor.process_all_experiments()

# Get first shot's aligned data
first_shot_data = list(processor.aligned_data_cache.values())[0]
time = first_shot_data['Time (s)'].values
fluorescence = first_shot_data['Channel 4 Voltage (V)'].values

# Calculate something custom
my_metric = np.max(fluorescence) - np.min(fluorescence)
print(f"Fluorescence range: {my_metric}")
```

### Modifying Normalization

To use a different normalization scheme, subclass the processor:

```python
class CustomProcessor(UnifiedFluorescenceProcessor):
    def calculate_normalized_fluorescence(self, averaged_df, **kwargs):
        # Get the parent's metrics first
        metrics = super().calculate_normalized_fluorescence(averaged_df, **kwargs)
        
        # Add or modify metrics
        metrics['my_custom_metric'] = ...  # your calculation here
        
        return metrics
```

### Changing Time Windows on the Fly

You don't need to modify the config file; you can override parameters in code:

```python
# Use different windows for this particular analysis
summary = processor.process_all_experiments(
    background_window=(-1e-3, -0.2e-3),  # Different MOT-on window
    final_window=(3e-3, 4e-3),            # Different MOT-off window
    img_window=(1.7e-3, 2.0e-3)           # Different imaging window
)
```

### Accessing Individual Shot Data

After processing, each shot's aligned trace is cached:

```python
processor.process_all_experiments()

# Get data for shot named "shot_001"
shot_data = processor.aligned_data_cache.get("shot_001")

# Plot custom analysis for this shot
if shot_data is not None:
    time = shot_data['Time (s)'] * 1e3  # Convert to ms
    ch4 = shot_data['Channel 4 Voltage (V)']
    
    plt.figure()
    plt.plot(time, ch4)
    plt.xlabel('Time since MOT drop (ms)')
    plt.ylabel('Fluorescence (V)')
    plt.show()
```

### Filtering Results

To analyze only certain shots:

```python
summary_df = processor.process_all_experiments()

# Filter to shots with good signal
good_shots = summary_df[summary_df['num_valid_traces'] > 80]

# Statistics on filtered data
print(f"Mean normalized fluorescence: {good_shots['F_normalized'].mean():.3f}")
print(f"Std: {good_shots['F_normalized'].std():.3f}")
```

## Common Diagnostics

### Shot has low `num_valid_traces`
- **Problem:** Many traces don't cross the drop voltage threshold
- **Fix 1:** Adjust `FLUOR_DROP_VOLTAGE` (lower it slightly to be more permissive)
- **Fix 2:** Check oscilloscope gain/offset during experiment
- **Fix 3:** May indicate genuinely bad shots that should be excluded

### `F_normalized` is close to 0 or 1 consistently
- **Problem:** Background or final windows may be misaligned
- **Fix:** Plot one shot with `processor.plot_averaged_traces()` to visualize the time windows
- **Check:** Do `BACKGROUND_WINDOW` and `FINAL_WINDOW` capture the correct regions?

### Normalized fluorescence uncertainties are very large
- **Problem:** Background or final window has high variance
- **Fix 1:** Widen the time window to average out noise
- **Fix 2:** Apply rolling smoothing: set `ROLLING_WINDOW = 64` (or similar)
- **Fix 3:** Check oscilloscope noise levels

### Drop time std is large
- **Problem:** Trace alignment is drifting in time
- **Diagnosis:** This is normal if trigger jitter is large
- **Impact:** Slightly increases uncertainty in final results

## Output Format Example

After running analysis, `fluorescence_analysis_summary.csv` looks like:

```
shot_name  shot_number  num_valid_traces  F_high     F_low     F_normalized  F_normalized_uncertainty  raw_integral  ...
shot_001   1            95               0.142      0.018     0.623         0.045                    0.0456        ...
shot_002   2            93               0.139      0.016     0.641         0.052                    0.0471        ...
shot_003   3            90               0.145      0.019     0.598         0.048                    0.0421        ...
```

Load and analyze in Python:

```python
import pandas as pd

df = pd.read_csv('fluorescence_analysis_summary.csv')

# Mean and uncertainty
mean = df['F_normalized'].mean()
sem = df['F_normalized'].std() / np.sqrt(len(df))
print(f"Normalized fluorescence: {mean:.3f} ± {sem:.3f}")

# Trend analysis
import matplotlib.pyplot as plt
plt.plot(df['shot_number'], df['F_normalized'], 'o-')
plt.xlabel('Shot Number')
plt.ylabel('Normalized Fluorescence')
plt.show()
```

## File Structure Expectations

The script expects data organized as:

```
root_folder/
├── parameter_folder_1/
│   ├── shot_001/
│   │   ├── iteration_0_data.csv
│   │   ├── iteration_1_data.csv
│   │   └── ...
│   ├── shot_002/
│   │   └── ...
│   └── ...
├── parameter_folder_2/
│   └── ...
└── fluorescence_analysis_summary.csv  (created by script)
```

The script recursively finds all folders matching `shot*` pattern, so you can have arbitrary nesting levels.

## Performance Notes

- Processing is fairly fast (~1-10 seconds per shot depending on number of traces)
- Memory usage is moderate (stores aligned data for all shots)
- For very large datasets (1000+ shots), consider processing in batches
- Interpolation to 50,000 points is smooth but can be reduced if speed is critical

## Troubleshooting

**No shots found:**
- Check that folder structure matches `shot_*` naming
- Make sure CSV files are named `iteration_N_data.csv`

**Memory error:**
- Reduce `NUM_INTERPOLATION_POINTS`
- Process in smaller batches:
  ```python
  for param_folder in root.iterdir():
      processor = UnifiedFluorescenceProcessor(param_folder)
      summary = processor.process_all_experiments()
  ```

**Different results than before:**
- Check all config parameters match your previous analysis
- Plot one shot to visually inspect alignment and windows

---

For questions about the mathematical details or to propose enhancements, refer to the docstrings in the class methods.
