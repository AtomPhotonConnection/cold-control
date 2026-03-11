"""
Integration-light tests for MotFluoresceExperiment and GenericExperiment.

All tests use DummyDAQController, DummyOscilloscopeManager (in development_mode)
and a MotFluoresceConfiguration built without hardware.  No real instruments needed.

Run with:  pytest tests/test_experimental_runner.py -v
"""

import threading

from classes.experimental_runner import MotFluoresceExperiment, MotFluorescenceAlignmentExperiment
from instruments.dummy import DummyOscilloscopeManager

# ===========================================================================
# Group A - GenericExperiment DAQ control (tested via MotFluoresceExperiment)
# ===========================================================================


class TestGenericExperimentDaqControl:
    def test_daq_cards_on_records_initial_state(self, dummy_daq, basic_seq, mot_config_no_hw):
        """daq_cards_on() stores the previous continuousOutput state."""
        expt = MotFluoresceExperiment(dummy_daq, basic_seq, mot_config_no_hw, development_mode=True)
        assert dummy_daq.continuousOutput is False  # sanity-check starting state

        expt.daq_cards_on()

        # isDaqContinuousOutput should record what it was BEFORE turning on
        assert expt.isDaqContinuousOutput is False
        # DAQ should now be running in continuous output mode
        assert dummy_daq.continuousOutput is True

    def test_daq_cards_off_restores_to_off(self, dummy_daq, basic_seq, mot_config_no_hw):
        """daq_cards_off() reverts continuous output to its original state."""
        expt = MotFluoresceExperiment(dummy_daq, basic_seq, mot_config_no_hw, development_mode=True)
        expt.daq_cards_on()  # turns DAQ on (was off)
        expt.daq_cards_off()  # should turn it back off

        assert dummy_daq.continuousOutput is False

    def test_run_in_thread_returns_thread_object(self, dummy_daq, basic_seq, mot_config_no_hw):
        """run_in_thread(start_thread=False) returns a Thread without starting it."""
        expt = MotFluoresceExperiment(dummy_daq, basic_seq, mot_config_no_hw, development_mode=True)
        t = expt.run_in_thread(start_thread=False)

        assert isinstance(t, threading.Thread)
        assert not t.is_alive()

    def test_run_in_thread_is_named(self, dummy_daq, basic_seq, mot_config_no_hw):
        """The thread returned by run_in_thread has the expected name."""
        expt = MotFluoresceExperiment(dummy_daq, basic_seq, mot_config_no_hw, development_mode=True)
        t = expt.run_in_thread(start_thread=False)
        assert "Cold Control" in t.name


# ===========================================================================
# Group B - MotFluoresceExperiment hardware flags
# ===========================================================================


class TestMotFluoresceExperimentFlags:
    def test_no_hw_all_flags_false(self, dummy_daq, basic_seq, mot_config_no_hw):
        """All hardware flags are False when config has no scope/AWG/camera."""
        expt = MotFluoresceExperiment(dummy_daq, basic_seq, mot_config_no_hw, development_mode=True)
        assert expt.with_scope is False
        assert expt.with_awg is False
        assert expt.with_cam is False

    def test_scope_flag_true_when_scope_config_provided(
        self, dummy_daq, basic_seq, mot_config_with_scope
    ):
        """with_scope is True when a ScopeConfiguration is in the config."""
        expt = MotFluoresceExperiment(
            dummy_daq, basic_seq, mot_config_with_scope, development_mode=True
        )
        assert expt.with_scope is True
        assert expt.with_awg is False
        assert expt.with_cam is False

    def test_construction_stores_iterations_and_mot_reload(
        self, dummy_daq, basic_seq, mot_config_no_hw
    ):
        """Configuration values are stored as experiment attributes."""
        expt = MotFluoresceExperiment(dummy_daq, basic_seq, mot_config_no_hw, development_mode=True)
        assert expt.iterations == mot_config_no_hw.iterations
        assert expt.mot_reload == mot_config_no_hw.mot_reload


# ===========================================================================
# Group C - configure() without and with scope (development_mode)
# ===========================================================================


class TestMotFluoresceExperimentConfigure:
    def test_configure_no_hw_does_not_raise(self, dummy_daq, basic_seq, mot_config_no_hw):
        """configure() completes without error when no hardware is requested."""
        expt = MotFluoresceExperiment(dummy_daq, basic_seq, mot_config_no_hw, development_mode=True)
        expt.configure()
        expt.close()  # restore original DAQ state

    def test_configure_with_scope_dev_mode_uses_dummy_scope(
        self, dummy_daq, basic_seq, mot_config_with_scope
    ):
        """In development_mode, configure() with scope uses DummyOscilloscopeManager."""
        expt = MotFluoresceExperiment(
            dummy_daq, basic_seq, mot_config_with_scope, development_mode=True
        )
        expt.configure()

        assert hasattr(expt, "scope"), "scope attribute must be set after configure()"
        assert isinstance(expt.scope, DummyOscilloscopeManager)

        expt.close()  # ensure cleanup code also runs without error

    def test_configure_loads_sequence_onto_daq(self, dummy_daq, basic_seq, mot_config_no_hw):
        """configure() calls daq_controller.load() exactly once (DummyDAQ logs calls)."""
        load_calls = []
        original_load = dummy_daq.load
        dummy_daq.load = lambda arr: (load_calls.append(arr.shape), original_load(arr))

        expt = MotFluoresceExperiment(dummy_daq, basic_seq, mot_config_no_hw, development_mode=True)
        expt.configure()
        expt.close()

        assert len(load_calls) >= 1, "daq.load() should have been called at least once"
        assert load_calls[0] == basic_seq.get_array().shape


# ===========================================================================
# Group D - run() thread execution
# ===========================================================================


class TestMotFluoresceExperimentThreadExecution:
    def test_run_no_save_thread_completes(self, dummy_daq, basic_seq, mot_config_no_hw):
        """run() with no hardware configured completes within a reasonable time.

        mot_reload=0 and iterations=1 keep the run loop instantaneous.
        A 5-second timeout is very generous for a no-hardware run.
        """
        expt = MotFluoresceExperiment(dummy_daq, basic_seq, mot_config_no_hw, development_mode=True)
        t = expt.run_in_thread(start_thread=True)
        t.join(timeout=5)

        assert not t.is_alive(), (
            "run_in_thread did not finish within 5 seconds for a no-hardware, "
            "0 ms reload, 1-iteration experiment"
        )

    def test_run_with_scope_dev_mode_completes(self, dummy_daq, basic_seq, mot_config_with_scope):
        """run() with scope enabled in development_mode uses DummyScope and completes."""
        expt = MotFluoresceExperiment(
            dummy_daq, basic_seq, mot_config_with_scope, development_mode=True
        )
        t = expt.run_in_thread(start_thread=True)
        t.join(timeout=10)

        assert not t.is_alive(), (
            "Scope experiment did not finish within 10 seconds in development mode"
        )


# ===========================================================================
# Group E - MotFluorescenceAlignmentExperiment
# ===========================================================================


class TestMotFluorescenceAlignmentExperiment:
    def test_stop_sets_flag(self, dummy_daq, alignment_config):
        """stop() sets stop_requested to True."""
        expt = MotFluorescenceAlignmentExperiment(
            alignment_config, dummy_daq, development_mode=True
        )
        assert expt.stop_requested is False
        expt.stop()
        assert expt.stop_requested is True

    def test_run_in_thread_returns_thread(self, dummy_daq, alignment_config):
        """run_in_thread(start_thread=False) returns a Thread without starting it."""
        expt = MotFluorescenceAlignmentExperiment(
            alignment_config, dummy_daq, development_mode=True
        )
        t = expt.run_in_thread(start_thread=False)
        assert isinstance(t, threading.Thread)
        assert not t.is_alive()

    def test_run_in_thread_is_named(self, dummy_daq, alignment_config):
        """The thread returned by run_in_thread has the expected name."""
        expt = MotFluorescenceAlignmentExperiment(
            alignment_config, dummy_daq, development_mode=True
        )
        t = expt.run_in_thread(start_thread=False)
        assert "Alignment" in t.name

    def test_immediate_stop_yields_no_results(self, dummy_daq, alignment_config):
        """If stop() is called before run(), the loop exits with 0 iterations."""
        expt = MotFluorescenceAlignmentExperiment(
            alignment_config, dummy_daq, development_mode=True
        )
        expt.stop()  # pre-set stop flag
        expt.run()  # should exit immediately

        assert expt.shot_count == 0
        assert len(expt.results) == 0
        assert expt.is_running is False

    def test_stop_during_run_exits_loop(self, dummy_daq, alignment_config):
        """Calling stop() from another thread causes run() to finish."""
        expt = MotFluorescenceAlignmentExperiment(
            alignment_config, dummy_daq, development_mode=True
        )
        # Start the experiment, then stop after a short delay
        t = expt.run_in_thread(start_thread=True)
        import time

        time.sleep(0.5)
        expt.stop()
        t.join(timeout=10)

        assert not t.is_alive(), (
            "Alignment experiment did not stop within 10 seconds after stop() was called"
        )
        assert expt.is_running is False
        # At least one iteration should have started (mot_reload=0, iterations=1)
        assert expt.shot_count >= 1
