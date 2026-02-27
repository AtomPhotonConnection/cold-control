# Cold Control – Test Suite

## Running the tests

All tests must be run inside the **`cold-control` conda environment**:

```bash
conda activate cold-control
```

Then, from the project root:

```bash
# Run everything
python -m pytest -v

# Run a single file
python -m pytest tests/test_daq_sequence.py -v

# Run a single test by name (substring match)
python -m pytest -v -k "test_ramp_linear"

# Stop on first failure
python -m pytest -x -v
```

pytest is configured in `pyproject.toml` (`testpaths = ["tests"]`), so you never need to specify the `tests/` directory explicitly.

---

## Test files

### `conftest.py` — shared fixtures

Provides pytest fixtures that any test file can use by requesting them as function arguments. No import needed.

| Fixture | What it creates |
|---|---|
| `basic_seq` | `DaqSequence(n_samples=100, t_step=10)` with ch 0 flat at 0 V and ch 1 flat at 5 V |
| `dummy_daq` | `DummyDAQController` with two channels (no real hardware) |
| `mot_config_no_hw` | `MotFluoresceConfiguration` with no scope, AWG, or camera; `mot_reload=0`, `iterations=1` |
| `mot_config_with_scope` | Same as above but with a minimal `ScopeConfiguration` (`use_scope=True`) |
| `minimal_scope_config` | A bare `ScopeConfiguration` (channel 1, 1 GHz sample rate) |

---

### `test_daq_sequence.py` — `DaqSequence` and `_ChannelSequence`

**No hardware required.** Pure logic tests.

| Group | Tests | What is verified |
|---|---|---|
| A – Basics | 8 | `get_length()`, `get_time_steps()`, `add_channel_seq()`, `get_channel_nums()` ordering, `get_array()` shape, `get_tv_pairs()` content |
| B – Interpolation | 4 | `FLAT` holds a constant value; `RAMP` is monotone and reaches the target voltage; `FLAT→RAMP` and step-change `FLAT→FLAT` transitions |
| C – Time queries | 6 | `get_channel_values_at_time()` at t=0 and t=end; `ValueError` for t<0 and t>length; `ch_nums` filter and ordering |
| D – Validation | 6 | `update_channel()` succeeds and reverts on failure; start time ≠ 0 raises; time beyond length raises; `update_time_steps()` rolls back on failure; `MultipleInvalidSequenceChannelError` carries channel list |
| E – `IntervalStyle` | 4 | `to_string`/`from_string` round-trip; case-insensitive parsing; `get_all()` completeness; FLAT ≠ RAMP |

Total: **29 tests**, all passing.

---

### `test_experimental_runner.py` — `MotFluoresceExperiment`

**No hardware required.** Uses `DummyDAQController` and (for scope tests) `DummyOscilloscopeManager` via `development_mode=True`.

| Group | Tests | What is verified |
|---|---|---|
| A – DAQ control | 4 | `daq_cards_on()` records prior state and enables output; `daq_cards_off()` restores to off; `run_in_thread(start_thread=False)` returns an unstarted `threading.Thread` with the expected name |
| B – Hardware flags | 3 | `with_scope/awg/cam` are all `False` when config has no hardware; `with_scope=True` when a `ScopeConfiguration` is provided; `iterations` and `mot_reload` stored correctly |
| C – `configure()` | 3 | No-hardware `configure()` does not raise; scope configure in `development_mode` creates a `DummyOscilloscopeManager`; sequence is loaded onto the DAQ controller |
| D – Thread execution | 2 | Full `run()` (no-hardware, 1 iteration, 0 ms reload) completes within 5 s; scope + `development_mode` experiment also completes within 10 s |

Total: **12 tests**, all passing.

---

### Pre-existing test files

These three files were written before pytest was adopted and use plain `assert` + `print` statements. pytest discovers and runs them automatically — they are compatible.

These tests can also be used to test config files to make sure they are functional.

| File | Module under test | Status |
|---|---|---|
| `test_awg_config_reader.py` | `AwgConfigReader`, `Waveform`, `AwgConfiguration` | 20 pass |
| `test_experiment_config_reader.py` | `ExperimentConfigReader`, `MotFluoresceConfiguration` sweep/scope/AWG nesting | 11 pass |
| `test_scope_config_reader.py` | `ScopeConfigReader`, `ScopeConfiguration` | 3 pass |


---

## Overall status

```
76 collected
76 passed
0 failed
```

---

## Adding new tests

1. **For a new module** — create `tests/test_<module_name>.py`.
2. **Reuse fixtures** from `conftest.py` by naming them as function arguments:
   ```python
   def test_something(basic_seq, dummy_daq):
       ...
   ```
3. **Add new fixtures** to `conftest.py` if they will be shared across multiple test files.
4. **For hardware-dependent code** — pass `development_mode=True` to experiment classes; they will substitute `DummyOscilloscopeManager` / `DummyAWGManager` automatically. For the DAQ, always use the `dummy_daq` fixture from `conftest.py`.
5. **Run after every change:**
   ```bash
   python -m pytest tests/test_<your_file>.py -v
   ```
