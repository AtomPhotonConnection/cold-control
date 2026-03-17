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

### Bug Fixes

4. None found. Look for bugs and record them here.


### Code Quality & Refactoring

5. Implement the protocols defined in protocols.py. The protocols exist and are tested but 
    only the DAQControllerProtocol is used. They should be used for type checking and to 
    ensure that code referencing the actual experiment manager classes is calling real methods.
    And that the same methods are implemented in the dummy classes and real classes. The type
    hints should work so that the types of objects are correctly inferred. Should there also
    be a DaqCardProtocol?

6. There should be some kind of validation scripts that allow a config file to be attempted to be loaded into
    the relevant config object to see if it will work properly (config validation).

7. `experimental_runner.py` — The MOT reload sleep pattern is now made up of two commands,
     `_start_mot_load()` that starts the MOT loading timer and `_wait_mot_load()` that only
    returns once the MOT loading timer is complete. However, this isn't properly implemented.
    The code should do the following:
    Gemini said
    Use time.perf_counter() in _start_timer to calculate and save a future end timestamp.
    This finishes instantly, allowing other experiment code to run completely unblocked.
    In _wait_reload, subtract the current time from the saved end time to find the remainder.
    If there is still time left, use time.sleep() to pause for that exact difference.
    If the time has already passed, it skips the sleep and continues executing immediately!

8. `experimental_configs.py` — The `make_property()` function generates trivial properties
    with no validation, obscuring the interface and breaking IDE type inference. Replace with
    `@dataclass` decorators or standard `@property`, reducing boilerplate by ~50%.

9. `experimental_configs.py` — Hardcoded channel numbers: `repump_channel = 20` (line 559),
    `freq_ch = 2` and `power_ch = 6` (lines 853–854, self-documented as "shouldn't be
    hardcoded"). Move to config.

### Type Safety & Documentation

10. Add type hints to all untyped function signatures. Record all currently untyped ones here:


11. Add docstrings to undocumented classes and methods:
    - `DaqReader.__init__()`, `DaqWriter.__init__()`, `ConfigWriter.__init__()`
    - `buffered_data_handler.py`: `__analyse_buffer()`, `start_polling_queue()`,
      `stop_polling_queue()`
    - Most `__init__` methods in `experimental_configs.py`



### Testing

12. Add tests for any large untested parts of the codebase. List important areas to test here.


### Architecture

13. A `CameraConfiguration` dataclass has been created to replace the raw `cam_dict` dict used in
    `MotFluoresceConfiguration`. This follows the pattern already established by `ScopeConfiguration`.
    This object should also be expanded to work with the absorptionImagingConfig and Experiment,
    and should read the properties from a separate file.


14. Review broad `except Exception` catches in `experimental_runner.py` (lines 1231, 1376,
    1441, 1487) — these log errors but silently swallow them. Consider re-raising or at
    least logging full tracebacks so failures are not hidden.

### Further improvements

15. Record any further suggested improvements to the codebase here.