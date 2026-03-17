The goal of this code is to have an easy to maintain codebase for running cold atom physics
experiments. It should be easy to maintain so that if anything breaks it can be easily fixed.
It should be modular so that different parts of the codebase can be used for different experiments.
And it should be clear what each part of the code is doing so that if changes need to be
made then this can be done quickly and easily.

## Suggested changes

### UI Improvements

1. The sequence UI is very complicated and a bit dodgy. It should be simplified and made so
   that all the channels can be easily turned on and off and removed from the legend (otherwise
   the legend gets too big to fit in the window).

2. `Sequence_UI.py` is a 1350-line monolith containing `DaqSequenceUI`, `SequencePlotUI`,
   `SequenceEditorUI`, `ChannelEditorUI`, and `NotesUI` all in one file. Split each into its
   own module under `UI_classes/sequence/`.


3. `Experimental_UI.py` — `execute_experiment()` (lines 379–438) mixes experiment creation,
   dispatch logic, and error handling directly in the UI class. Extract the experiment
   orchestration into a separate controller/service layer.

4. **[Suggested for future implementation]** Add a dark / light theme toggle.  Tkinter's
   `ttk.Style` supports fully configurable themes.  A `ThemeManager` singleton could
   apply the chosen theme across all frames at startup and on demand, making the UI
   easier to use in dark lab environments.

5. **[Suggested for future implementation]** Replace raw `tk.Entry` + manual validation
   in `ExperimentalParamFrame`, `DaqChannelEntry`, and similar widgets with a shared
   `ValidatedEntry` base widget (using `ttk.Entry` + `tk.StringVar` with a `trace_add`
   callback).  This would centralise input validation, reduce duplicated validation code,
   and make it easier to provide visual feedback (e.g. red border on invalid input).

6. **[Suggested for future implementation]** Replace hard-coded pixel sizes
   (`height=25, width=150`) in `ExperimentalUI._create_experiment_buttons()` and
   similar methods with DPI-aware constants or a layout configuration object.  This
   would make the UI scale correctly on high-DPI displays without manual adjustments
   scattered through the code.

7. **[Suggested for future implementation]** Add a status-bar widget at the bottom of
   the root window to show the current experiment state (idle / running / error) and
   the last logged message in the UI — removing the need to keep a separate terminal
   window open to see progress.

8. **[Suggested for future implementation]** `DAQ_UI.py` — Provide a scrollable
   `Canvas`-backed frame for the channel list so the UI remains usable when there are
   many DAQ channels.  Currently, adding channels beyond the window height causes them
   to be clipped with no scroll.

9. **[Suggested for future implementation]** Replace image-loaded icon buttons with
   `ttk.Button` + Unicode symbols (▶, ■, ✕) as a fallback when icon files are missing,
   so the UI degrades gracefully instead of raising an error or showing blank buttons.

### Bug Fixes

10. None found. Look for bugs and record them here.


### Code Quality & Refactoring

11. **[Done]** Implement the protocols defined in protocols.py. The protocols exist and are
    tested but only the DAQControllerProtocol is used. They should be used for type
    checking and to ensure that code referencing the actual experiment manager classes is
    calling real methods. And that the same methods are implemented in the dummy classes and
    real classes. The type hints should work so that the types of objects are correctly
    inferred. Should there also be a DaqCardProtocol?

12. **[Done]** There should be some kind of validation scripts that allow a config file to be
    attempted to be loaded into the relevant config object to see if it will work properly
    (config validation). Added `validate_config_file()` to `config_readers.py`.

13. **[Done]** `experimental_runner.py` — The MOT reload sleep pattern is now made up of two
    commands, `_start_mot_load()` that starts the MOT loading timer and `_wait_mot_load()`
    that only returns once the MOT loading timer is complete. Now properly implemented using
    `time.perf_counter()`:
    - `_start_mot_load(mot_reload_ms)` calculates and saves a future end timestamp, finishing
      instantly so other experiment code can run completely unblocked.
    - `_wait_mot_load()` subtracts the current time from the saved end time to find the
      remainder, sleeping only for that exact difference (or skipping if already elapsed).

14. `experimental_configs.py` — The `make_property()` function generates trivial properties
    with no validation, obscuring the interface and breaking IDE type inference. Replace with
    `@dataclass` decorators or standard `@property`, reducing boilerplate by ~50%.

15. `experimental_configs.py` — Hardcoded channel numbers: `repump_channel = 20` (line 559),
    `freq_ch = 2` and `power_ch = 6` (lines 853–854, self-documented as "shouldn't be
    hardcoded"). Move to config.

### Type Safety & Documentation

16. Add type hints to all untyped function signatures. Record all currently untyped ones here:


17. **[Done]** Add docstrings to undocumented classes and methods:
    - `DaqReader.__init__()`, `DaqWriter.__init__()`, `ConfigWriter.__init__()`
    - `PhotonProductionBufferedDataHandler.__init__()`
    - `GenericConfiguration.__init__()`, `MotFluoresceConfiguration.__init__()`,
      `ExperimentSessionConfig.__init__()`



### Testing

18. Add tests for any large untested parts of the codebase. List important areas to test here.


### Architecture

19. A `CameraConfiguration` dataclass has been created to replace the raw `cam_dict` dict used in
    `MotFluoresceConfiguration`. This follows the pattern already established by `ScopeConfiguration`.
    This object should also be expanded to work with the absorptionImagingConfig and Experiment,
    and should read the properties from a separate file.


20. **[Done]** Review broad `except Exception` catches in `experimental_runner.py` — these
    log errors but silently swallow them. Now fixed: `MotFluoresceExperiment.run()` and
    `MotFluorescenceAlignmentExperiment._run()` re-raise after logging so failures propagate
    to the caller. Analysis helpers (`_analyse_shot`) intentionally return `None` on failure
    and are left unchanged.

### Further improvements

21. Record any further suggested improvements to the codebase here.