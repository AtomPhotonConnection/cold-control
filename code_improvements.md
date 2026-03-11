# Cold Control – Code Improvements

This file documents completed improvements and outstanding items for the codebase.
Tick items off as they are addressed.

---

## ✅ Completed

### Security
- **Replace `eval()` with `ast.literal_eval()`** throughout `config_readers.py`.
  Prevents arbitrary code execution from values read out of config files
  (waveform sequences, mot reload, counter channels, global timings, etc.).

### Bug Fixes
- **`Image.frombuffer()` type error** in `experimental_runner.py`: wrapped `data[0]`
  with `bytes()` at all three camera image-capture sites
  (`AbsorbtionImagingExperiment` × 2, `MotFluoresceExperiment`).
  PIL's `frombuffer` requires a `bytes`-like object, not the raw ctypes buffer
  returned by the IC-Imaging driver.

### Code Quality
- **`IntervalStyle` → `IntEnum`** in `daq_sequence.py`: replaces the brittle
  `FLAT, RAMP = range(2)` class with a proper `enum.IntEnum`.  Backward-compatible
  with stored integer values (0/1); `to_string`/`from_string`/`get_all` updated.
- **`get_val_array()` performance**: replaced the `np.append()` in a loop (O(n²)
  copies) with a list-of-chunks accumulator and a single `np.concatenate()` call.
- **`Warning(...)` anti-pattern** fixed: replaced silent `Warning("...")` (creates
  but never raises) with `warnings.warn(..., stacklevel=2)` in `to_float_list()`.
- **Marker-width `print()` warning** replaced with `warnings.warn()` in
  `AwgConfigReader._extract_marker_width()`.
- **Remove dead commented-out code** (`get_val_array()` dead branch, `to_float_list`
  alternative implementation) in `config_readers.py` and `daq_sequence.py`.

### Logging
- **`config_readers.py`**: added module-level `logger = logging.getLogger(__name__)`;
  replaced all `print()` calls with `logger.debug/info/error`.
- **`Root_UI.py`**: replaced the hardcoded Windows-only log path
  (`C:\pulse_shaping_data\logging\cold_control.log`) with a portable setup:
  - Log directory defaults to `~/cold_control_logs/` and can be overridden via the
    `COLD_CONTROL_LOG_DIR` environment variable.
  - Uses a `RotatingFileHandler` (10 MB per file, 5 backups) so logs never grow
    without bound.
  - A `StreamHandler` at `INFO` level still prints important messages to the console.
  - `print()` calls in `on_exit()` replaced with `logger.info()`.

---

## 🔲 Outstanding / Future Work

### High Priority

- **Fix pre-existing test failures** in `test_experiment_config_reader.py` and
  `test_awg_config_reader.py`: 14 tests fail because config files reference Windows
  paths (`waveforms\\new_Jan\\...`) and because `ScopeConfiguration` is parsed with
  a `data_channels` key that is absent from the test fixture INI files.

- **`SequenceReader` / `SequenceWriter` round-trip for `IntervalStyle`**: The writer
  now correctly serialises `IntervalStyle` values as plain integers; verify that
  older hand-edited INI files with string values (`"FLAT"`, `"RAMP"`) are rejected
  or handled gracefully.

### Medium Priority

- **Instrument Protocols** (`instruments/protocols.py`): Add `typing.Protocol`
  definitions for `OscilloscopeProtocol`, `AWGProtocol`, and `DAQControllerProtocol`
  so real drivers and `instruments/dummy.py` stubs can be used interchangeably
  without inheritance.  This would enable full static type-checking of experiment
  runners.

- **MOT Fluorescence Alignment Experiment**: A live-alignment loop that repeatedly
  runs the same MOT fluorescence shot and reports a metric (F_norm or F_img) after
  each iteration so the experimenter can tune the physical setup in real time.
  Suggested new class: `MotFluorescenceAlignmentExperiment` in
  `experimental_runner.py`.

- **`ExperimentConfigReader` validation**: the `_validate_experiment_config_structure`
  method only runs when `metadata.config_type == "experiment"`.  Consider making
  structural validation the default so config errors are caught at load time rather
  than when the experiment runs.

- **`ConfigReader.is_development_mode()`**: currently emits a debug log of all config
  keys on every call.  Remove or lower to `logging.DEBUG` once the development
  workflow stabilises.

### Low Priority / Housekeeping

- **Rename `AbsorbtionImaging*` → `AbsorptionImaging*`** (fix typo) across all
  files; this is a large rename that affects config keys, file names and tests.

- **`_ChannelSequence.get_change_func()`**: returns `None` for unrecognised styles
  (the caller then raises `ValueError`).  Raise directly in `get_change_func()` and
  remove the `None`-check at the call site.

- **`DaqSequence.update_time_steps()` rollback**: on validation failure the method
  correctly resets `n_samples` and `t_step` but does *not* revert channel updates
  that succeeded before the first failure.  The existing test covers the error-raise
  path but does not verify that no channel data was mutated.

- **Remove `TODO – MAKE PIECEWISE?`** comment in `get_change_func()` – either
  implement it or delete the comment.

- **Windows-style paths in config files**: several `.ini` files under `configs/`
  contain backslash path separators that break on Linux/macOS.  Migrate to forward
  slashes or `pathlib`-based resolution everywhere.

- **`to_float_list()` edge cases**: the function does not handle `None` input or
  single numeric values; these cases would raise `TypeError` from `map(float, ...)`.
  A more robust implementation should be adopted (the alternative was already written
  and commented out — see git history).

- **Linting / formatting**: run `ruff check --fix` and `ruff format` across the
  whole codebase to apply the rules already declared in `pyproject.toml`.

- **Type annotations**: many functions in `config_readers.py` and
  `experimental_runner.py` lack return-type annotations.  Adding them would improve
  IDE support and catch bugs with Pyright in `standard` mode.
