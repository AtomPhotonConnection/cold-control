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

3. `Experimental_UI.py` — `flash_channel()` (lines 620–639) calls `time.sleep()` inside a loop,
   which freezes the entire tkinter event loop. Replace with `root.after()` scheduling.

4. `Experimental_UI.py` — `toggle_run_tone()` hardcodes DAQ channel values (14→2.485,
   8→0.0048, 22→2.0) and physics constants (`run_tone_freqs` at line 225) directly in the UI
   code. Move these to named constants.

5. `Camera_UI.py` — `prepare_camera()` has hardcoded exposure (60) and frame rate (30.00) at
   lines 135–142. The existing TODO says "move these values into the UI". Move them to named constants.

6. `Camera_UI.py` — `prepare_camera()` assumes at least one camera exists without checking
   `cam_names`. Add error handling for missing cameras.

7. Arrow-key increment logic is duplicated between `ExperimentalParamFrame.arrow_key()` and
   `DaqChannelEntry.arrow_key()` in `DAQ_UI.py`. Extract to a shared utility function.

8. Icon loading in `DAQ_UI.py` uses hardcoded relative paths like `Image.open("icons/...")`.
   If the working directory differs from the project root, this will crash. Resolve paths
   relative to the project root using `Path(__file__).parent`.

9. `Experimental_UI.py` — `execute_experiment()` (lines 379–438) mixes experiment creation,
   dispatch logic, and error handling directly in the UI class. Extract the experiment
   orchestration into a separate controller/service layer.

### Bug Fixes

10. **CRITICAL:** `buffered_data_handler.py` line 54 — `target=self.__analyse_buffer()` calls
    the method immediately (note the parentheses) and passes its return value (`None`) as the
    thread target. Fix to `target=self.__analyse_buffer` (no parentheses).

11. `buffered_data_handler.py` — `count_rate`, `hist_stirap`, `completed_iterations`, and
    `new_data_waiting` are read/written from multiple threads without any lock. Add
    `threading.Lock` for thread safety (the existing TODO at line 99 acknowledges this).



### Code Quality & Refactoring

12. Implement the protocols defined in protocols.py

13. There should be some kind of test scripts that allow a config file to be tested to see if
    it will work properly (config validation).

14. `config_readers.py` — Config value parsing (`int()`, `float()`, `to_bool()`,
    `ast.literal_eval()`) is done with no try/except. A malformed config produces cryptic
    `ValueError`/`SyntaxError` tracebacks. Wrap these in a validation helper that gives clear
    error messages pointing to the offending config key and the file that caused it.

15. `experimental_runner.py` — Camera configuration logic is duplicated between
    `AbsorbtionImagingExperiment.__configure_camera()` (lines 393–430) and
    `MotFluoresceExperiment.__configure_camera()` (lines 921–960). Extract a shared
    `_configure_camera_common()` helper on `GenericExperiment`.

16. `experimental_runner.py` — The MOT reload sleep pattern
    `sleep(self.config.mot_reload * 10**-3)` appears in at least 5 places. Extract into two
    methods that are called at the start and end of the waiting period allowing other code
    to be run syncronously.

17. `experimental_runner.py` — `MotFluoresceSweepExperiment` and
    `MotFluorescenceAlignmentExperiment` duplicate `run_in_thread()` instead of inheriting
    from `GenericExperiment`. Refactor to use the base class.

18. `experimental_configs.py` — The `make_property()` function generates trivial properties
    with no validation, obscuring the interface and breaking IDE type inference. Replace with
    `@dataclass` decorators or standard `@property`, reducing boilerplate by ~50%.

19. `experimental_configs.py` — Hardcoded channel numbers: `repump_channel = 20` (line 559),
    `freq_ch = 2` and `power_ch = 6` (lines 853–854, self-documented as "shouldn't be
    hardcoded"). Move to config.

20. Replace all `raise Exception(...)` calls with specific exception types (`RuntimeError`,
    `ValueError`, or custom exceptions). At least 8 instances across `experimental_runner.py`
    (lines 570, 614, 852) and `daq.py` (lines 758, 763, 935).

21. Replace 40+ `print()` calls across `classes/` with proper `logger.info()` /
    `logger.warning()` / `logger.debug()`. Key offenders: `daq.py` (~15 calls),
    `experimental_configs.py` (~12 calls), `buffered_data_handler.py` (2 debug prints).

22. `daq.py` — Lines 157–235 contain ~80 lines of commented-out DAQ constants that duplicate
    the actual constants above. Remove deadcode.

23. `config_readers.py` — Method name typo: `get_mot_flourescence_configuration()` (line 815)
    and `get_mot_flourescence_configuration_sweep()` (line 905) — "flourescence" should be
    "fluorescence". Fix the typo and add a deprecation alias.

24. `config_readers.py` — `ExperimentalAutomationReader` uses bare `map()` returning lazy
    iterators (lines 1168–1177) that are stored in config objects. Wrap in `list()` to avoid
    single-consumption bugs.

25. Remove dead/deprecated code: `PhotonProductionWriter` (line 1121, explicitly deprecated),
    `AbsorbtionImagingWriter.save()` (TODO stub), `ExperimentalAutomationWriter.save()`
    (TODO stub), and large commented-out blocks throughout `experimental_runner.py`.

26. Fix spelling inconsistency: "absorbtion" should be "absorption" in class names
    (`AbsorbtionImagingExperiment`, `AbsorbtionImagingConfiguration`), config keys, method
    names, and filenames. This is a larger refactor — plan it carefully with find-and-replace
    across the entire codebase.

### Type Safety & Documentation

27. Add type hints to all untyped function signatures. Key gaps:
    - `PhotonProductionDataSaver.__init__()` parameters (line 1502)
    - `PhotonProductionDataSaver.__save()` parameters (line 1573)
    - `ExperimentalAutomationRunner` methods
    - `_ChannelSequence` internals and `DaqSequence.update_time_steps()` (lines 97–127)
    - Helper functions `to_bool()`, `to_int_list()`, `to_float_tuple()`, `to_int_tuple()`
      in `config_readers.py` (lines 82–100)

28. Add docstrings to undocumented classes and methods:
    - `DaqReader.__init__()`, `DaqWriter.__init__()`, `ConfigWriter.__init__()`
    - `buffered_data_handler.py`: `__analyse_buffer()`, `start_polling_queue()`,
      `stop_polling_queue()`
    - Most `__init__` methods in `experimental_configs.py`

29. Add `__all__` exports to modules in `classes/` and `instruments/` to make the public API
    explicit.

30. `instruments/protocols.py` — `DAQControllerProtocol` is missing
    `get_channel_number_name_dict()` and `get_channel_calibration_dict()`, both of which are
    used by the UI. Add them to the protocol.

### Testing

31. Add tests for `daq.py` — `DAQChannel`, `DAQController`, `DAQCard`, and `DAQDio` are
    completely untested.

32. Add tests for `buffered_data_handler.py` — including the threading bug fix.

33. Add smoke tests for `instruments/dummy.py` — verify all dummy implementations satisfy
    their respective protocols.

34. Add tests for `rabi_voltage_converter.py`.

35. Add tests for `Waveform` class in `experimental_configs.py` — CSV parsing, modulation,
    and phase jump logic have significant complexity but no dedicated tests.

36. Expand `test_experimental_runner.py` to cover `PhotonProductionExperiment`,
    `AbsorbtionImagingExperiment`, `MotFluoresceSweepExperiment`,
    `PhotonProductionDataSaver`, and `ExperimentalAutomationRunner`.

37. Add tests for `ExperimentalAutomationReader`, `ConfigWriter`, `DaqWriter`, and
    `SequenceWriter` in the config readers.

38. Add edge-case tests for `DaqSequence`: `update_time_steps()`,
    `get_channel_values_at_time()`, and the `InvalidSequenceChannelError` path.

### Architecture

39. Create a `CameraConfiguration` dataclass to replace the raw `cam_dict` dict used in
    `MotFluoresceConfiguration` (line 556). This follows the pattern already established by
    `ScopeConfiguration`.

40. Introduce custom exception classes (e.g. `ConfigValidationError`,
    `HardwareConnectionError`, `ExperimentStateError`) instead of using bare `Exception` or
    generic `RuntimeError` throughout the codebase.

41. Review broad `except Exception` catches in `experimental_runner.py` (lines 1231, 1376,
    1441, 1487) — these log errors but silently swallow them. Consider re-raising or at
    least logging full tracebacks so failures are not hidden.