# DAQ Calibration — New design (Calibration object + CalibrationManager)

This document describes the current, refactored calibration system: the `Calibration` value object,
the `CalibrationManager` (config-driven loader/cacher), and how runtime code and the UI should use them.

Overview
--------
- Calibration data is stored in CSV files (canonical format). Each CSV contains two columns:
  1. Voltage in volts (V) as the first column.
  2. The physical quantity corresponding to those voltages as the second column (header includes units, e.g. "Power (uW)").
- The runtime representation is a `Calibration` object (see `classes/calibration.py`) with the following key API:
  - `Calibration.from_file(path)` → loads and returns a `Calibration` instance.
  - `calibration.from_voltage(v: float | np.ndarray) -> float | np.ndarray` converts volts → physical units.
  - `calibration.to_voltage(x: float | np.ndarray) -> float | np.ndarray` converts physical units → volts.
  - `calibration.units` and `calibration.meta` provide human-readable units and metadata (source path, extrapolation policy).

CalibrationManager
------------------
- `CalibrationManager` (implemented in `classes/calibration_manager.py`) is the single place that maps logical calibration
  names (from `calibration.ini`) to CSV paths, loads `Calibration` objects on demand, and caches them.
- Use `CalibrationManager.get(name)` (or similar loader API) to obtain a `Calibration` instance; callers should not reparse CSV files directly.

How code should use Calibration objects
--------------------------------------
- DAQ channel objects store a `calibration` attribute when a calibration is applied:
  - `channel.calibration` is either a `Calibration` instance or `None`.
  - To convert a stored voltage into display units: `channel.calibration.from_voltage(voltage)`.
  - To convert a user-supplied display value into volts: `channel.calibration.to_voltage(value)`.
- Important: the DAQ controller and `DAQCard` operate in volts internally. The UI converts to/from volts when displaying or accepting user input.

UI behaviour (current expectations)
----------------------------------
- For calibrated channels the UI displays values in the physical units returned by `calibration.from_voltage`.
- When the user inputs a value in the UI, the UI must convert it to volts using `calibration.to_voltage` before passing it to `DAQController`.
- `DAQController` stores voltages and `DAQCard.array_to_digital_values()` clips voltages to `DAQChannel.chLimits` (in volts) and scales to the DAC digital range.

Removal of old callable shims
----------------------------
- Previous versions exposed two callable attributes on channel objects: `calibrationFromVFunc` and `calibrationToVFunc`.
- These shims have been removed. Please update any code that used those attributes to instead access the `Calibration` instance:

  - Old: `val_units = channel.calibrationFromVFunc(voltage)`
  - New: `val_units = channel.calibration.from_voltage(voltage)`

  - Old: `voltage = channel.calibrationToVFunc(value_units)`
  - New: `voltage = channel.calibration.to_voltage(value_units)`

- If you need help migrating call sites, search the codebase for `calibrationFromVFunc` / `calibrationToVFunc` and replace as above.

Migration utilities
-------------------
- A migration script exists at `scripts/migrate_calibrations.py` which converts legacy two-column `.txt` calibrations
  into canonical CSV files and updates the `calibration.ini` mapping where possible.

Developer checklist
-------------------
- To add a new calibration file: add a CSV and add an entry in `calibration.ini` (name → path + optional extrapolation policy).
- To apply a calibration at runtime: use `CalibrationManager.get("my_calibration_name")` and assign it to `channel.calibration` or call `channel.calibrate(path)`.
- To inspect or debug: print `channel.calibration.meta` or `channel.calibration.units`.

Notes & pitfalls
----------------
- `Calibration` uses linear interpolation via NumPy and supports configurable extrapolation policies (e.g. clamp or error).
- The DAQ code always clips voltages to `DAQChannel.chLimits` (in volts) before scaling to digital codes; ensure `calibration.to_voltage` returns values compatible with those limits.
- There is no automatic unit library; unit strings are for human display only.

Contact
-------
If you want me to run an automated migration of remaining call-sites or open a PR removing the old attributes and updating docs, say so and I'll proceed.

---
Generated programmatically from the refactored calibration subsystem in the repository.
