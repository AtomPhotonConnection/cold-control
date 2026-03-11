"""
Created on 13 Aug 2016

@author: apc
"""

import math
import time
import tkinter as tk
from tkinter import messagebox as tk_message_box
from tkinter import simpledialog
from typing import Any, Literal

from classes.config_readers import (
    ExperimentConfigReader,
)
from classes.daq import DAQDio
from classes.experimental_configs import (
    MotFluoresceConfiguration,
    MotFluoresceConfigurationSweep,
    MotFluorescenceAlignmentConfiguration,
    PhotonProductionConfiguration,
)
from classes.experimental_runner import (
    AbsorbtionImagingExperiment,
    GenericExperiment,
    MotFluoresceExperiment,
    MotFluorescenceAlignmentExperiment,
    MotFluoresceSweepExperiment,
    PhotonProductionExperiment,
)

try:
    from instruments.WX218x.awg_manager import AWGManager
except (ImportError, ModuleNotFoundError):
    AWGManager = None  # type: ignore[assignment, misc]
from UI_classes.DAQ_UI import DaqUI
from UI_classes.Sequence_UI import DaqSequenceUI
from UI_classes.ToolTip_UI import ToolTip
from UI_classes.UI_helpers import ImageButton, load_icon

AWG_TRIG_BUTTON = False


# =======================================================================================
# MARK: Experimental UI
# =======================================================================================
class ExperimentalUI(tk.LabelFrame):
    def __init__(
        self,
        parent,
        daq_ui: DaqUI,
        sequence_ui: DaqSequenceUI,
        experiment_config_fname,
        absorbtion_imaging_config_fname,
        ic_imaging_control=None,
        text="Experimental Actions",
        font=("Helvetica", 16),
        development_mode=False,
        **kwargs,
    ):
        tk.LabelFrame.__init__(self, parent, text=text, font=font, **kwargs)

        self.parent = parent
        self.daq_ui = daq_ui
        self.sequence_ui = sequence_ui
        self.absorbtion_imaging_config = ExperimentConfigReader(
            absorbtion_imaging_config_fname
        ).get_absorbtion_imaging_configuration()
        self.expt_config_reader = ExperimentConfigReader(experiment_config_fname)
        self.loaded_experiment_config = self.expt_config_reader.get_correct_config()
        self.ic_ic = ic_imaging_control
        self.development_mode = development_mode

        self._create_experiment_buttons()
        self._create_absorption_imaging_buttons()
        self._create_flash_channel_controls()
        self._create_run_tones_frame()
        self._layout_grid()

    # ------------------------------------------------------------------
    # __init__ helpers
    # ------------------------------------------------------------------

    def _create_experiment_buttons(self):
        """Create the view-sequence, execute-experiment, and config buttons."""
        butt_opts = {"font": ("Helvetica", 12), "height": 25, "width": 150, "compound": tk.LEFT}

        icon = load_icon("icons/graph_icon.png")
        self.view_sequence_button = ImageButton(
            self,
            image=icon,
            text="View sequence",
            command=self.open_sequence_viewer,
            background="green4",
            **butt_opts,
        )
        self.view_sequence_button.image_ref = icon

        icon = load_icon("icons/play_icon.png")
        self.execute_experiment_button = ImageButton(
            self,
            image=icon,
            text="Execute experiment",
            command=self.execute_experiment,
            background="green2",
            **butt_opts,
        )
        self.execute_experiment_button.image_ref = icon

        icon = load_icon("icons/config_icon.png")
        self.configure_photon_production_button = ImageButton(
            self,
            image=icon,
            width=25,
            height=25,
            command=self.experiment_config_button,
            background="green2",
        )
        self.configure_photon_production_button.image_ref = icon

        if isinstance(
            self.loaded_experiment_config,
            (MotFluoresceConfigurationSweep, MotFluorescenceAlignmentConfiguration),
        ):
            cfg = self.loaded_experiment_config.base_config
        else:
            cfg = self.loaded_experiment_config

        self.total_iterations_frame = ExperimentalParamFrame(
            self,
            "Num. iterations",
            initial_value=cfg.iterations,
            data_type=int,
            help_text="The number of times the experimental sequence will be run.",
            action=lambda entry_value: cfg.set_iterations(entry_value),
        )
        self.reload_time_frame = ExperimentalParamFrame(
            self,
            "MOT reload time (ms):",
            initial_value=cfg.mot_reload,
            data_type=float,
            help_text="The delay between successive iterations.",
            action=lambda entry_value: cfg.set_mot_reload(entry_value),
        )

    def _create_absorption_imaging_buttons(self):
        """Create the absorption-imaging run/test/config buttons."""
        butt_opts = {"font": ("Helvetica", 12), "height": 25, "width": 150, "compound": tk.LEFT}

        icon = load_icon("icons/play_icon.png")
        self.run_abs_img_button = ImageButton(
            self,
            image=icon,
            text="Run abs. imaging",
            command=lambda: self.run_absorption_imaging(),
            background="deep sky blue",
            **butt_opts,
        )
        self.run_abs_img_button.image_ref = icon
        self.test_bkg_button = ImageButton(
            self,
            image=icon,
            text="Test background",
            command=lambda: self.run_absorption_imaging(bkg_test=True),
            background="light sky blue",
            **butt_opts,
        )
        self.test_bkg_button.image_ref = icon

        icon = load_icon("icons/config_icon.png")
        self.configure_abs_img_button = ImageButton(
            self,
            image=icon,
            width=25,
            height=25,
            command=self.absorption_imaging_config_button,
            background="deep sky blue",
        )
        self.configure_abs_img_button.image_ref = icon

    def _create_flash_channel_controls(self):
        """Create the flash-channel button, config button, and default config."""
        butt_opts = {"font": ("Helvetica", 12), "height": 25, "width": 150, "compound": tk.LEFT}

        icon = load_icon("icons/play_icon.png")
        self.flash_channel_button = ImageButton(
            self,
            image=icon,
            text="Flash channel",
            command=self.flash_channel,
            background="light salmon",
            **butt_opts,
        )
        self.flash_channel_button.image_ref = icon

        icon = load_icon("icons/config_icon.png")
        self.configure_flash_channel_button = ImageButton(
            self,
            image=icon,
            width=25,
            height=25,
            command=self.configure_flash_channel,
            background="light salmon",
        )
        self.configure_flash_channel_button.image_ref = icon

        self.flash_channel_config: dict[str, Any] = {
            "channel": -1,
            "duration": 1,
            "low_val": 0,
            "high_val": 10,
            "repeats": 10,
        }

    def _create_run_tones_frame(self):
        """Create the run-tones sub-frame with per-channel frequency entries and toggle buttons."""
        self.run_tones_frame = rtf = tk.LabelFrame(self, text="Run tones", font=("Helvetica", 12))

        self.run_tone_awg = None
        self.run_tone_freqs = [60.8558 * 10**6, 80 * 10**6, 54.8558 * 10**6, 10 * 10**6, 2.6]
        self.run_tone_output_states = [False, False, False, False, False]
        self.run_tone_buttons: dict[int, tk.Button | None] = {
            0: None,
            1: None,
            2: None,
            3: None,
            4: None,
        }

        self.on_icon = load_icon("icons/toggle_on_icon.png", size=(25, 20))
        self.off_icon = load_icon("icons/toggle_off_icon.png", size=(25, 20))

        def set_run_tone_freq(ch, freq):
            if ch == 4:
                self.run_tone_freqs[ch] = freq
            else:
                self.run_tone_freqs[ch] = freq * 10**6

        rtf_grid_opts = {"padx": 5, "pady": 2, "sticky": tk.E + tk.W}
        for i in range(4):
            if AWG_TRIG_BUTTON:
                run_tone_freq_frame = ExperimentalParamFrame(
                    rtf,
                    "AWG trig. Amplitude (V)",
                    initial_value=self.run_tone_freqs[i],
                    data_type=float,
                    help_text="The AWG trigger amplitude in V.",
                    action=lambda entry_value, ch=i, f=set_run_tone_freq: f(ch, entry_value),
                )
            else:
                run_tone_freq_frame = ExperimentalParamFrame(
                    rtf,
                    f"channel{i + 1} freq (MHz)",
                    initial_value=self.run_tone_freqs[i] * 10**-6,
                    data_type=float,
                    help_text="The run tone frequency in MHz.",
                    action=lambda entry_value, ch=i, f=set_run_tone_freq: f(ch, entry_value),
                )

            toggle_run_tone_button = tk.Button(
                rtf, image=self.off_icon, background="red", relief=tk.RAISED, width=28
            )
            toggle_run_tone_button.config(
                command=lambda button=toggle_run_tone_button, i_ch=i: self.toggle_run_tone(
                    button, i_ch
                )
            )
            self.run_tone_buttons[i] = toggle_run_tone_button

            run_tone_freq_frame.grid(row=i, column=0, **rtf_grid_opts)
            toggle_run_tone_button.grid(row=i, column=1, **rtf_grid_opts)

        rtf.grid_columnconfigure(0, weight=1)
        rtf.grid_columnconfigure(1, weight=1)

    def _layout_grid(self):
        """Arrange all widgets in the grid."""
        grid_opts = {"padx": 5, "pady": 2, "sticky": tk.E + tk.W}

        self.view_sequence_button.grid(row=0, column=0, **grid_opts)
        self.execute_experiment_button.grid(row=1, column=0, **grid_opts)
        self.configure_photon_production_button.grid(row=1, column=1, **grid_opts)
        self.total_iterations_frame.grid(row=2, column=0, **grid_opts)
        self.reload_time_frame.grid(row=3, column=0, **grid_opts)

        self.test_bkg_button.grid(row=0, column=2, **grid_opts)
        self.run_abs_img_button.grid(row=1, column=2, **grid_opts)
        self.configure_abs_img_button.grid(row=1, column=3, **grid_opts)
        self.flash_channel_button.grid(row=2, column=2, **grid_opts)
        self.configure_flash_channel_button.grid(row=2, column=3, **grid_opts)

        self.grid_columnconfigure(0, weight=1, uniform="button_col")
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1, uniform="button_col")
        self.grid_columnconfigure(3, weight=1)
        self.grid_columnconfigure(4, weight=1)

        self.run_tones_frame.grid(row=0, column=4, rowspan=3, **grid_opts)

    def open_sequence_viewer(self):
        if (
            self.sequence_ui.configured_channel_labels
            != self.daq_ui.daq_controller.get_channel_number_name_dict(only_visible=False)
        ):
            self.sequence_ui.configure_for_new_channel_labels(
                self.daq_ui.daq_controller.get_channel_number_name_dict(only_visible=False)
            )
        if (
            self.sequence_ui.configured_channel_calibrations
            != self.daq_ui.daq_controller.get_channel_calibration_dict()
        ):
            self.sequence_ui.configure_for_new_channel_calibrations(
                self.daq_ui.daq_controller.get_channel_calibration_dict()
            )
        self.sequence_ui.open_window()

    def run_experiment(
        self, loaded_experiment: GenericExperiment, live_ui=True, auto_close_live_ui=False
    ):
        """
        Run a photon production experiment. There is a some layered architecture here to be aware of if you
        change code (threading can cause very confused computers if done wrong...).  Basically we create two
        objects:
            1. PhotonProductionExperiment - this runner knows nothing about the UI, it simply configures the
                instruments (.configure()), runs the experiment (.run()/.run_in_thread()), and tidies up after
                itself (.close()).  If we use .run() the program holds until the run() method returns (i.e. we
                can not stop the experiment, poll it on-the-fly etc).  run_in_thead runs the same code in a
                separate thread, releasing the main thread (this one!) to keep going.  In this case it is vital
                we wait for the experimental thread to terminate before we try to close the experiment.  This
                is done with the <Thread object>.join() method.
            2. Photon_production_live_UI - this is a top level window for on the fly control/analysis of
                an experiment.  It takes a PhotonProductionExperiment in order to either
                    - tell it to stop running / change the number of iterations to run
                    - poll it for new data, then use this to update the UI.
        Note for completeness: to avoid timing issues between taking/saving the data, the PhotonProductionExperiment
        spawns a new thread to save every iterations data to file.
        """
        experiment_live_ui = None

        if live_ui:
            assert isinstance(loaded_experiment, PhotonProductionExperiment), (
                "Live UI only works with PhotonProductionExperiment objects."
            )
            experiment_live_ui = PhotonProductionLiveUI(
                self, photon_production_experiment=loaded_experiment, auto_close=auto_close_live_ui
            )

        experiment_thread = loaded_experiment.run_in_thread()

        # Small delay to ensure the photon_production_experiment is flagged as live before the UI starts polling it.
        # Otherwise the UI can think it's already over and not update!
        time.sleep(0.1)
        if live_ui and experiment_live_ui is not None:
            experiment_live_ui.poll_live_data()
            # Wait for the live window to close!
            self.winfo_toplevel().wait_window(experiment_live_ui)
            # Wait for the experimental thread to finish - though if the window is
            # shut the photon_production_experiment really should be done!
            experiment_thread.join()
        # If there is no live UI, the experiment thread manages its own lifecycle.

    def execute_experiment(self, live_ui=True, auto_close_live_ui=False):
        """
        Function to run experiments when the "Run experiment" button is pressed.
        """
        # If run tone is on, turn it off!
        for state, button in zip(
            self.run_tone_output_states, self.run_tone_buttons.values(), strict=True
        ):
            if state and button is not None:
                button.invoke()

        if isinstance(self.loaded_experiment_config, PhotonProductionConfiguration):
            # If the experiment loaded is a photon production experiment, run the code as normal
            experiment = PhotonProductionExperiment(
                daq_controller=self.daq_ui.daq_controller,
                sequence=self.sequence_ui.sequence,
                photon_production_configuration=self.loaded_experiment_config,
                development_mode=self.development_mode,
            )

        elif isinstance(self.loaded_experiment_config, MotFluoresceConfiguration):
            if self.loaded_experiment_config.use_cam:
                if self.parent.camera_live:
                    tk_message_box.showwarning(
                        "Error",
                        "Can't run an absorption imaging experiment\n while the camera is running.",
                    )
                    return
                camera_control = self.ic_ic
            else:
                camera_control = None

            experiment = MotFluoresceExperiment(
                daq_controller=self.daq_ui.daq_controller,
                sequence=self.sequence_ui.sequence,
                mot_fluoresce_configuration=self.loaded_experiment_config,
                ic_imaging_control=camera_control,
                sweep=False,
                development_mode=self.development_mode,
            )
            # The mot fluoresce experiment is a special case where the Live UI is not set up.
            live_ui = False
            auto_close_live_ui = False

        elif isinstance(self.loaded_experiment_config, MotFluoresceConfigurationSweep):
            # Sweep config loaded â€” run the full sweep experiment
            sweep_experiment = MotFluoresceSweepExperiment(
                self.loaded_experiment_config,
                self.daq_ui.daq_controller,
                development_mode=self.development_mode,
            )
            print("Running MOT Fluoresce Sweep experiment")
            sweep_experiment.run_in_thread()
            return

        elif isinstance(self.loaded_experiment_config, MotFluorescenceAlignmentConfiguration):
            # Alignment config loaded â€” run the alignment loop with live UI
            alignment_experiment = MotFluorescenceAlignmentExperiment(
                self.loaded_experiment_config,
                self.daq_ui.daq_controller,
                development_mode=self.development_mode,
            )
            print("Running MOT Fluorescence Alignment experiment")
            experiment_thread = alignment_experiment.run_in_thread()
            time.sleep(0.1)
            alignment_ui = AlignmentLiveUI(self, alignment_experiment)
            alignment_ui.poll_results()
            self.winfo_toplevel().wait_window(alignment_ui)
            experiment_thread.join()
            return

        else:
            raise Exception(
                "Invalid experiment type specified.  Must be either PhotonProductionExperiment or MotFluoresceExperiment."
            )
        self.run_experiment(experiment, live_ui, auto_close_live_ui)

    def run_absorption_imaging(self, bkg_test=False):
        if self.parent.camera_live:
            tk_message_box.showwarning(
                "Error", "Can't run an absorption imaging experiment\n while the camera is running."
            )
            return

        assert self.ic_ic, "No IC Imaging Control provided, can't run absobtion imaging experiment."

        experiment = AbsorbtionImagingExperiment(
            daq_controller=self.daq_ui.daq_controller,
            sequence=self.sequence_ui.sequence,
            absorbtion_imaging_configuration=self.absorbtion_imaging_config,
            ic_imaging_control=self.ic_ic,
        )
        experiment.run(bkg_test=bkg_test)
        if self.absorbtion_imaging_config.review_processed_images or bkg_test:
            absorption_imaging_review_ui = AbsorptionImagingReviewUI(self, experiment)
            self.winfo_toplevel().wait_window(absorption_imaging_review_ui)

    def toggle_run_tone(self, button: tk.Button, i_ch):
        if i_ch == 4:
            daq_controller = self.daq_ui.daq_controller
            daq_controller.update_channel_value(14, 2.485)
            daq_controller.update_channel_value(8, 0.0048)
            for _i in range(10):
                daq_controller.continuousOutput = True
                daq_controller.update_channel_value(
                    22, 2.0
                )  # for manual control of amplitude input (in V)
                daq_controller.update_channel_value(22, 0)
                time.sleep(0.5)
            return
        else:
            channel = i_ch + 1

        if not self.run_tone_output_states[i_ch]:
            if self.run_tone_awg is None:
                if self.development_mode:
                    from instruments.dummy import DummyAWGManager

                    self.run_tone_awg = awg = DummyAWGManager()
                else:
                    assert AWGManager is not None, (
                        "AWGManager class not found.  Make sure the WX218x AWG module is correctly installed."
                    )
                    self.run_tone_awg = awg = AWGManager()
                for i in [1, 2, 3, 4]:
                    awg.disable_channel(i)

                awg.set_sample_rate(1.25 * 10**9)

            else:
                awg = self.run_tone_awg

            freq = self.run_tone_freqs[i_ch]

            print(f"Sending run tone to {channel} at {freq * 10**-6}MHz")

            # reduce amplitude so as not to saturate the AOM
            awg.play_sine_wave(channel, freq, amplitude=0.5)
            awg.set_continuous(True)
            awg.enable_channel(channel)

            self.run_tone_output_states[i_ch] = True

            button.configure(bg="green", image=self.on_icon, relief=tk.SUNKEN)

        else:
            assert self.run_tone_awg, "AWG not connected, can't turn off run tone!"
            print(f"Turning off run tone on {channel}")
            self.run_tone_awg.disable_channel(channel)
            self.run_tone_output_states[i_ch] = False

            if True not in self.run_tone_output_states:
                # Reset the awg operation mode - this is required for sequences to run properly after using a run tone.
                for _channel in [1, 2, 3, 4]:
                    self.run_tone_awg.set_output_mode("USER")

                self.run_tone_awg.close()
                print("Connection to AWG closed.")
                self.run_tone_awg = None

            button.configure(bg="red", image=self.off_icon, relief=tk.RAISED)

    def exit_run_tones(self):
        """
        Function to turn off all run tones and close connection to the awg when cold control is exited.
        Failure to do this causes problems for running sequences on the awg.
        """

        if self.run_tone_awg is None:
            # AWG not connected
            print("No connection to AWG was opened")
            return

        # Turns off run tones on all active channels
        for i, channel in enumerate([1, 2, 3, 4]):
            if self.run_tone_output_states[i]:
                print(f"Turning off run tone on {channel}")
                self.run_tone_awg.disable_channel(channel)
                self.run_tone_output_states[i] = False
                self.run_tone_awg.set_output_mode("USER")

        # Disconnects from awg
        self.run_tone_awg.close()
        print("Connection to AWG closed.")
        self.run_tone_awg = None

    def experiment_config_button(self):
        config_ui = GenericExperimentConfigUi(
            self,
            expt_config=self.loaded_experiment_config,
            expt_config_reader=self.expt_config_reader,
        )
        self.winfo_toplevel().wait_window(config_ui.top)
        config_reader = config_ui.conf_reader
        expt_config = config_ui.experiment_config

        # If the user asked for their changes to be applied, set the config accordingly.
        if config_ui.apply_changes:
            self.loaded_experiment_config = expt_config
            if config_reader is not None:
                self.expt_config_reader = config_reader

        # Update UI fields - sweep configs store experiment params on base_config
        cfg = self.loaded_experiment_config
        if isinstance(cfg, (MotFluoresceConfigurationSweep, MotFluorescenceAlignmentConfiguration)):
            cfg = cfg.base_config
        self.total_iterations_frame.entryWid.delete(0, tk.END)
        self.total_iterations_frame.entryWid.insert(0, cfg.iterations)
        self.reload_time_frame.entryWid.delete(0, tk.END)
        self.reload_time_frame.entryWid.insert(0, cfg.mot_reload)

    def absorption_imaging_config_button(self):
        config_ui = AbsorptionImagingConfigurationUi(
            self,
            absorbtion_imaging_configuration=self.absorbtion_imaging_config,
            daq_controller=self.daq_ui.daq_controller,
            sequence_length=self.sequence_ui.sequence.get_length(),
            sequence_t_step=self.sequence_ui.sequence.t_step,
        )
        self.winfo_toplevel().wait_window(config_ui.top)
        # If the user asked for their changes to be applied, set the absorbtion imaging config accordingly.
        if config_ui.apply_changes:
            self.absorbtion_imaging_config = config_ui.config

    def flash_channel(self):
        channel = self.flash_channel_config["channel"]
        if channel == -1:
            tk_message_box.showwarning("Error", "No channel to flash configured.")
            return

        duration = self.flash_channel_config["duration"]
        repeats = self.flash_channel_config["repeats"]

        if channel == "dio":
            dio: DAQDio = self.daq_ui.daq_controller.get_dios()[
                0
            ]  # Assuming we flash the first DIO
            for i in range(repeats):
                dio.toggle_state()
                time.sleep(duration)
                print(f"Flash number {i + 1} complete for DIO channel {dio.dio_name}")
            return

        num_name_dict = self.daq_ui.daq_controller.get_channel_number_name_dict()

        print(f"Flashing channel {channel}, {num_name_dict[channel]}")

        low_val = self.flash_channel_config["low_val"]
        high_val = self.flash_channel_config["high_val"]

        for i in range(repeats):
            self.daq_ui.daq_controller.update_channel_value(channel, low_val)
            time.sleep(duration)
            self.daq_ui.daq_controller.update_channel_value(channel, high_val)
            time.sleep(duration)
            print(f"Flash number {i + 1} complete")

    def configure_flash_channel(self):
        print("Configuring flash channel")
        inputs = simpledialog.askstring(
            "Flash channel configuration",
            "Enter channel, duration (s), low value, high value, repeats (comma separated):",
        )
        if inputs:
            inputs = inputs.split(",")
            if len(inputs) != 5:
                tk_message_box.showwarning("Error", "Invalid number of inputs.")
                return
            try:
                duration = float(inputs[1])
                low_val = float(inputs[2])
                high_val = float(inputs[3])
                repeats = int(inputs[4])
                channel = "dio" if inputs[0] == "dio" else int(inputs[0])
            except ValueError:
                tk_message_box.showwarning("Error", "Invalid input format.")
                return

            self.flash_channel_config["channel"] = channel
            self.flash_channel_config["duration"] = duration
            self.flash_channel_config["low_val"] = low_val
            self.flash_channel_config["high_val"] = high_val
            self.flash_channel_config["repeats"] = repeats


class ExperimentalParamFrame(tk.Frame):
    """
    A sub-class of a Tkinter.Frame to create entry widgets and decorations for setting experimental numerical values.
        label - The text to label the entry widget with
        initVal - The initial value of the entry
        dataType - The type expected by the entry (used for validation). Must be int or float
        helpText - The info displayed when the user hovers the mouse.
        action - A function called with the value of the widget as it's only arg, when a valid entry
                 is made. If no function is to be called, set action to None.
                 e.g. action = lambda entry_value: myAction(entry_value)
    """

    def __init__(
        self,
        parent,
        label,
        initial_value=1,
        data_type: type = int,
        help_text=None,
        action=None,
        state: Literal["normal", "disabled", "readonly"] = tk.NORMAL,
        **kwargs,
    ):
        tk.Frame.__init__(self, parent, **kwargs)

        self.label = label
        self.dataType = data_type
        self.value = initial_value

        self.entryWid = tk.Entry(self, width=7)
        self.entryWid.insert(0, str(self.value))
        self.entryWid.configure(state=state)

        self.labelWid = tk.Label(self, width=20, text=self.label, anchor="w")

        self.entryWid.bind("<FocusOut>", self.validate)
        self.entryWid.bind("<Return>", self.validate)
        self.entryWid.bind("<Up>", self.arrow_key)
        self.entryWid.bind("<Down>", self.arrow_key)

        self.labelWid.grid(row=0, column=0)
        self.entryWid.grid(row=0, column=1)

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1, pad=2)

        if help_text is not None:
            self.tooltip = ToolTip(self, help_text)

        self.action = action

    def update_entry(self, value):
        entry_state = self.entryWid.cget("state")
        self.entryWid.configure(state=tk.NORMAL)
        self.entryWid.delete(0, tk.END)
        self.entryWid.insert(0, value)
        self.entryWid.configure(state=entry_state)
        self.validate()

    def validate(self, params=None):
        """
        Ensure the widget value is in the right number form - if so update the frames value,
        otherwise revert to the last valid entry and flash red to show an error.
        """
        try:
            self.value = self.dataType(self.entryWid.get())
            self.flash("green")
            # Call the action function if one is configured.
            if self.action:
                self.action(self.value)
        except (ValueError, NameError):
            self.entryWid.delete(0, tk.END)
            self.entryWid.insert(0, str(self.value))
            self.flash("red")

    def flash(self, col, length=500):
        """
        Flashes the background of the entry widget a colour (col) for a length of time (length) in ms.
        Usually used during validation to indicate whether the new value entered is valid.
        """
        self.entryWid.config(bg=col)
        self.entryWid.after(length, lambda: self.entryWid.configure(bg="white"))

    def arrow_key(self, event):
        """
        Called when the Up or Down arrow key is pressed.
        Increments the value on the DAQ channel accordingly.
        """
        if self.dataType in (int, float):
            #       Count the number of places between the decimal place in the float and the cursor index
            #       to calculate the order of the incrementation, i.e 0.01,0.1,1,10,...ect.
            #       Try/Except to handle the case when there is no decimal point shown.
            try:
                decimal_index = self.entryWid.get().index(".")
            except ValueError:
                decimal_index = len(self.entryWid.get())
            cursor_index = self.entryWid.index(tk.INSERT)
            increment_order = decimal_index - cursor_index

            # If the increment order is -1 the cursor is on the decimal point so do nothing.
            if increment_order != -1:
                if increment_order < -1:
                    increment_order += 1
                # Caculate the amount to change the value by.  The sign is determined by the key pressed.
                iterator = (
                    math.pow(10, increment_order)
                    if event.keysym == "Up"
                    else -1 * math.pow(10, increment_order)
                )

                current_value = self.entryWid.get()
                # We have to count the number of decimal points of the number and found the iterated
                # value back to this level due to Python's imprecision with floats.
                ndp = current_value[::-1].find(".")
                if ndp < 0:
                    ndp = 0

                self.entryWid.delete(0, tk.END)
                self.entryWid.insert(
                    0, str(self.dataType(round(float(current_value) + iterator, ndp)))
                )
                self.validate(event)
                self.entryWid.icursor(cursor_index)


# ---------------------------------------------------------------------------
# Re-exported from new modules so existing callers still work via this file.
# ---------------------------------------------------------------------------
from UI_classes.absorption_imaging_review_ui import AbsorptionImagingReviewUI  # noqa: E402
from UI_classes.experiment_config_ui import (  # noqa: E402
    AbsorptionImagingConfigurationUi,
    GenericExperimentConfigUi,
)
from UI_classes.experiment_live_ui import (  # noqa: E402
    AlignmentLiveUI,
    PhotonProductionLiveUI,
)
