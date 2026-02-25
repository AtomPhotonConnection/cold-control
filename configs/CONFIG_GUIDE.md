# Cold Control Configuration Guide

This document describes how the different configuration files work, what options they support, and how they are wired together. It also suggests ways the config structure could be improved.

---

## 1. Overview: How configs are wired

The **root config** (`configs/rootConfig.ini`) is the single entry point. It specifies paths to all other config files. The main application (`Root_UI.py`) loads it and then loads:

- **Sequence config** – which DAQ sequence (timing and channel voltages) to use
- **DAQ config** – which DAQ cards/channels/DIOs exist and how they are wired
- **Absorption imaging config** – used for absorption-imaging experiments
- **Experiment config** – used for MOT fluorescence and related experiments (scope, AWG, camera, sweep)

The experiment config references instrument configs by path:

- A **scope config** – standalone scope settings (trigger, channels, ranges, impedance, coupling)
- An **AWG config** – waveforms and AWG sequence
- A **sequence config** – DAQ sequence path (overrides `rootConfig.ini`)


So the dependency tree is:

```
rootConfig.ini
├── sequence_filename     → sequence config (DEPRECATED — prefer sequence_config in experiment config)
├── daq_config_filename  → DAQ config (e.g. daq_config_may25.ini)
├── absorbtion_images_config_filename → absorption imaging config
└── experiment_config_filename        → experiment config (preferred key)
     ├── scope_config    → standalone scope config (e.g. scope/keysight_feb26.ini)
     ├── awg_config      → AWG config (e.g. awg_configs/jan26_new_seq.ini)
     ├── sequence_config → sequence config (e.g. sequence/readout_with_MOTC.ini)
     └── default_sweep_config_path → optional default sweep config for UI dialog

sweep config (self-contained superset of experiment config)
├── scope_config    → scope config path
├── awg_config      → AWG config path
├── sequence_config → sequence config path
├── experiment params (save location, mot reload, iterations)
├── sweep params (sweep_type, num_shots, defaults, sweeps)
└── [metadata] experiment_type = "MOT Fluorescence Sweep"
```

All configs use **ConfigObj** (INI-style with optional nested `[[sections]]`). Paths in the root config are typically relative (e.g. `configs\daq\daq_config_may25.ini`). Relative paths are resolved from **config root**: `COLD_CONTROL_CONFIG_ROOT` env var if set, otherwise the current working directory.

---

## 2. Root config (`configs/rootConfig.ini`)

**Purpose:** Points to the sequence, DAQ, absorption imaging, and experiment config files. Also sets development mode.

**Reader:** `ConfigReader` in `classes/config_readers.py`. Used by `Root_UI.py`, calibration scripts, and lab control scripts. All returned paths are resolved relative to **config root** (`get_config_root()`: `COLD_CONTROL_CONFIG_ROOT` env var if set, else current working directory).

| Option | Description |
|--------|-------------|
| `sequence_filename` | **(Deprecated)** Path to the sequence config. Prefer `sequence_config` in the experiment config instead. Still used as fallback. |
| `daq_config_filename` | Path to the DAQ config (cards, channels, DIOs). |
| `absorbtion_images_config_filename` | Path to the absorption imaging experiment config. |
| `experiment_config_filename` | **Preferred.** Path to the MOT fluorescence / experiment config. |
| `development_mode` | Boolean; when true, enables development-mode behaviour (e.g. mocked DAQ). |

Use `get_experiment_config_fname()` to get the experiment config path.

---

## 3. Experiment config (e.g. `expt_config_feb26.ini`)

**Purpose:** Defines a single MOT-fluorescence-style experiment: save location, iterations, and references to instrument configs (scope, AWG, sequence) by path.

**Reader:** `ExperimentConfigReader.get_mot_flourescence_configuration()` in `classes/config_readers.py`. Loaded by Experimental_UI using the path from the root config's `experiment_config_filename`.

**Required:** A `[metadata]` section with `experiment_type` (e.g. `"MOT Fluorescence"`).

**Optional:** `config_type = experiment` in `[metadata]` enables structure validation on load. `default_sweep_config_path` (top-level) sets the default file/directory for the sweep file dialog.

### New format (preferred)

Instrument configs are referenced by path. Whether scope/AWG/camera are used is determined by whether the corresponding path key is present.

| Option | Description |
|--------|-------------|
| `save location` | Directory (or base path) for saving experiment data. |
| `mot reload` | MOT reload time (e.g. milliseconds). |
| `iterations` | Number of experiment iterations (shots) per run. |
| `scope_config` | Path to standalone scope config file (see section 3a). Presence means scope is used. |
| `awg_config` | Path to AWG config file. Presence means AWG is used. |
| `sequence_config` | Path to sequence config file. Overrides `rootConfig.ini` `sequence_filename`. |
| `default_sweep_config_path` | Optional. Default sweep config file for UI dialog. |

### Old format (backward compatible, deprecated)

A `DeprecationWarning` is emitted when inline scope/AWG settings are detected.

| Option | Description |
|--------|-------------|
| `use_cam` | `True`/`False` - use camera. |
| `use_scope` | `True`/`False` - use oscilloscope. |
| `use_awg` | `True`/`False` - use AWG. |
| `[scope_settings]` | Inline scope settings (trigger, channels, ranges, impedance, coupling). |
| `[awg_settings]` | Inline AWG path reference (`config_path`). |

### Section: `[metadata]`

| Option | Description |
|--------|-------------|
| `experiment_type` | String identifying the experiment type, e.g. `"MOT Fluorescence"`. |
| `config_type` | Optional. Set to `experiment` to enable validation. |

---

## 3a. Scope config (e.g. `scope/keysight_feb26.ini`)

**Purpose:** Standalone scope settings extracted from inline experiment config `[scope_settings]`. Referenced from experiment/sweep configs by path. Parsed into a `ScopeConfiguration` object.

**Reader:** `ScopeConfigReader.load_scope_configuration()` in `classes/config_readers.py`.

### Top-level options

| Option | Description |
|--------|-------------|
| `trigger_channel` | Scope channel number for trigger. |
| `trigger_level` | Trigger level (voltage). |
| `sample_rate` | Scope sample rate (Hz). |
| `time_range` | Timebase range as `start, stop` (e.g. `-100e-6, 4.1e-3`). |

### Section: `[data_channels]`

Subsections `[[1]]`, `[[2]]`, etc. one per channel. Channel number is the subsection key.

| Option | Description |
|--------|-------------|
| `range` | Voltage range as `lower, upper` (e.g. `-1.0, 5.0`). |
| `impedance` | `high` (1 MOhm) or `low` (50 Ohm). Default: `high`. |
| `coupling` | `AC` or `DC`. Default: `DC`. |


## 4. AWG config (e.g. `awg_configs/jan26_new_seq.ini`)

**Purpose:** Defines the AWG sequence: which waveforms are played, in what order, on which channels, with what delays and markers. The experiment config references this file via `[awg_settings] config_path`.

**Reader:** Loaded indirectly: `ExperimentConfigReader` reads `awg_settings.config_path` and then parses this file with `MyConfig` to build an `AwgConfiguration` (and optionally a second config from `config_path_single`).

### Top-level options

| Option | Description |
|--------|-------------|
| `waveform sequence` | Python list of lists of waveform indices, e.g. `"[2, 3],[0, 4],[1]"` for segments. |
| `waveform stitch delays` | Delays between segments (same structure as sequence). |
| `interleave waveforms` | Boolean for interleaved waveform mode. |
| `sample rate` | AWG sample rate (Hz). |
| `burst count` | Burst count. |
| `waveform output channels` | Comma-separated channel names, e.g. `channel1, channel2, channel3`. |
| `waveform output channel lags` | Per-channel lag (e.g. seconds), comma-separated, same order as channels. |
| `marked channels` | Channels that carry markers, comma-separated. |
| `marker width` | Marker pulse width (e.g. seconds). |

### Section: `[waveforms]`

Subsections `[[0]]`, `[[1]]`, … keyed by waveform index (must match indices used in `waveform sequence`).

Per-waveform:

| Option | Description |
|--------|-------------|
| `modulation frequency` | Modulation frequency (Hz). |
| `phases` | Phase list (can be empty ` , `). |
| `filename` | Path to waveform CSV file (e.g. under `waveforms/`). |

---

## 5. Sequence config (e.g. `sequence/readout_with_MOTC.ini`)

**Purpose:** Defines the DAQ sequence: total time, step, global timings (labels), and per-channel time–voltage pairs and interval styles. This is what the sequence UI edits and what the DAQ runs.

**Reader:** `SequenceReader` in `classes/config_readers.py`; `load_sequence()` builds a `Sequence` object. The root config’s `sequence_filename` points to this file.

### Section: `[notes]`

| Option | Description |
|--------|-------------|
| `user` | Free-form user notes (e.g. triple-quoted string). |
| `config_ch_assignments` | Optional; channel assignment labels for UI/documentation. |

### Section: `[sequence]`

| Option | Description |
|--------|-------------|
| `n_samples` | Number of time samples (length of sequence). |
| `t_step` | Time step (e.g. µs). Total time = n_samples * t_step. |
| `global_timings` | List of `(time, label)` tuples for markers/labels, e.g. `"(0.0, 'MOT on')", "(15000.0, 'MOT off')"`. |

### Section: `[sequence channels]`

Subsections `[[0]]`, `[[1]]`, … one per DAQ channel.

| Option | Description |
|--------|-------------|
| `chNum` | DAQ channel number (must match DAQ config). |
| `tV_pairs` | List of `(time, voltage)` tuples, e.g. `"(0.0, 6.27)", "(15000.0, 0.0)"`. |
| `V_interval_styles` | One integer per interval (flat/ramp/etc.), comma-separated. |

---

## 6. Sweep config (e.g. `sweeps/feb26_sweep_level.ini`)

**Purpose:** Defines a parameter sweep over multiple "shots": e.g. different AWG pulse parameters (Rabi frequencies, waveforms) or different imaging parameters. The UI loads a sweep config when you run a sweep.

**Reader:** `ExperimentConfigReader.get_full_sweep_configuration()` (new format) or `get_mot_flourescence_configuration_sweep()` (old format) in `classes/config_readers.py`. Returns a `MotFluoresceConfigurationSweep` object.

### New format (self-contained, preferred)

New-format sweep files are self-contained: they include all experiment parameters, instrument config paths, and sweep parameters. Detected by `[metadata] experiment_type = "MOT Fluorescence Sweep"`.

#### Top-level experiment params

| Option | Description |
|--------|-------------|
| `save location` | Save directory. |
| `mot reload` | MOT reload time. |
| `iterations` | Iterations per shot. |
| `scope_config` | Path to scope config file. |
| `awg_config` | Path to AWG config file. |
| `sequence_config` | Path to sequence config file. |

#### Sweep params

| Option | Description |
|--------|-------------|
| `notes` | Optional free-form description. |
| `num_shots` | Number of shots per sweep point. |
| `sweep_type` | `"awg_sequence"` or `"mot_imaging"`. |

#### Section: `[metadata]`

| Option | Description |
|--------|-------------|
| `experiment_type` | Must be `"MOT Fluorescence Sweep"`. |

### Old format (backward compatible)

Old-format sweep files contain only sweep parameters; experiment config is loaded separately from the currently active experiment config file. No `[metadata]` section.

### Top-level options (both formats)

| Option | Description |
|--------|-------------|
| `notes` | Optional free-form description. |
| `num_shots` | Number of shots per sweep point (e.g. 3). |
| `sweep_type` | Either `"awg_sequence"` or `"mot_imaging"`. |

### For `sweep_type = "awg_sequence"`

**Section: `[defaults]`**  
Baseline values; each sweep entry can override per-key.

| Option | Description |
|--------|-------------|
| `waveform_indices` | Comma-separated waveform indices to vary (e.g. `0, 1, 2, 3, 4`). |
| `rabi_frequencies` | Default Rabi frequencies (one per waveform index). |
| `modulation_frequencies` | Default modulation frequencies (Hz). |
| `waveforms` | Default waveform CSV paths (one per index). |
| `calibration_paths` | Calibration directories for Rabi scaling (one per index). |

**Section: `[sweeps]`**  
Subsections `[[0]]`, `[[1]]`, …: each is one sweep “point” (e.g. one AWG variant).

| Option | Description |
|--------|-------------|
| `title` | Short name for this sweep point (used in save paths). |
| `rabi_frequencies` | Override Rabi frequencies for this point. |
| `modulation_frequencies` | Override modulation frequencies. |
| `waveforms` | Override waveform paths. |
| `calibration_paths` | Override calibration paths. |

Length of overridden lists must match `waveform_indices` length.

### For `sweep_type = "mot_imaging"`

Sweep dict is built from sections that define ranges:

- `beam_powers`: section with `start`, `stop`, `num_points` (float list).
- `beam_frequencies`: same idea.
- `pulse_lengths`: section with `start`, `stop`, `step` (int list).
- `pulse_times`: same idea.

(Exact section names and structure are as in `get_mot_flourescence_configuration_sweep()`.)

---

## 7. DAQ config (e.g. `daq/daq_config_may25.ini`)

**Purpose:** Defines which DAQ cards exist, which channels belong to which card, channel names, limits, calibrations, and DIOs. Used to build the `DAQ_controller` and the DAQ UI.

**Reader:** `DaqReader.load_daq_controller()` in `classes/config_readers.py`.

### Section: `[DAQ cards]`

**Subsection: `[[master]]`**

| Option | Description |
|--------|-------------|
| `channels` | Comma-separated channel numbers on the master card. |
| `card number` | Hardware card number. |
| `dios` | Comma-separated DIO numbers on this card (or empty). |

**Subsection: `[[slaves]]`**  
Then nested `[[[1]]]`, `[[[2]]]`, … for each slave.

Same options as master: `channels`, `card number`, `dios`.

### Section: `[DIOs]`

Subsections `[[0]]`, `[[1]]`, … per DIO.

| Option | Description |
|--------|-------------|
| `dioName` | Human-readable name. |
| `dioNum` | DIO number (used in DAQ cards’ `dios`). |
| `port` | Port: `A`, `B`, `C`, `CL`, `CH`. |
| `line` | Line number. |
| `direction` | `In`/`Out` (or Input/Output). |
| `enabled state` | `High`/`Low` (or 1/0). |

### Section: `[DAQ channels]`

Subsections `[[0]]`, `[[1]]`, … per channel. Channel numbers and order must match what is listed in `[DAQ cards]`.

| Option | Description |
|--------|-------------|
| `chNum` | Channel number. |
| `chName` | Display name (e.g. in UI). |
| `chLimits` | Min, max voltage as `low, high`. |
| `default value` | Default output voltage. |
| `UIvisible` | Whether to show in UI. |
| `calibrationFname` | Path to calibration file (frequency/voltage etc.); empty if uncalibrated. |

---

## 8. Absorption imaging config (e.g. `absorbtion imaging/jan24_test.ini`)

**Purpose:** Config for absorption-imaging experiments: which channel triggers the camera, which controls imaging power, scan vs fixed frequency, exposure/gain, MOT reload, backgrounds, etc.

**Reader:** `ExperimentConfigReader.get_absorbtion_imaging_configuration()` in `classes/config_readers.py`. Used when `experiment_type` is absorption imaging (or when the UI loads absorption imaging mode from the root config’s absorption imaging config path).

**Typical options (names as in code):**

| Option | Description |
|--------|-------------|
| `scan_abs_img_freq` | Whether to scan absorption imaging frequency. |
| `abs_img_freq_ch` | DAQ channel for absorption imaging frequency. |
| `abs_img_freqs` | Frequency value(s). |
| `camera_trig_ch` | DAQ channel for camera trigger. |
| `imag_power_ch` | DAQ channel for imaging beam power. |
| `camera_trig_levs` | Min, max trigger levels. |
| `imag_power_levs` | Min, max imaging power levels. |
| `camera_pulse_width` | Trigger pulse width. |
| `imag_pulse_width` | Imaging pulse width. |
| `t_imgs` | Imaging time(s). |
| `mot_reload_time` | MOT reload time. |
| `n_backgrounds` | Number of background images. |
| `bkg_off_channels` | DAQ channels to turn off for background. |
| `cam_gain`, `cam_exposure` | Camera settings. |
| `save_location` | Where to save images. |
| `save_raw_images`, `save_processed_images`, `review_processed_images` | Booleans. |
| `cam_gain_lims`, `cam_exposure_lims` | Limits for gain/exposure. |

---

## 9. Implemented improvements and further ideas

### 9.1 Implemented

- **Config root:** Relative paths from the root config are resolved from **config root** (`get_config_root()` in `classes/config_readers.py`). Default is current working directory; override with env var `COLD_CONTROL_CONFIG_ROOT`.
- **experiment_config_filename:** Root config supports `experiment_config_filename` (preferred). `photon_production_config_filename` is removed.
- **Standalone scope configs:** Scope settings are now in standalone `.ini` files (e.g. `configs/scope/keysight_feb26.ini`), parsed by `ScopeConfigReader` into `ScopeConfiguration` objects. Experiment configs reference them by path via `scope_config`.
- **Self-contained experiment configs:** Experiment configs reference instrument configs (scope, AWG, sequence) by path instead of embedding settings inline. Old inline `[scope_settings]`/`[awg_settings]` format is still supported with deprecation warnings.
- **Sequence path in experiment config:** `sequence_config` in experiment configs overrides `rootConfig.ini`'s `sequence_filename` (which is now deprecated).
- **Self-contained sweep configs:** Sweep configs can now be self-contained supersets that include experiment parameters, instrument config paths, and sweep parameters. Detected by `[metadata] experiment_type = "MOT Fluorescence Sweep"`. Old sweep-only files are still supported.
- **config_type:** In experiment config `[metadata]`, optional `config_type = experiment` enables validation.
- **default_sweep_config_path:** Optional top-level key in the experiment config for the sweep file dialog default.
- **Validation on load:** When `config_type = experiment`, `ExperimentConfigReader` runs `_validate_experiment_config_structure()`.
- **Deprecation warnings:** `PhotonProductionExperiment`, `ExperimentalAutomationRunner`, inline scope/AWG settings, and `ConfigReader.get_sequence_fname()` all emit `DeprecationWarning`.

### 9.2 Further improvements

- **Shared defaults:** A small "lab defaults" config could avoid repeating MOT reload, sample rates, etc., across configs.
- **Config diff / template:** A script that diffs two configs or generates a template INI.
- **Optional config_type for other files:** Same pattern could be applied to AWG, sequence, DAQ, and sweep configs.
- **Migrate remaining sweep files:** Convert remaining old-format sweep configs to self-contained format with `[metadata]` section.

---

## 10. Defaults (code behaviour when optional keys are missing)

| Context | Option | Default |
|--------|--------|--------|
| Root | Config root for relative paths | `os.getcwd()` unless `COLD_CONTROL_CONFIG_ROOT` is set |
| Experiment config | `default_sweep_config_path` | `None` (dialog uses `configs/pulse_shaping_expt/sweeps` as initial dir) |
| Experiment config | `config_type` | Not required; validation only runs when set to `experiment` |
| Scope data channels | Per-channel impedance (if `[[data_channel_impedance]]` missing) | `high` (1 MΩ) |
| Scope data channels | Per-channel coupling (if `[[data_channel_coupling]]` missing) | `DC` |
| Keysight scope | `configure_scope` when channel value is tuple (old format) | Impedance from `high_impedance` arg; coupling `DC` |

---

## 11. Quick reference: which file defines what

| You want to… | Edit / select |
|--------------|----------------|
| Change which sequence/DAQ/experiment are loaded | `configs/rootConfig.ini` |
| Change scope ranges, impedance, coupling, trigger | Scope config file (e.g. `scope/keysight_feb26.ini`), referenced from experiment config via `scope_config` |
| Change AWG waveforms and sequence | AWG config (referenced from experiment config via `awg_config`) |
| Change DAQ timing and channel voltages | Sequence config (referenced from experiment config via `sequence_config`, or root `sequence_filename`) |
| Change DAQ hardware (cards, channels, DIOs) | DAQ config (path in root `daq_config_filename`) |
| Run a parameter sweep (e.g. AWG levels) | Sweep config (chosen in UI; structure depends on `sweep_type`) |
| Change absorption imaging params | Absorption imaging config (path in root `absorbtion_images_config_filename`) |

---

*Generated for the cold-control codebase. Config readers live in `classes/config_readers.py`; experiment and sweep logic in `classes/experimental_configs.py` and `classes/experimental_runner.py`.*
