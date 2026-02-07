# Cold Control Configuration Guide

This document describes how the different configuration files work, what options they support, and how they are wired together. It also suggests ways the config structure could be improved.

---

## 1. Overview: How configs are wired

The **root config** (`configs/rootConfig.ini`) is the single entry point. It specifies paths to all other config files. The main application (`Root_UI.py`) loads it and then loads:

- **DAQ config** – which DAQ cards/channels/DIOs exist and how they are wired, including things like calibrations and default values.
- **Experiment config** - the configuration information needed to run any particular experiment. These configs can vary widely depending on the particular experiment being implemented. Absorbtion imaging, photon production, MOT fluorescence and MOT fluorescence sweep experiments can all be configured with these files.

The experiment config can in turn reference:

- **Sequence config** – which DAQ sequence (timing and channel voltages) to use.
- An **AWG config** – waveforms and AWG sequence
- Optionally a **sweep config** – when running parameter sweeps (e.g. AWG pulse sweeps)
- In future a **camera config** - this may be added later to enable the camera to be configured

So the dependency tree is:

```
rootConfig.ini
├── daq_config_filename  → DAQ config (e.g. daq_config_may25.ini)
├── experiment_config_filename        → experiment config 
                                         ├── [configs] sequence_path → sequence config (e.g. readout_with_MOTC.ini)
                                         ├── [configs] awg_path → AWG config (e.g. jan26_new_seq.ini)
                                         ├── [configs] scope_path -> scope config 
                                         └── [configs] sweep_path → sweep config
```

All configs use **ConfigObj** (INI-style with optional nested `[[sections]]`). Paths in the root config are typically relative (e.g. `configs\daq\daq_config_may25.ini`). Relative paths are resolved from **config root**: `COLD_CONTROL_CONFIG_ROOT` env var if set, otherwise the current working directory.

---

## 2. Root config (`configs/rootConfig.ini`)

**Purpose:** Points to the sequence, DAQ, absorption imaging, and experiment config files. Also sets development mode.

**Reader:** `ConfigReader` in `classes/Config.py`. Used by `Root_UI.py`, calibration scripts, and lab control scripts. All returned paths are resolved relative to **config root** (`get_config_root()`: `COLD_CONTROL_CONFIG_ROOT` env var if set, else current working directory).

| Option | Description |
|--------|-------------|
| `daq_config_filename` | Path to the DAQ config (cards, channels, DIOs). |
| `experiment_config_filename` | Path to the experiment config (scope, AWG, camera, etc.). |
| `development_mode` | Boolean; when true, enables development-mode behaviour (e.g. mocked DAQ). |

Use `get_experiment_config_fname()`. Only one of each filename is active; commented lines are alternatives.

---

## 3. Experiment config (e.g. `expt_config_feb26.ini`)

**Purpose:** Defines a single MOT-fluorescence–style experiment: save location, iterations, whether camera/scope/AWG are used, and their settings defined with paths to the relevant config files. Can point to an AWG config, scope config, sweep config, sequence config.

**Reader:** `ExperimentConfigReader.get_mot_flourescence_configuration()` (and related) in `classes/Config.py`. Loaded by Experimental_UI using the path from the root config’s `experimental_config`.


### Top-level options

| Option | Description |
|--------|-------------|
| `experiment_type` | Type of experiment being run, eg. MOT Fluorescence or MOT Fluorescence sweep|
| `save location` | Directory (or base path) for saving experiment data. |
| `mot reload` | MOT reload time (e.g. milliseconds). |
| `iterations` | Number of experiment iterations (shots) per run. |
| `use_cam` | `True`/`False` – use camera. |
| `use_scope` | `True`/`False` – use oscilloscope. |
| `use_awg` | `True`/`False` – use AWG. |
| `use_sweep` | `True`/`False` - whether or not to read the sweep config file. |
| `use_sequence` | `True`/`False` - whether or not to use the DAQ cards to play a sequence. |

### Section: `[configs]`

| Option | Description |
|--------|-------------|
| `awg_path` | Path to the AWG config file (waveforms, sequence, channels, etc.). |
| `sequence_path` | Path to the sequence config file. |
| `scope_path` | Path to the scope config file. |
| `sweep_path` | Path to the sweep config file. |

More details on each of these config files/objects can be found below.


---

## 4. AWG config (e.g. `awg_configs/jan26_new_seq.ini`)

**Purpose:** Defines the AWG sequence: which waveforms are played, in what order, on which channels, with what delays and markers. The experiment config references this file via `[configs] awg_path`.

**Reader:** Still needs to be implemented correctly.

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

Subsections `[[0]]`, `[[1]]`, … keyed by waveform index. They are loaded as a dictionary into the awg config object.

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

## 7. Scope config (e.g. `feb26_scope_config.ini`)

**Purpose:** Contains all the necessary parameters to configure the oscilloscope ready for an experiment.

**Reader:** Not yet created, wil be a config reader in `classes/Config.py`.

| Option | Description |
|--------|-------------|
| `data_channels` | Which channels to read data from. |
| `trigger_channel` | Scope channel number for trigger. |
| `trigger_level` | Trigger level (voltage). |
| `sample_rate` | Scope sample rate (Hz). |
| `time_range` | Timebase range as `start, stop` (e.g. `-100e-6, 4.1e-3`). |
| `[channel_ranges]` | Subsection: channel number → voltage range as `lower, upper` (e.g. `1 = -1.0, 5.0`). |
| `[channel_impedances` | Optional. Channel number → `high` or `low` (1 MΩ or 50 Ω). Default per channel: `high`. If the impedance is `low`, then the coupling cannot be `AC` and the voltage range must be <5 V. |
| `[channel_couplings]` | Optional. Channel number → `AC` or `DC`. Default per channel: `DC`. |

## 8. DAQ config (e.g. `daq/daq_config_may25.ini`)

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

## 9. Absorption imaging config (e.g. `absorbtion imaging/jan24_test.ini`)

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




## 10 Further improvements

- **Config diff / template:** A script that diffs two configs of the same type or generates a template INI from the expected structure would help when adding new experiments.


---

