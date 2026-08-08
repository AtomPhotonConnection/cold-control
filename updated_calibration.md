# Refactoring Proposal — DAQ Calibration (simpler, file-driven, and easier to maintain)

This document describes the refactor I would actually want for the calibration system.

The main goals are:
- keep the calibration system simple,
- stop relying on a complicated interactive UI for calibration selection,
- support the existing large collection of `.txt` calibration files in the `calibrations/` tree,
- and make it easy to see which calibration file is currently being used.

This proposal is intentionally practical and conservative. It does not require the UI to become a calibration browser.

## High-level goals

- Keep calibration handling fully file-driven.
- Convert the existing `.txt` calibration files into `.csv` files in a controlled, repeatable way.
- Make calibration selection explicit through a simple `calibration.ini` file.
- Keep the DAQ UI simple: no interactive calibration viewer.
- Make it easy to find the path to the calibration file currently associated with a channel or experiment.

## 1. Convert existing `.txt` calibration files into `.csv`

The repository already contains a very large number of calibration files in the `calibrations/` folder, and many of them are currently in text form. The refactor should treat these as legacy input data and provide a reliable conversion step.

### Proposed behaviour

- Add a dedicated conversion script whose job is to read the legacy `.txt` files and write `.csv` files with a consistent format.
- The conversion should be explicit and deterministic.
- The generated CSV should always follow the same structure:
  - first column: voltage,
  - second column: measured value,
  - header row: clear, standard names such as `Voltage (V)` and `Value (units)`.

### Conversion rules

The conversion script should:
- read the original file format carefully,
- preserve the numeric values exactly,
- infer the correct units from the source file if possible,
- write a clean CSV file with a consistent column order,
- and store the output in a predictable location, for example alongside the original file or in a dedicated `calibrations/csv/` area.

### Why this is important

The current calibration setup is hard to reason about because the system is mixing multiple file formats and a large number of calibration files. Converting everything to `.csv` first gives one clear, standard representation that the rest of the code can rely on.

### Suggested approach

- Keep the existing `.txt` files as source material.
- Generate `.csv` equivalents once and use those going forward.
- Treat the `.csv` files as the canonical calibration format for the application.

## 2. Replace interactive calibration selection with a simple `calibration.ini`

The DAQ UI should not have an interactive calibration viewer. That is more complexity than the system needs.

Instead, the refactor should use a plain configuration file such as `calibration.ini` to define which calibration file is used for each relevant channel or experiment.

### Example structure

```ini
[calibrations]
channel_0 = calibrations/cool_center/cool_center_abs_amp_at_100MHz.csv
channel_1 = calibrations/cool_center/cool_center_amp_at_100MHz.csv
channel_2 = calibrations/other/another_calibration.csv

[experiment_defaults]
default_abs_amp = calibrations/cool_center/cool_center_abs_amp_at_100MHz.csv
default_amp = calibrations/cool_center/cool_center_amp_at_100MHz.csv
```

### What this file should do

- list the calibration file path for each relevant calibration entry,
- make it easy to edit by hand,
- make it easy to inspect which file is currently in use,
- and make it easy to change a mapping without touching the DAQ UI code.

### Why this is better

- It is simple and transparent.
- It avoids a UI feature that does not really add much value.
- It gives a single place to inspect or modify calibration paths.
- It makes the system easier to debug and easier to move between machines or experiments.

## 3. Keep the DAQ UI simple

The DAQ UI should remain focused on entering values and sending them to the DAQ hardware. It should not try to act like a calibration browser.

### What the UI should do

- display the current value in the relevant units,
- validate the entered value against the configured range,
- convert that value to the internal voltage representation,
- and pass it to the DAQ controller.

## 4. Calibration loading model

The refactor should introduce a very small and clear loading model:

- the application reads `calibration.ini`,
- it resolves the file path for the requested channel or experiment,
- it loads the CSV calibration file,
- it applies the interpolation to convert between displayed units and volts.

This means the logic becomes:

1. read the calibration mapping from `calibration.ini`,
2. resolve the file path,
3. load the CSV,
4. convert values using the interpolation table,
5. send the resulting voltage to the DAQ output path.

## 5. Recommended structure

The refactor should be centred around a simple conceptual model:

- `Calibration` object: responsible for loading and interpolating a single calibration file.
- `CalibrationRegistry` or `CalibrationLoader`: responsible for reading `calibration.ini` and resolving which calibration file should be used.
- `DAQChannel` and `DAQInputChannel`: responsible for applying the calibration to the channel and exposing the correct conversion functions.

The change should be deliberately small and easy to follow.

## 6. Suggested migration plan

1. Keep the existing calibration files in place for now.
2. Add a conversion step to turn the current `.txt` files into `.csv` files.
3. Create a simple `calibration.ini` file that maps channels or experiment names to their current calibration file paths.
4. Update the DAQ loading code to read the calibration file path from `calibration.ini`.
5. Preserve the existing conversion behaviour for values entering and leaving the UI, but make the underlying storage and lookup simpler.

## 7. Practical benefits

This refactor would make the system:
- easier to understand,
- easier to maintain,
- easier to edit by hand,
- easier to debug,
- and much less dependent on UI complexity.

The important idea is that calibration files should be treated as data files with an explicit mapping, not as something the user has to browse through interactively inside the DAQ panel.

## 8. What I would want the final shape to look like

- A clear set of `.csv` calibration files in the `calibrations/` tree.
- A single `calibration.ini` file that lists the calibration paths currently in use.
- A simple conversion utility for the existing `.txt` files.
- A straightforward load path from the config into the DAQ channel objects.
- No interactive calibration viewer in `DAQ_UI`.

That is the refactor I would actually want.
