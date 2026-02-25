# Cold Control Configuration Guide

This document describes how the different configuration files work, what options they support, and how they are wired together. It also suggests ways the config structure could be improved.

---

## 1. Overview: How configs are wired

The **root config** (`configs/rootConfig.ini`) is the single entry point. It specifies paths to all other config files. The main application (`Root_UI.py`) loads it and then loads:

- **Sequence config** – which DAQ sequence (timing and channel voltages) to use
- **DAQ config** – which DAQ cards/channels/DIOs exist and how they are wired
- **Absorption imaging config** – used for absorption-imaging experiments
- **Photon production / experiment config** – used for MOT fluorescence and related experiments (scope, AWG, camera, sweep)

The experiment config can in turn reference:

- An **AWG config** – waveforms and AWG sequence
- Optionally a **sweep config** – when running parameter sweeps (e.g. AWG pulse sweeps)

So the dependency tree is:

```
rootConfig.ini
├── sequence_filename     → sequence config (e.g. readout_with_MOTC.ini)
├── daq_config_filename  → DAQ config (e.g. daq_config_may25.ini)
├── absorbtion_images_config_filename → absorption imaging config
├── experiment_config_filename        → experiment config (preferred key)
└── photon_production_config_filename → experiment config (deprecated, kept for backward compatibility)
                                         ├── [awg_settings] config_path → AWG config (e.g. jan26_new_seq.ini)
                                         └── default_sweep_config_path  → optional default sweep config for UI dialog
```

All configs use **ConfigObj** (INI-style with optional nested `[[sections]]`). Paths in the root config are typically relative (e.g. `configs\daq\daq_config_may25.ini`). Relative paths are resolved from **config root**: `COLD_CONTROL_CONFIG_ROOT` env var if set, otherwise the current working directory.

---

## 2. Root config (`configs/rootConfig.ini`)

**Purpose:** Points to the sequence, DAQ, absorption imaging, and experiment config files. Also sets development mode.

**Reader:** `ConfigReader` in `classes/Config.py`. Used by `Root_UI.py`, calibration scripts, and lab control scripts. All returned paths are resolved relative to **config root** (`get_config_root()`: `COLD_CONTROL_CONFIG_ROOT` env var if set, else current working directory).

| Option | Description |
|--------|-------------|
| `sequence_filename` | Path to the sequence config (DAQ timing and channel outputs). |
| `daq_config_filename` | Path to the DAQ config (cards, channels, DIOs). |
| `absorbtion_images_config_filename` | Path to the absorption imaging experiment config. |
| `experiment_config_filename` | **Preferred.** Path to the MOT fluorescence / experiment config (scope, AWG, camera, etc.). |
| `photon_production_config_filename` | **Deprecated.** Same as experiment config; kept for backward compatibility. Code prefers `experiment_config_filename` if both are set. |
| `development_mode` | Boolean; when true, enables development-mode behaviour (e.g. mocked DAQ). |

Use `get_experiment_config_fname()` or `get_photon_production_config_fname()` (both return the experiment config path). Only one of each filename is active; commented lines are alternatives.

---

## 3. Experiment config (e.g. `expt_config_feb26.ini`)

**Purpose:** Defines a single MOT-fluorescence–style experiment: save location, iterations, whether camera/scope/AWG are used, and their settings (including scope channel ranges, impedance, coupling). Can point to an AWG config.

**Reader:** `ExperimentConfigReader.get_mot_flourescence_configuration()` (and related) in `classes/Config.py`. Loaded by Experimental_UI using the path from the root config’s `photon_production_config_filename`.

**Required:** A `[metadata]` section with `experiment_type` (e.g. `"MOT Fluorescence"`). This is used to decide which getter runs (e.g. MOT fluorescence vs absorption imaging).

**Optional:** `config_type = experiment` in `[metadata]` enables structure validation on load. `default_sweep_config_path` (top-level) sets the default file/directory for the “Configure fluoresce sweep” file dialog when present and valid.

### Top-level options

| Option | Description |
|--------|-------------|
| `save location` | Directory (or base path) for saving experiment data. |
| `mot reload` | MOT reload time (e.g. milliseconds). |
| `iterations` | Number of experiment iterations (shots) per run. |
| `use_cam` | `True`/`False` – use camera. |
| `use_scope` | `True`/`False` – use oscilloscope. |
| `use_awg` | `True`/`False` – use AWG. |

### Section: `[scope_settings]`

Used only if `use_scope` is True.

| Option | Description |
|--------|-------------|
| `trigger_channel` | Scope channel number for trigger. |
| `trigger_level` | Trigger level (voltage). |
| `sample_rate` | Scope sample rate (Hz). |
| `time_range` | Timebase range as `start, stop` (e.g. `-100e-6, 4.1e-3`). |
| `[[data_channels]]` | Subsection: channel number → voltage range as `lower, upper` (e.g. `1 = -1.0, 5.0`). |
| `[[data_channel_impedance]]` | Optional. Channel number → `high` or `low` (1 MΩ or 50 Ω). Default per channel: `high`. If the impedance is `low`, then the coupling cannot be `AC` and the voltage range must be <5 V. |
| `[[data_channel_coupling]]` | Optional. Channel number → `AC` or `DC`. Default per channel: `DC`. |

### Section: `[awg_settings]`

Used only if `use_awg` is True.

| Option | Description |
|--------|-------------|
| `config_path` | Path to the AWG config file (waveforms, sequence, channels, etc.). |
| `config_path_single` | Optional path to a second AWG config (e.g. single-channel); can be empty. |

### Section: `[camera_settings]`

Used only if `use_cam` is True (not shown in the example you opened). Typically includes `cam_exposure`, `cam_gain`, `camera_trig_ch`, `camera_trig_levs`, `camera_pulse_width`, `save_images`, etc.

### Section: `[metadata]`

| Option | Description |
|--------|-------------|
| `experiment_type` | String identifying the experiment type, e.g. `"MOT Fluorescence"`. Drives which configuration getter is called. |
| `config_type` | Optional. Set to `experiment` to enable validation of required keys/sections on load. If present and not `experiment`, a warning is emitted. |

### Optional top-level

| Option | Description |
|--------|-------------|
| `default_sweep_config_path` | Path to a sweep config file. If set and the file exists, the “Configure fluoresce sweep” dialog opens with this file’s directory and optionally this file selected. |

---

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

**Reader:** `SequenceReader` in `classes/Config.py`; `loadSequence()` builds a `Sequence` object. The root config’s `sequence_filename` points to this file.

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

**Purpose:** Defines a parameter sweep over multiple “shots”: e.g. different AWG pulse parameters (Rabi frequencies, waveforms) or different imaging parameters. The UI loads a sweep config when you run a sweep; it is not referenced from the experiment config file.

**Reader:** `ExperimentConfigReader.get_mot_flourescence_configuration_sweep()` in `classes/Config.py`. Returns sweep type, number of shots, and a sweep parameter dict.

### Top-level options

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

**Reader:** `DaqReader.load_DAQ_controller()` in `classes/Config.py`.

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

**Reader:** `ExperimentConfigReader.get_absorbtion_imaging_configuration()` in `classes/Config.py`. Used when `experiment_type` is absorption imaging (or when the UI loads absorption imaging mode from the root config’s absorption imaging config path).

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

- **Config root:** Relative paths from the root config are resolved from **config root** (`get_config_root()` in `classes/Config.py`). Default is current working directory; override with env var `COLD_CONTROL_CONFIG_ROOT`.
- **experiment_config_filename:** Root config supports `experiment_config_filename` (preferred). `photon_production_config_filename` is still read and written for backward compatibility; a deprecation warning is emitted when only the old key is present. Use `get_experiment_config_fname()` or `get_photon_production_config_fname()`.
- **config_type:** In experiment config `[metadata]`, optional `config_type = experiment` enables validation of required keys/sections when the config is loaded. If `config_type` is present and not `experiment`, a warning is emitted.
- **default_sweep_config_path:** Optional top-level key in the experiment config. When set and the file exists, the “Configure fluoresce sweep” dialog uses its directory and file as the default.
- **Validation on load:** When `config_type = experiment`, `ExperimentConfigReader` runs `_validate_experiment_config_structure()` (required top-level keys, `[metadata].experiment_type`, and conditional checks for `[scope_settings]` / `[awg_settings]` when `use_scope` / `use_awg` is True).

### 9.2 Further improvements

- **Shared defaults:** A small “lab defaults” config or environment section could be merged when loading to avoid repeating MOT reload, sample rates, etc., across configs.
- **Config diff / template:** A script that diffs two configs of the same type or generates a template INI from the expected structure would help when adding new experiments.
- **Optional config_type for other files:** Same pattern (optional `config_type` + validation) could be applied to AWG, sequence, DAQ, and sweep configs.

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
| Change scope ranges, impedance, coupling, trigger | Experiment config `[scope_settings]` and `[[data_channels]]` etc. |
| Change AWG waveforms and sequence | AWG config (path in experiment config `[awg_settings] config_path`) |
| Change DAQ timing and channel voltages | Sequence config (path in root `sequence_filename`) |
| Change DAQ hardware (cards, channels, DIOs) | DAQ config (path in root `daq_config_filename`) |
| Run a parameter sweep (e.g. AWG levels) | Sweep config (chosen in UI; structure depends on `sweep_type`) |
| Change absorption imaging params | Absorption imaging config (path in root `absorbtion_images_config_filename`) |

---

*Generated for the cold-control codebase. Config readers live in `classes/Config.py`; experiment and sweep logic in `classes/experimental_configs.py` and `classes/experimental_runner.py`.*
