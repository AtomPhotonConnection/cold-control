#!/usr/bin/python

import logging
import logging.handlers
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox as tk_message_box
from typing import Any

import classes.ui_styles as ui_styles
from classes.config_readers import ConfigReader, ExperimentConfigReader
from UI_classes.Camera_UI import CameraUI
from UI_classes.DAQ_UI import DaqUI
from UI_classes.Experimental_UI import ExperimentalUI
from UI_classes.Labbook_UI import LabbookUI
from UI_classes.Sequence_UI import DaqSequenceUI

# ---------------------------------------------------------------------------
# Logging setup — writes to a rotating log file in the user's home directory
# (or a lab-specific path if $COLD_CONTROL_LOG_DIR is set) and to stderr.
# ---------------------------------------------------------------------------
_log_dir = Path(
    os.environ.get("COLD_CONTROL_LOG_DIR", str(Path.home() / "cold_control_logs"))
)
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = _log_dir / "cold_control.log"

_root_logger = logging.getLogger()
_root_logger.setLevel(logging.DEBUG)

# Rotating file handler (10 MB per file, keep 5 backups)
_file_handler = logging.handlers.RotatingFileHandler(
    _log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

# Console handler (INFO and above)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))

_root_logger.addHandler(_file_handler)
_root_logger.addHandler(_console_handler)

logger = logging.getLogger(__name__)

# Suppress noisy third-party debug output
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)


class ColdControlUI(tk.Frame):
    """
    The ColdControlUI is the main tkinter frame into which assorted UI's are inset.
    Each if these UI's is responsible for creating, running and closing their own
    element of experimental control.  Namely:

        DAQ_UI: Interfaces with the DAQ cards that control static voltages to
                setup the system and play sequences to run experiments.

        Sequence_UI: Allows the user to load and edit the experimental sequence.

        Camera_UI: Runs the inbuilt camera for monitoring the experiment.

        Labook_UI: Provides access to read and write into the labbooks to document
                   the experiment.
    """

    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        self.master: tk.Misc = parent

        self.config_reader = ConfigReader(str(Path.cwd() / "configs" / "rootConfig.ini"))
        self.development_mode = self.config_reader.is_development_mode()

        self.master.wm_title("Cold Control Heavy")
        self.add_menu()
        self.title = tk.Label(self, text="Cold Control Heavy", font=("Helvetica", 24))

        """Load DAQ channels and cards from the config file.  Set up the DAQ_controller with these."""
        self.daq_config_fname = self.config_reader.get_daq_config_fname()
        self.daq_UI = DaqUI(self, self.daq_config_fname, development_mode=self.development_mode)

        """Load a sequence — prefer from experiment config, fall back to rootConfig."""
        self.experiment_config_fname = self.config_reader.get_experiment_config_fname()
        self.expt_config_reader = ExperimentConfigReader(self.experiment_config_fname)
        try:
            _sequence = self.expt_config_reader.get_sequence()
            self.sequence_fname = self.expt_config_reader.config["sequence_config"]
        except KeyError:
            # Fallback: old-style rootConfig with sequence_filename (emits DeprecationWarning)
            self.sequence_fname = self.config_reader.get_sequence_fname()
            _sequence = None  # Sequence_UI will load from fname

        self.sequence_ui = DaqSequenceUI(
            self,
            self.sequence_fname,
            self.daq_UI.daq_controller.get_channel_number_name_dict(only_visible=False),
            self.daq_UI.daq_controller.get_channel_calibration_dict(),
            hidden=True,
        )

        """Start up the camera UI."""
        self.camera_UI = CameraUI(self, ic_imaging_control=None)
        self.camera_live = (
            self.camera_UI.is_live
        )  # monitors status of camera to prevent taking photos while camera is live

        """Set up the experimental UI with pre-configured defaults from the appropriate config files."""
        self.absorbtion_imaging_config_fname = (
            self.config_reader.get_absorbtion_imaging_config_fname()
        )
        self.experimental_UI = ExperimentalUI(
            self,
            self.daq_UI,
            self.sequence_ui,
            self.experiment_config_fname,
            self.absorbtion_imaging_config_fname,
            ic_imaging_control=self.camera_UI.ic_ic,
            development_mode=self.development_mode,
        )

        """Initialise the labook UI"""
        self.labbook_UI = LabbookUI(self)

        """Configure the interface and place the displays for each UI appropriately."""
        self.grid_columnconfigure(0, weight=1, pad=3, uniform="cols")
        self.grid_columnconfigure(1, weight=1, pad=3, uniform="cols")
        self.grid_columnconfigure(2, weight=1, pad=3, uniform="cols")
        self.grid_columnconfigure(3, weight=1, pad=3, uniform="cols")

        grid_opts: dict[str, Any] = {"padx": 10, "pady": 10}

        self.title.grid(row=0, column=0, columnspan=3, **grid_opts)
        self.daq_UI.grid(row=1, column=1, columnspan=2, sticky=tk.N + tk.E + tk.W, **grid_opts)
        self.experimental_UI.grid(row=2, column=1, columnspan=2, sticky=tk.N)
        self.camera_UI.grid(row=1, column=0, sticky=tk.N + tk.E + tk.W)
        self.labbook_UI.grid(row=1, column=3, sticky=tk.N + tk.E + tk.W)

        """Bind closing the app to a clean up method."""
        root.protocol("WM_DELETE_WINDOW", self.on_exit)

    def add_menu(self):
        """Create a pulldown menu, and add it to the menu bar"""
        menubar = tk.Menu(self.master)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open", command=lambda: None)
        filemenu.add_command(label="Save", command=lambda: None)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.on_exit)
        menubar.add_cascade(label="File", menu=filemenu)

        self.master.config(menu=menubar)  # type: ignore

    def on_exit(self):
        """
        Called on closing ColdControl.  Confirms the exit and safely closes the various UI's.
        """

        exit_confirmation = tk_message_box.askquestion(
            "Please confirm exit",
            "Are you sure you want to close Cold Control?\nThis will release all DAQ cards and exit the program - unsaved information will be lost?",
            icon="warning",
        )
        if exit_confirmation == "yes":
            logger.info("Disconnecting from AWG...")
            self.experimental_UI.exit_run_tones()
            logger.info("Closing camera connections...")
            self.camera_UI.close_cameras()
            logger.info("All camera connections closed.")
            logger.info("Releasing DAQ cards...")
            if not self.development_mode:
                self.daq_UI.daq_controller.release_all()
            logger.info("All cards released.")
            logger.info("Saving labbook...")
            self.labbook_UI.write()
            logger.info("Labbook saved.")
            root.destroy()
            logger.info("Cold Control closed - bye!")


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1600x800")
    ui_styles.configure_styles()
    ColdControlUI(root).pack(fill="both", expand=True)
    root.mainloop()
