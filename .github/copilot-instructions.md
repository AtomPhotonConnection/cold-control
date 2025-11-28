## Quick context — what this project is

This is the GUI + control stack for an experimental atomic cavity-QED setup (lab hardware, AWG, DAQ, camera, TDC, scopes).
The GUI entry-point is `Root_UI.py`. The app is configuration-driven: .ini files in `configs/` define DAQ layouts, sequences and experiment parameters.

## High‑level architecture (read these files first)
- Entry & UI: `Root_UI.py` — creates and composes UI widgets from `UI_classes/`.
- UI components: `UI_classes/DAQ_UI.py`, `UI_classes/Sequence_UI.py`, `UI_classes/Experimental_UI.py` — each manages their own lifecycle.
- Core domain: `classes/` — DAQ low-level (classes/DAQ.py), sequences (classes/Sequence.py), config readers/writers (classes/Config.py) and experiment runners (classes/ExperimentalRunner.py).
- Instrument wrappers: `instruments/` (AWG, quTAU TDC, IC Imaging, TF930, etc.). Tests and manual scripts live nearby (e.g. `instruments/WX218x/test_WX218x.py`).
- Helpers: `lab_control_functions/` contains AWG control helpers and other hardware helpers used by experimental runners.

## Important operational assumptions & environment
- The code expects hardware drivers and vendor DLLs (Windows native). `classes/DAQ.py` directly loads `D2K-Dask64` (WinDLL), and many instruments use VISA or vendor SDKs.
- Development mode: if you don't have lab hardware, flip `development_mode = True` in `configs/rootConfig.ini` — DAQ_UI will use a patched / dummy DAQ controller (see `UI_classes/DAQ_UI.py` + `classes/Config.py:load_dummy_DAQ_controller`).

## Project‑specific conventions and gotchas for changes
- Config‑first design: most behaviour is driven by files under `configs/` — change the code only after finding the relevant config entries and test using a config file (Sequence / DAQ / experimental configs).
- DAQ channel ordering: `DAQ_card.expectedChOrderForSeq` (classes/DAQ.py) re-orders sequences for the hardware — when making changes to DAQ sequence handling, ensure reordering and digital scaling (`arrayToDigitalValues`) remain correct.
- Calibration files: channels may be calibrated from CSV or legacy TXT. `DAQ_channel.calibrate` expects a CSV with two columns: voltage, calibration value (units extracted from column name). See `calibrations/` for examples.
- Sequence timing units: Sequence.t_step is in microseconds. Sequences and AWG/timing conversions are sensitive to units — prefer reading Sequence.getLength/getTimeSteps when in doubt.
- UI is stateful and often relies on side-effects (e.g. starting/stopping hardware). When adding tests/mocks prefer to use `development_mode` or patch hardware-level classes.

## Developer workflows (how to run / test locally)
- Run the GUI (desktop):
  - Set development mode in `configs/rootConfig.ini` if you don't have hardware
  - From repo root: `python3 Root_UI.py`
- Manual instrument tests: many `instruments/*` subfolders include manual test scripts (e.g. `instruments/WX218x/test_WX218x.py`) — run them directly, but they are hardware‑dependent.
- There is no centralized pytest/CI harness in the repository. Tests are ad‑hoc scripts in `instruments/` and `waveforms/tests/`.

## What an AI agent should prioritize
1. Preserve calibration & safety semantics — altering channel limits, default values, or DAQ output code can have physical effects in a lab: prefer to run in `development_mode` or add clear opt‑outs.
2. Edit configuration parsers (classes/Config.py) when changing experiment behaviour — most user-facing behavior is driven by .ini content.
3. When modifying timing/sequence code, add unit tests that validate conversion between t_step (us), array length, and DAQ/AWG update intervals.

## Useful code pointers / examples you will likely inspect and edit
- Start: `Root_UI.py` (composition of UI and wiring of components)
- DAQ core: `classes/DAQ.py` (registers Win DLL, DAQ_card -> DAQ_controller mapping, calibration functions)
- Configs: `classes/Config.py` (ConfigReader, DaqReader, SequenceReader — your go‑to for config-driven changes)
- Experiment orchestration: `classes/ExperimentalRunner.py` (AWG, TDC, camera, data saver logic — long file, modify carefully)
- UI helpers: `UI_classes/DAQ_UI.py` (shows how dev-mode is used and user interactions)

## Example small tasks and where to implement them
- Add safe platform detection for DAQ DDL load: modify `classes/DAQ.py` to check platform before WinDLL.
- Add unit tests for sequence -> digital scaling: add tests around `Sequence.getArray()` and `DAQ_card.arrayToDigitalValues` with a `development` DAQ instance.
- Improve calibration parsing: update `DAQ_channel.calibrate` and add a test fixture that reads `calibrations/*.txt` or CSV files in this repo.

---
If anything above is unclear or you want extra detail about a section (e.g. configuration format examples, instrument init flows, or safe test scaffolding for hardware), tell me which pieces to expand and I’ll iterate. ✅
