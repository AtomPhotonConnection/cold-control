# Refactoring Proposal v3 — DAQ Calibration (File-Driven Architecture & Robust Safety)

This proposal is strong overall, and it already matches the goals of clarity, safety, and easy maintenance. I would make a few refinements so it is even more practical and less ambiguous during implementation.

### Recommended refinements

1. Make the migration path explicit: the runtime system should use only canonical `.csv` files, while `.txt` files are treated as legacy source data that are converted offline.
2. Make channel mapping names explicit and meaningful (for example `cool_center_abs_amp` or `mot_fluoresce_power`) rather than generic numeric keys like `channel_0`.
3. Keep the responsibilities strictly separated: `Calibration` does interpolation and safety checks; `CalibrationManager` handles loading and mapping; `DAQChannel` only applies the conversion and passes values to the controller.
4. Keep the UI very simple: show the current calibration path and units in a tooltip or label, but do not add editing or preview behavior.
5. Use the existing configuration style in the repository where possible so the new `calibration.ini` feels native to the rest of the project.

---

## 1. High-Level Goals

* **File-Driven Configuration:** Use a explicit `calibration.ini` file to map channels to calibration files.


* **Offline CSV Standardization:** Provide a dedicated batch conversion script to convert legacy `.txt` calibration files into standardized `.csv` files.


* **Encapsulated Calibration Logic:** Centralize unit conversion, limit calculations, and math safety inside a dedicated `Calibration` class.


* **Explicit Extrapolation Policies:** Replace unbounded `numpy.interp` extrapolation with explicit policies (`clamp`, `warn`, `error`) to protect hardware.


* **Lightweight UI:** Keep the UI simple—display active units, validate user inputs, and provide tooltips showing the current calibration path without built-in file editing or plotting.



---

## 2. Legacy File Migration (`scripts/migrate_calibrations.py`)

To eliminate runtime ambiguity caused by supporting multiple text layouts, all legacy `.txt` files in `calibrations/` will be converted to standard `.csv` format before deployment.

* **Script Responsibilities:**
* Parse two-column `.txt` files (comma, space, or tab-delimited).


* Extract units from header strings (e.g., `Power (uW)` $\rightarrow$ `uW`).


* Order data points monotonically by voltage.


* Export structured `.csv` files with standard column headers: `Voltage (V), Value (<units>)`.





---

## 3. Configuration Mapping (`calibration.ini`)

Replace interactive calibration selectors with a plain text INI configuration file to define mappings clearly.

```ini
[calibrations]
channel_0 = calibrations/cool_center/cool_center_abs_amp_at_100MHz.csv
channel_1 = calibrations/cool_center/cool_center_amp_at_100MHz.csv
channel_2 = calibrations/other/another_calibration.csv

[defaults]
extrapolate_policy = clamp

```

* **Benefits:**
* Single source of truth for channel mappings.


* Easily tracked under version control.


* Simple to edit manually or swap between experimental setups.





---

## 4. Core `Calibration` Abstraction & Safety (`classes/calibration.py`)

Encapsulate unit conversions and boundary enforcement into a dedicated class.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import numpy as np

@dataclass
class CalibrationMeta:
    units: str
    source_path: Path

class Calibration:
    def __init__(
        self, 
        voltages: np.ndarray, 
        values: np.ndarray, 
        meta: CalibrationMeta, 
        extrapolate: Literal['clamp', 'warn', 'error'] = 'clamp'
    ):
        self._v = voltages
        self._u = values
        self.meta = meta
        self.extrapolate = extrapolate

    @classmethod
    def from_file(cls, path: Path, extrapolate='clamp') -> 'Calibration':
        # Handles CSV loading; includes graceful fallback for legacy .txt with a logged warning
        ...

    def to_voltage(self, physical_val: float) -> float:
        """Converts physical unit to voltage with explicit extrapolation handling."""
        u_min, u_max = min(self._u), max(self._u)
        if not (u_min <= physical_val <= u_max):
            if self.extrapolate == 'error':
                raise ValueError(f"Value {physical_val} outside calibration bounds [{u_min}, {u_max}]")
            elif self.extrapolate == 'clamp':
                physical_val = float(np.clip(physical_val, u_min, u_max))
        
        return float(np.interp(physical_val, self._u, self._v))

    def from_voltage(self, voltage: float) -> float:
        """Converts voltage to physical unit for UI display."""
        v_min, v_max = min(self._v), max(self._v)
        if self.extrapolate == 'clamp':
            voltage = float(np.clip(voltage, v_min, v_max))
        return float(np.interp(voltage, self._v, self._u))

    def range_in_units(self) -> tuple[float, float]:
        return (float(min(self._u)), float(max(self._u)))

    def range_in_voltage(self) -> tuple[float, float]:
        return (float(min(self._v)), float(max(self._v)))

```

---

## 5. Calibration Manager (`classes/calibration_manager.py`)

The `CalibrationManager` loads `calibration.ini`, manages cached `Calibration` instances, and resolves paths for channels.

* **Key Responsibilities:**
* Parse `calibration.ini` on startup.


* Cache loaded `Calibration` objects to avoid redundant file reads.


* Fallback Parser: If `calibration.ini` points to a legacy `.txt` file, log a deprecation warning and load it gracefully via a fallback parser.


* Provide a `reload()` method to re-read `calibration.ini` dynamically without restarting the application.





---

## 6. UI Integration (`UI_classes/DAQ_UI.py`)

Keep `DAQ_UI` strictly focused on input entry, range validation, and display.

* **Simplified UI Responsibilities:**
* **Limits & Defaults:** Query `channel.calibration.range_in_units()` and `channel.calibration.from_voltage()` to set validation bounds and default display values.


* **Conversions:** Use `channel.calibration.to_voltage()` when sending typed inputs down to `DAQController`.


* **Path Tooltip:** Display the active calibration file path and units as a hover tooltip over the channel label in `DaqChannelEntry`.


* **Reload Trigger:** Add a "Reload Calibrations" action in the UI menu to trigger `CalibrationManager.reload()` on demand.





---

## 7. Implementation-Ready Rollout Plan

The implementation should be done in small, testable steps. The following sequence is designed so that each step can be completed independently and verified before moving on.

### Step 1 — Create the migration script

Create a new script at `scripts/migrate_calibrations.py`.

Responsibilities:
- scan the `calibrations/` tree for legacy `.txt` files,
- parse the file into two numeric columns,
- infer or preserve the unit string,
- write a canonical `.csv` file with standard headers,
- save the output in a deterministic location,
- and log a summary of converted files.

Implementation notes:
- support whitespace-delimited and tab-delimited files,
- support files with headers like `V	uW` or `Voltage (V), Power (uW)`,
- keep the original file unchanged,
- and write output files with a predictable naming convention such as `original_name.csv`.

Acceptance criteria:
- a legacy calibration file can be converted to CSV without manual editing,
- the resulting CSV contains exactly two columns with clear headers,
- and the values are preserved in the same order.

### Step 2 — Add the new calibration configuration file

Create a new file at `calibration.ini` in the repository root.

Responsibilities:
- define the mapping between a number and a tuple containing the channel name and a calibration CSV file,
- define the default extrapolation policy,
- and leave the file easy to edit by hand.

Example structure:

```ini
[defaults]
extrapolate_policy = clamp

[calibrations]
0 = cool_center_amp, calibrations/cool_center/cool_center_abs_amp_at_100MHz.csv
1 = cool_center_freq, calibrations/cool_center/cool_center_amp_at_100MHz.csv
2 = mot_fluoresce_power, calibrations/cool_center/cool_center_abs_amp_at_100MHz.csv
```

Acceptance criteria:
- a developer can add or change a calibration mapping by editing the INI file only,
- and the application can resolve the configured path relative to the repository root.

### Step 3 — Implement the calibration abstraction

Create `classes/calibration.py`.

Responsibilities:
- load a calibration from CSV,
- validate the file contents,
- sort the points by voltage,
- expose `from_voltage()` and `to_voltage()` methods,
- apply the selected extrapolation policy (`clamp`, `warn`, or `error`),
- and expose bounds in both voltage and display units.

Implementation notes:
- use `numpy.interp` internally,
- but wrap it with explicit safety logic,
- and raise clear exceptions or log warnings when values are outside the calibration bounds.

Suggested API:

```python
class Calibration:
    def from_file(path: str | Path, extrapolate: str = "clamp") -> "Calibration": ...
    def from_voltage(self, voltage: float) -> float: ...
    def to_voltage(self, value: float) -> float: ...
    def range_in_voltage(self) -> tuple[float, float]: ...
    def range_in_units(self) -> tuple[float, float]: ...
```

Acceptance criteria:
- a valid CSV file produces a populated calibration object,
- out-of-range values follow the configured policy,
- and the class is easy to test in isolation.

### Step 4 — Implement the calibration manager

Create `classes/calibration_manager.py`.

Responsibilities:
- parse `calibration.ini`,
- resolve the configured file paths,
- instantiate `Calibration` objects,
- cache them for reuse,
- and expose functions such as `get_calibration(name)` and `reload()`.

Implementation notes:
- do not make the manager responsible for UI logic,
- and do not make it responsible for hardware writes.
- It should only own configuration and calibration object resolution.

Acceptance criteria:
- loading the manager returns the correct calibration object for a named entry,
- changing a path in `calibration.ini` and calling `reload()` updates the resolved calibration.

### Step 5 — Refactor `DAQChannel` to use the calibration object

Update the DAQ channel classes in `classes/daq.py`.

Responsibilities:
- each channel should optionally hold a `Calibration` object,
- `DAQChannel` should expose methods to attach a calibration and to convert values using it,
- and the old inline interpolation logic should be removed from the UI-facing path.

Implementation notes:
- keep the storage of raw voltages unchanged,
- but let the channel handle conversion to and from display units through the calibration object,
- and ensure that the DAQ output path still receives a voltage in the correct range.

Acceptance criteria:
- a calibrated channel can convert display input to an internal voltage,
- and a calibrated channel can expose its display limits to the UI.

### Step 6 — Simplify the UI

Update `UI_classes/DAQ_UI.py`.

Responsibilities:
- read the display limits from `channel.calibration.range_in_units()` if present,
- display the value in calibrated units,
- validate the typed value using those display limits,
- convert the user value to voltage via `channel.calibration.to_voltage()` before sending it to the controller,
- and show the active calibration path and units in a tooltip or label.

Implementation notes:
- keep the UI focused on entry and validation only,
- and avoid adding any file editing controls in the panel.

Acceptance criteria:
- the UI works,
- and the display value and the hardware voltage remain consistent.

### Step 7 — Add tests

Add or extend tests under `tests/`.

Suggested test cases:
- `Calibration.from_file()` loads a valid CSV correctly,
- `to_voltage()` clamps values outside the calibration range when policy is `clamp`,
- `to_voltage()` raises an error when policy is `error`,
- `CalibrationManager` resolves the configured path from `calibration.ini`,
- and a channel using a calibration converts values correctly.

Acceptance criteria:
- the new calibration logic is covered by automated tests,
- and regressions in the conversion path are caught early.

### Step 8 — Document the workflow

Add a short internal note describing:
- where the canonical CSV files live,
- how to edit `calibration.ini`,
- how to run the migration script,
- and how to resolve calibration paths when debugging.

This step is optional but recommended because it reduces future confusion.

---

## 8. Final Design Summary

When this refactor is complete, the system should have the following shape:

- legacy `.txt` calibration files are converted offline into `.csv`,
- `calibration.ini` is the single place where channel-to-file mappings are defined,
- `Calibration` encapsulates all conversion logic and safety policy,
- `CalibrationManager` resolves and caches loaded calibrations,
- `DAQChannel` applies those calibrations to channel values,
- and `DAQ_UI` remains lightweight and simple.

This is the version of the refactor I would recommend implementing next.
