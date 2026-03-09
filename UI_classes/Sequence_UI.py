"""
Created on 25 Mar 2016

@author: tombarrett
"""

import tkinter as tk

# from tkinter import font as tkFont
from tkinter import filedialog as tk_file_dialog
from tkinter import messagebox as tk_message_box
from tkinter import ttk

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends._backend_tk import NavigationToolbar2Tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# from IPython.core.display import display
# from tkinter.constants import ANCHOR
from PIL import Image, ImageTk

import UI_classes.ToolTip_UI as tooltip

# import wx
from classes.config_readers import SequenceReader, SequenceWriter
from classes.daq_sequence import (
    DaqSequence,
    IntervalStyle,
    InvalidSequenceChannelError,
    MultipleInvalidSequenceChannelError,
)

"""
TODO -
1. Be able to add/remove sequence channels
2. Provide 'sort' option for time channel - sort when re-loading channel to look at it / provide sort button to remove incomplete lines and reorder
3. Implement channel wrapper (e.g. V <--> Hz for AOMs)
4. Sequence: update interval --> sequence speed
"""


class ImageButton(tk.Button):
    """Important class to prevent image being garbage collected.
    Usage:
    self.addButton = ImageButton(..., image=icon)
    self.addButton.image_ref=icon
    """

    image_ref: ImageTk.PhotoImage


class DaqSequenceUI(tk.Toplevel):
    """Seqeuence UI to look after the sequence plotting/editing/loading/saving."""

    def __init__(
        self,
        parent,
        sequence_fname,
        configured_channel_labels=None,
        configured_channel_calibrations=None,
        hidden=True,
    ):
        """parent - parent widget
        sequence - initial sequence to be configured with
        configured_channel_labels - dict. of {channel number:channel label} as currently configured.
        configured_channel_calibrations= - dict. of {channel number:(calibrationUnits, calibrationToVFunc, calibrationFromVFunc)} as currently configured.

        Note - the sequecnce_UI doen't validate that the configured sequence matches the configured DAQ channels
        (for channel limits etc.) as a) sequence validation is performed by the DAQ_controller before it is run
        and b) sequences could be run with different config files."""
        if configured_channel_calibrations is None:
            configured_channel_calibrations = {}
        if configured_channel_labels is None:
            configured_channel_labels = {}
        tk.Toplevel.__init__(self, parent)

        if hidden:
            self.withdraw()

        self.parent = parent
        self.sequence_fname: str = sequence_fname
        print(f"Loading sequence from file: {self.sequence_fname}")
        self.sequence_reader = SequenceReader(self.sequence_fname)
        self.sequence: DaqSequence = self.sequence_reader.load_sequence()
        self.configured_channel_labels: dict = configured_channel_labels
        self.configured_channel_calibrations: dict = configured_channel_calibrations

        self.wm_title("Set sequence")

        self.configure_for_current_sequence()

        # Changes the close button to call my close function.
        self.protocol("WM_DELETE_WINDOW", self.close_window)

    def configure_for_current_sequence(self):
        """This method creates, configures and draws all the elements of the UI that are dependent on the currently loaded sequence (as
        defined by the class variables self.sequence, self.sequence_reader...  Primarily it is just an extension of the __init__ for the
        class however this section of code needs to be run to re-configure the UI for a new sequence if one is loaded."""
        # Destroy any widgets that have already been created (i.e. clear the frame before re-drawing)
        for wid in self.winfo_children():
            wid.destroy()

        self.sequence_channel_labels = self.get_channel_labels(self.configured_channel_labels)

        self.tabs = ttk.Notebook(self)
        self.tabs.enable_traversal()

        self.buttons = self.get_action_buttons()
        self.seqPlot = SequencePlotUI(self, self.sequence, self.sequence_channel_labels)
        self.seqEditor = SequenceEditorUI(self, self.sequence_reader)
        self.chEditor = ChannelEditorUI(
            self,
            self.sequence,
            self.sequence_reader,
            self.sequence_channel_labels,
            self.configured_channel_calibrations,
        )
        self.notesFrame = NotesUI(self, self.sequence_reader)

        self.tabs.add(self.seqEditor, text="Sequence")
        self.tabs.add(self.chEditor, text="Channels")
        self.tabs.add(self.notesFrame, text="Notes")
        self.tabs.select(self.chEditor)

        self.seqPlot.grid(row=0, column=0, columnspan=2, sticky=tk.N + tk.E + tk.S + tk.W)
        self.tabs.grid(row=1, column=0, sticky=tk.N + tk.E + tk.S + tk.W)
        self.buttons.grid(row=1, column=1, sticky=tk.N + tk.E + tk.S + tk.W)

        # Make some rows and columns change size as the window is resized.
        self.grid_columnconfigure(0, weight=4, pad=15)
        self.grid_columnconfigure(1, weight=1, pad=15)
        self.grid_rowconfigure(0, weight=1, pad=5)
        self.grid_rowconfigure(1, weight=1, pad=5)
        self.grid_rowconfigure(2, weight=1, pad=5)

    def configure_for_new_channel_labels(self, configured_channel_labels):
        """Redraws all the elements that use the names of the currently configured channel in the UI.  The intended
        use of this function is to update the UI visually if the use has changed the names of the configured channels."""
        self.configured_channel_labels = configured_channel_labels
        self.sequence_channel_labels = self.get_channel_labels(self.configured_channel_labels)

        self.seqPlot.update_channel_labels(self.sequence_channel_labels)
        self.chEditor.update_channel_labels(self.sequence_channel_labels)

    def configure_for_new_channel_calibrations(self, configured_channel_calibrations):
        """Redraws all the elements that use the calibrations of the currently configured channel in the UI.  The intended
        use of this function is to update the UI visually if the use has changed the calibrations of the configured channels."""
        self.configured_channel_calibrations = configured_channel_calibrations

        self.chEditor.update_channel_calibrations(self.configured_channel_calibrations)

    def get_channel_labels(self, configured_channel_labels):
        """This method takes a dictionary of channel number:labels and matches them to the channel numbers
        expected on the current sequence.  If a channel number is expected but not found, a label is automatically
        created.  If a channel number is given but not expected it is removed from the list."""
        sequence_channel_labels = {}

        for ch_num in self.sequence.get_channel_nums():
            try:
                ch_label = configured_channel_labels[ch_num]
            except KeyError:
                ch_label = "Unconfigured channel"

            sequence_channel_labels[ch_num] = ch_label

        return sequence_channel_labels

    def get_action_buttons(self):
        buttons = tk.Frame(self)

        self.CloseButton = tk.Button(buttons, text="Close", command=self.close_window)
        self.CloseButton.grid(row=1, column=0, padx=5, pady=5, sticky=tk.S + tk.E)

        # self.saveLoadButtons = tk.Frame(buttons)
        # self.LoadButton = tk.Button(
        #     self.saveLoadButtons, text="Load sequence", command=self.loadSeq
        # )
        # self.SaveButton = tk.Button(
        #     self.saveLoadButtons, text="Save sequence", command=self.saveSeq
        # )
        # self.LoadButton.pack(side=tk.TOP, padx=5, pady=5)
        # self.SaveButton.pack(side=tk.TOP, padx=5, pady=5)
        # self.saveLoadButtons.grid(row=0, column=0, padx=5, pady=5, sticky=tk.N + tk.E)

        return buttons

    def load_sequence(self):
        fname = tk_file_dialog.askopenfilename(title="Load a sequence", initialdir="")

        # Check for empty filenames (i.e. when the user cancelled the action)
        if fname != "":
            self.sequence_reader = SequenceReader(fname)
            self.sequence: DaqSequence = self.sequence_reader.load_sequence()

            self.configure_for_current_sequence()

        # Seems to be a tkinter bug that the parent is shown on top after a file dialog - so let's fix that
        self.lift(self.parent)

    def save_sequence(self):
        fname = tk_file_dialog.asksaveasfilename(title="Save a sequence")
        # Check for empyy filenames (i.e. when the user cancelled the acion)
        if fname != "":
            writer = SequenceWriter(fname)
            writer.save(
                self.sequence,
                self.sequence_channel_labels,
                self.seqEditor.global_timings,
                self.notesFrame.get_user_notes(),
            )

        # Seems to be a tkinter bug that the parent is shown on top after a file dialog - so let's fix that
        self.lift(self.parent)

    def open_window(self):
        """Open the window."""
        self.deiconify()
        self.grab_set()

    #         self.wm_attributes("-topmost", True)

    def close_window(self):
        """Close the window."""
        self.grab_release()
        self.parent.focus_set()
        self.withdraw()

    def update_live_sequence_channel(self):
        """The update method triggered by changes in the ChannelEditor_UI"""
        live_ch_num = self.chEditor.livech_num
        tv_pairs, interval_styles = self.chEditor.get_channel_sequence(live_ch_num)
        try:
            self.sequence.update_channel(live_ch_num, tv_pairs, interval_styles)
            self.seqPlot.update_ch_plot(live_ch_num)
        except InvalidSequenceChannelError as err:
            # The new sequence was invalid and the update rejected - refresh the rows
            # for the live channel to reverse the changes made.
            self.chEditor.refresh_rows(live_ch_num)

            # Create a warning label explaining why the change was rejected.
            self.display_warning(str(err), 3000)

    def update_global_timings(self):
        self.chEditor.global_timings = self.seqEditor.global_timings
        for ch_num in self.sequence.get_channel_nums():
            self.chEditor.refresh_rows(ch_num)

    def update_sequence_sampling_configuration(self):

        def reset_changes():
            """local convenience function to simply reset the changes in the Sequence_Editor_UI"""
            n_samples, t_step = self.sequence_reader.get_sequence_init_args()
            self.seqEditor.set_n_samples(n_samples)
            self.seqEditor.set_t_step(t_step)
            self.display_warning(
                "Changes not applied - reverted to the values in the sequence file", 3000
            )

        # If t_new > t_old: ask if you want to extend sequence, if so just add FLAT intervals at end
        # If t_new < t_old: ask if you want to crop sequence.
        new_sequence_length = (self.seqEditor.n_samples - 1) * self.seqEditor.t_step

        # Depending on how long the new sequence is, channels may need to be manually changed.  These changes will be entered in this
        # dictionary to be passed to the update function later.
        channels_to_update = {}
        if new_sequence_length > self.sequence.get_length():
            result = tk_message_box.askquestion(
                "Please confirm changes",
                f"Sequence length will be increased from {self.sequence.get_length()} to {new_sequence_length}. Channels will be set as constant from their current end values to compensate."
                + "\nIs that ok?",
                icon="warning",
            )
            # Seems to be a tkinter bug that the parent is shown on top after this message dialog
            self.lift(self.parent)
            if result == "yes":
                for ch_num in self.sequence.get_channel_nums():
                    # fill in channelsToUpdate dict.
                    tv_pairs, interval_styles = (
                        self.sequence.get_tv_pairs(ch_num),
                        self.sequence.get_v_interval_styles(ch_num),
                    )
                    # If there are more value pairs than interval styles, the last pair was on the final time step of the old sequence.
                    # For the new (longer) sequence this would be invalid, so add another interval style to take this final value and
                    # set it as a constant.
                    if len(tv_pairs) > len(interval_styles):
                        interval_styles.append(IntervalStyle.FLAT)
                        channels_to_update[ch_num] = (tv_pairs, interval_styles)
            else:
                reset_changes()
                return

        elif new_sequence_length < self.sequence.get_length():
            result = tk_message_box.askquestion(
                "Please confirm changes",
                f"Sequence length will be decreased from {self.sequence.get_length()} to {new_sequence_length}. Channels will be cropped with there last time interval being made constant to compensate."
                + "\nIs that ok?",
                icon="warning",
            )
            # Seems to be a tkinter bug that the parent is shown on top after this message dialog
            self.lift(self.parent)
            if result == "yes":
                for ch_num in self.sequence.get_channel_nums():
                    tv_pairs, interval_styles = self.chEditor.get_channel_sequence(ch_num)
                    # Cut any tV pairs that are not outside the sequence length
                    tv_pairs = sorted(
                        [x for x in tv_pairs if x[0] <= new_sequence_length], key=lambda x: x[0]
                    )
                    # If of the remaining pairs, the last pair in on the last timestep of the new sequence,
                    # then the channel is fully specified by just cropping the interval_styles list accordingly.
                    # If not, we need to add a final interval style to be constant in order to make the sequence valid.
                    if tv_pairs[-1][0] == new_sequence_length:
                        interval_styles = interval_styles[0 : len(tv_pairs) - 1]
                    else:
                        interval_styles = [
                            *interval_styles[0 : len(tv_pairs) - 1],
                            IntervalStyle.FLAT,
                        ]
                    # fill in channelsToUpdate dict.
                    channels_to_update[ch_num] = (tv_pairs, interval_styles)

            else:
                reset_changes()
                return

        # Try to update the timing variables on the sequence
        try:
            self.sequence.update_time_steps(
                self.seqEditor.n_samples,
                self.seqEditor.t_step,
                channels_to_update=channels_to_update,
            )
            self.seqPlot.reload_plot_data()
            self.chEditor.refresh_rows(self.chEditor.livech_num)

        # Catch validation errors, reset the variables in the UI and display an appropriate warning message
        except MultipleInvalidSequenceChannelError as mulErr:
            error_message = str(mulErr) + "\n"
            for i in range(0, len(mulErr.errors)):
                error_message += f"\nChannel {mulErr.errorChannels[i]} - {mulErr.errors[i]!s}"
                print(mulErr.errorChannels[i], str(mulErr.errors[i]))

            tk_message_box.showwarning(
                "Unable to applySamplingConfiguration changes", error_message
            )
            # Seems to be a tkinter bug that the parent is shown on top after this message dialog
            self.lift(self.parent)

            # reset the changes made and explain what has happened
            reset_changes()

    def display_warning(self, message, delay=3000):
        """Create an unobtrusive warning label that disappears after a delay."""
        warning_label = tk.Label(self, text=message, bg="yellow", height=1)
        warning_label.grid(row=2, column=0, columnspan=2, sticky=tk.N + tk.E + tk.W + tk.S)
        self.after(delay, warning_label.destroy)


class NotesUI(tk.Frame):
    def __init__(self, parent, sequence_reader):
        tk.Frame.__init__(self, parent)
        self.sequence_reader: SequenceReader = sequence_reader

        self.seqNotes, self.seqNotesFrame = self.create_sequence_notes()
        self.userNotes, self.userNotesFrame = self.create_user_notes()

        self.pack_propagate(False)
        self.seqNotesFrame.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.userNotesFrame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=1)

    def create_sequence_notes(self):
        sequence_notes_frame = tk.LabelFrame(self, text="Sequence notes", height=100)
        sequence_notes_frame.pack_propagate(False)

        scrollbar = tk.Scrollbar(sequence_notes_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Setting the width just enables the widget size to change - the actual size is determined
        # by the frame
        sequence_notes = tk.Text(
            sequence_notes_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, width=1
        )
        notes = f"sequence name: {self.sequence_reader.get_name()}\nlast saved: {self.sequence_reader.get_time()} on {self.sequence_reader.get_date()}\n\nThe channel assignments when this sequence was last saved were:\n"

        for x in self.sequence_reader.get_channel_assignment_notes():
            notes += f"Ch {x[0]}: {x[1]}\n"

        sequence_notes.insert(tk.END, notes)
        scrollbar.config(command=sequence_notes.yview)
        sequence_notes.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        sequence_notes.config(state=tk.DISABLED)

        return sequence_notes, sequence_notes_frame

    def create_user_notes(self):
        user_notes_frame = tk.LabelFrame(self, text="User notes")
        scrollbar = tk.Scrollbar(user_notes_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Setting the width just enables the widget size to change - the actual size is determined
        # by the frame
        user_notes = tk.Text(user_notes_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, width=1)

        notes = self.sequence_reader.get_user_notes()

        user_notes.insert(tk.END, notes)
        scrollbar.config(command=user_notes.yview)
        user_notes.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        return user_notes, user_notes_frame

    def get_user_notes(self):
        return self.userNotes.get(1.0, tk.END)


class SequenceEditorUI(tk.Frame):
    def __init__(self, parent, sequence_reader):
        tk.Frame.__init__(self, parent)
        self.sequence_reader = sequence_reader
        self.n_samples, self.t_step = self.sequence_reader.get_sequence_init_args()
        self.global_timings = self.sequence_reader.get_global_timings()

        sampling_config_frame = tk.LabelFrame(
            self, text="Sampling configuration", font=("Helvetica", 12)
        )

        label_opts = {"font": ("Helvetica", 10), "anchor": tk.E, "justify": tk.RIGHT}

        self.applyButton = tk.Button(
            sampling_config_frame,
            text="Apply",
            command=self.apply_sampling_configuration,
            state=tk.DISABLED,
        )

        self.samVar = tk.IntVar()
        self.samVar.set(self.n_samples)
        # %P = value of the entry if the edit is allowed
        vcmd_sam = (self.register(self.validate_sam_var), "%P")

        samlabel = tk.Label(sampling_config_frame, text="Num. samples:", **label_opts)
        self.samWid = tk.Entry(
            sampling_config_frame, validate="key", textvariable=self.samVar, vcmd=vcmd_sam
        )

        self.tStepVar = tk.DoubleVar()
        self.tStepVar.set(self.t_step)
        # %P = value of the entry if the edit is allowed
        vcmd_tstep = (self.register(self.validate_t_step), "%P")

        t_step_label = tk.Label(sampling_config_frame, text="time step (\u03bcs):", **label_opts)
        self.tStepWid = tk.Entry(
            sampling_config_frame, validate="key", textvariable=self.tStepVar, vcmd=vcmd_tstep
        )

        self.gridOpts = {"padx": 5, "pady": 5}

        samlabel.grid(row=0, column=0, padx=self.gridOpts["padx"], pady=self.gridOpts["pady"])
        self.samWid.grid(row=0, column=1, padx=self.gridOpts["padx"], pady=self.gridOpts["pady"])

        t_step_label.grid(row=1, column=0, padx=self.gridOpts["padx"], pady=self.gridOpts["pady"])
        self.tStepWid.grid(row=1, column=1, padx=self.gridOpts["padx"], pady=self.gridOpts["pady"])
        self.tStepTooltip = tooltip.create_tool_tip(
            self.tStepWid, f"{10**3 / float(self.tStepWid.get())}kHz rep. rate", open_delay=500
        )
        self.tStepWid.bind(
            "<FocusOut>",
            lambda event: self.tStepTooltip.update_text(
                f"{10**3 / float(self.tStepWid.get())}kHz rep. rate"
            ),
        )

        self.applyButton.grid(
            row=0, column=2, rowspan=2, padx=self.gridOpts["padx"], pady=self.gridOpts["pady"]
        )

        sampling_config_frame.pack(side=tk.TOP, padx=15, pady=15, fill=tk.X, expand=1)

        global_timing_frame = tk.LabelFrame(self, text="Global timings", font=("Helvetica", 12))

        self.globalTimingRows = []

        for timing in self.global_timings:
            self.globalTimingRows.append(GlobalTimingRowFrame(global_timing_frame, *timing))

        i = 0
        for row in self.globalTimingRows:
            row.grid(row=i, column=0, sticky=tk.W, **self.gridOpts)
            i += 1

        icon = Image.open("icons/add_icon.png").resize((12, 12))
        icon = ImageTk.PhotoImage(icon)
        self.addButton = ImageButton(
            global_timing_frame,
            image=icon,
            command=lambda: self.add_row(global_timing_frame),
            height=12,
            width=12,
        )
        self.addButton.image_ref = icon  # prevent garbage collection
        self.addButton.grid(row=i, column=0, sticky=tk.W, padx=10, pady=10)

        global_timing_frame.pack(side=tk.BOTTOM, padx=15, pady=15, fill=tk.BOTH, expand=1)

        self.bind("<FocusOut>", self.update_global_timings)
        self.bind("<Leave>", self.update_global_timings)

    def add_row(self, row_frame):
        _, n_rows = row_frame.grid_size()
        self.addButton.grid(row=n_rows, column=0, sticky=tk.W, padx=10, pady=10)

        name_popup = PopupEntry(
            self,
            "Create global timing",
            "Please enter the name of the new global timing - this cannot be edited after this point.",
        )
        # wait for the popup window to be destroyed before continuing
        self.winfo_toplevel().wait_window(name_popup.top)

        new_row = GlobalTimingRowFrame(row_frame, time="", name=name_popup.value)
        self.globalTimingRows.append(new_row)
        new_row.grid(
            row=n_rows - 1,
            column=0,
            sticky=tk.W,
            padx=self.gridOpts["padx"],
            pady=self.gridOpts["pady"],
        )

    def validate_sam_var(self, new_value):
        """Check the input is an integer and enable the applySamplingConfiguration button if the new value is not that
        which is currently set on the sequence"""
        try:
            int(new_value)
        except ValueError:
            return False
        if int(new_value) != self.n_samples:
            self.applyButton.config(state=tk.NORMAL)
        else:
            self.applyButton.config(state=tk.DISABLED)
        return True

    def validate_t_step(self, new_value):
        """Check the input is an float and enable the applySamplingConfiguration button if the new value is not that
        which is currently set on the sequence"""
        try:
            float(new_value)
        except ValueError:
            return False
        if float(new_value) != self.t_step:
            self.applyButton.config(state=tk.NORMAL)
        else:
            self.applyButton.config(state=tk.DISABLED)
        return True

    def set_n_samples(self, n_samples):
        self.samVar.set(n_samples)

    def set_t_step(self, t_step):
        self.tStepVar.set(t_step)

    def update_global_timings(self, event):
        self.global_timings = [
            (x.time, x.name) for x in self.globalTimingRows if x.isComplete() and x.isActive()
        ]
        self.winfo_toplevel().updateGlobalTimings()  # type: ignore

    def apply_sampling_configuration(self):
        """Update self.n_samples and self.t_step
        call up to Sequence_UI to update the sequence
        Sequence validates or rejects changes
        catch rejections: display message why & reset self.n_samples and self.t_step
        otherwise force updates to the res of the UI"""
        self.n_samples = self.samVar.get()
        self.t_step = self.tStepVar.get()
        self.winfo_toplevel().updateSequenceSamplingConfiguration()  # type: ignore


class GlobalTimingRowFrame(tk.Frame):
    def __init__(self, parent, time="", name="", **kwargs):
        tk.Frame.__init__(self, parent, **kwargs)

        self.time: str = time
        self.name = name
        self.active = True

        self.timeWid = tk.Entry(self)
        if self.time is not None:
            self.timeWid.insert(0, self.time)

        self.timeWid.bind("<FocusOut>", self.validate_time)

        self.nameWid = tk.Entry(self)
        if self.name is not None:
            self.nameWid.insert(0, self.name)
        self.nameWid.configure(state=tk.DISABLED)

        icon = Image.open("icons/delete_icon.png").resize((12, 12))
        icon = ImageTk.PhotoImage(icon)
        self.deleteButton = ImageButton(self, image=icon, command=self.delete, height=12, width=12)
        self.deleteButton.image_ref = icon  # prevent garbage collection

        self.grid_columnconfigure(0, weight=1, pad=3, uniform="cols")
        self.grid_columnconfigure(1, weight=1, pad=3, uniform="cols")
        self.grid_columnconfigure(2, weight=0, pad=3, uniform="cols")

        self.nameWid.grid(row=0, column=0, padx=5)
        self.timeWid.grid(row=0, column=1, sticky=tk.W, padx=5)
        self.deleteButton.grid(row=0, column=2, sticky=tk.W, padx=5)

    def validate_time(self, params):
        if self.timeWid.get().strip() == "":
            self.time = self.timeWid.get()
        else:
            try:
                self.time = str(self.timeWid.get())
            except ValueError:
                self.timeWid.delete(0, tk.END)
                self.timeWid.insert(0, self.time)

    #     def validateName(self, params):
    #         self.name = self.nameWid.get()
    def is_active(self):
        return self.active

    def is_complete(self):
        return self.time != "" and self.name != ""

    def delete(self):
        self.active = False
        self.destroy()


class PopupEntry:
    def __init__(self, parent, title, message, **kwargs):
        self.value = ""

        top = self.top = tk.Toplevel(parent, **kwargs)
        self.center_window()
        top.grab_set()
        top.title(title)

        tk.Message(top, text=message, aspect=300).grid(row=0, column=0, columnspan=2)

        self.entry = tk.Entry(top)
        self.entry.grid(row=1, column=0, columnspan=2)

        tk.Button(top, text="Confirm", command=self.confirm).grid(row=2, column=0)
        tk.Button(top, text="Cancel", command=self.destroy).grid(row=2, column=1)

    def center_window(self):
        """Centers the popup window on it's parent"""
        self.top.update_idletasks()

        top_size = [int(x) for x in self.top.geometry().split("+")[0].split("x")]
        parent_size = [
            int(x)
            for x in self.top.master.winfo_toplevel().winfo_geometry().split("+")[0].split("x")
        ]
        x_parent, y_parent = [
            int(x) for x in self.top.master.winfo_toplevel().winfo_geometry().split("+")[1:]
        ]
        x_top, y_top = (
            x_parent + parent_size[0] / 2 - top_size[0] / 2,
            y_parent + parent_size[1] / 2 - top_size[1] / 2,
        )

        self.top.geometry(f"{top_size[0]}x{top_size[1]}{int(x_top):+d}{int(y_top):+d}")

    def confirm(self):
        self.value = self.entry.get()
        self.destroy()

    def destroy(self):
        self.top.grab_release()
        self.top.master.focus_set()
        self.top.destroy()


class SequencePlotUI(tk.LabelFrame):
    def __init__(
        self,
        parent,
        sequence: DaqSequence,
        sequence_channel_labels: dict,
        text="Sequence preview",
        font=("Helvetica", 16),
        **kwargs,
    ):
        tk.LabelFrame.__init__(self, parent, text=text, font=font, **kwargs)

        self.sequence: DaqSequence = sequence

        self.fig, self.ax = plt.subplots()
        self.t = self.sequence.get_time_steps()
        # A dictionary to store the 2dLine matplotlib objects relating to each plotted channel
        self.chPlots = {}
        for ch_num in sequence.get_channel_nums():
            (ch_plot,) = self.ax.plot(
                self.t,
                self.sequence.get_channel_val_array(ch_num),
                label=self.get_legend_label(ch_num, sequence_channel_labels[ch_num]),
            )
            self.chPlots[ch_num] = ch_plot

        # Always cut the plot tight on the time axis and with a 10% buffer on the value axis
        self.ax.locator_params(axis="x", tight=True)
        self.ax.margins(y=0.1)
        self.rescale_view()

        self.interactiveLegend = self.get_interactive_legend()
        self.interactiveLegend.show()

    def draw_legend(self):
        self.ax.legend(
            loc="upper left", bbox_to_anchor=(1.05, 1), ncol=1, borderaxespad=0, fontsize=12
        )
        self.fig.subplots_adjust(left=0.05, bottom=0.06, right=0.68, top=0.96)

        self.interactiveLegend = self.get_interactive_legend()
        self.interactiveLegend.show()

    def get_legend_label(self, ch_num, ch_label):
        """Convert a channel number and label into a string to be dsiplayed in the plot legend."""
        return f"Ch {ch_num}: {ch_label}"

    def update_channel_labels(self, sequence_channel_labels):
        for ch_num in self.sequence.get_channel_nums():
            self.chPlots[ch_num].set_label(
                self.get_legend_label(ch_num, sequence_channel_labels[ch_num])
            )
        self.interactiveLegend.destroy()
        self.interactiveLegend = self.get_interactive_legend()
        self.interactiveLegend.show()

    def update_ch_plot(self, ch_num):
        """Update one of the channel plots to show new y-data (the time data will be unchanged as that is
        set for the whole sequence rather than a single channel)."""
        self.chPlots[ch_num].set_ydata(self.sequence.get_channel_val_array(ch_num))
        self.rescale_view()
        self.fig.canvas.draw()

    def reload_plot_data(self):
        """Reload all plot data from the sequence - typically called after updating variables that affect all channels,
        e.g. update interval, n_samples etc."""
        self.t = self.sequence.get_time_steps()
        for ch_num in self.sequence.get_channel_nums():
            self.chPlots[ch_num].set_data(self.t, self.sequence.get_channel_val_array(ch_num))
        self.rescale_view()
        self.fig.canvas.draw()

    def rescale_view(self):
        #         self.ax.locator_params(axis='x', tight=True)
        #         self.ax.locator_params(axis='y', tight=False)
        self.ax.relim()
        self.ax.autoscale_view()

    def get_interactive_legend(self, ax=None):
        self.ax.legend(
            loc="upper left", bbox_to_anchor=(1.05, 1), ncol=1, borderaxespad=0, fontsize=12
        )
        self.fig.subplots_adjust(left=0.05, bottom=0.06, right=0.68, top=0.96)
        return _InteractiveLegend(self, self.ax.legend_)


class _InteractiveLegend:
    def __init__(self, master, legend):
        self.master = master
        self.legend = legend
        self.fig = legend.axes.figure

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.master)
        self.toolbar.update()

        self.lookup_artist, self.lookup_handle = self._build_lookups(legend)
        self._setup_connections()
        self.update()

        self._dragging_legend = False
        self._drag_offset_y = 0
        self._drag_anchor_x = 1.0

    def _setup_connections(self):
        handles, _labels = self.legend.axes.get_legend_handles_labels()
        for artist in self.legend.texts + handles:
            artist.set_picker(10)

        self.canvas.mpl_connect("pick_event", self.on_pick)
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.canvas.mpl_connect("button_press_event", self.on_legend_press)
        self.canvas.mpl_connect("motion_notify_event", self.on_legend_motion)
        self.canvas.mpl_connect("button_release_event", self.on_legend_release)

    def _build_lookups(self, legend):
        handles, labels = legend.axes.get_legend_handles_labels()
        label2handle = dict(zip(labels, handles, strict=True))
        handle2text = dict(zip(handles, legend.texts, strict=True))

        lookup_artist = {}
        lookup_handle = {}
        for artist in legend.axes.get_children():
            if artist.get_label() in labels:
                handle = label2handle[artist.get_label()]
                lookup_handle[artist] = handle
                lookup_artist[handle] = artist
                lookup_artist[handle2text[handle]] = artist

        lookup_handle.update(zip(handles, handles, strict=True))
        lookup_handle.update(zip(legend.texts, handles, strict=True))

        return lookup_artist, lookup_handle

    def on_pick(self, event):
        handle = event.artist
        if handle in self.lookup_artist:
            artist = self.lookup_artist[handle]
            artist.set_visible(not artist.get_visible())
            self.update()

    def on_click(self, event):
        if event.button == 3:
            visible = False
        elif event.button == 2:
            visible = True
        else:
            return

        for artist in self.lookup_artist.values():
            artist.set_visible(visible)
        self.update()

    def on_legend_press(self, event):
        if self.legend.contains(event)[0]:
            self._dragging_legend = True
            bbox = self.legend.get_window_extent()
            self._drag_offset_y = bbox.y0 - event.y
            # fig_width = self.fig.get_size_inches()[0] * self.fig.dpi
            # x_anchor = self.legend.get_bbox_to_anchor()._bbox.get_points()[-1][-1]
            # self._drag_anchor_x = x_anchor

    def on_legend_motion(self, event):
        if self._dragging_legend and event.y is not None:
            fig_width, fig_height = self.fig.get_size_inches()
            fig_dpi = self.fig.dpi
            fig_px = fig_width * fig_dpi, fig_height * fig_dpi

            y = (event.y - self._drag_offset_y) / fig_px[1]
            y = max(0, min(2, y))  # clamp y between 0 and 1

            x = self._drag_anchor_x

            self.legend.set_bbox_to_anchor((x, y))
            self.update()

    def on_legend_release(self, event):
        self._dragging_legend = False

    def update(self):
        for artist in self.lookup_artist.values():
            handle = self.lookup_handle[artist]
            handle.set_visible(artist.get_visible())
        self.fig.canvas.draw()

    def show(self):
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def destroy(self):
        self.canvas.get_tk_widget().destroy()
        self.toolbar.destroy()


class ChannelEditorUI(tk.Frame):
    def __init__(
        self,
        parent,
        sequence: DaqSequence,
        sequence_reader: SequenceReader,
        sequence_channel_labels: dict,
        configured_channel_calibrations,
        **kwargs,
    ):
        tk.Frame.__init__(self, parent, **kwargs)

        self.parent = parent
        self.sequence: DaqSequence = sequence
        self.sequence_channel_labels = sequence_channel_labels
        self.configured_channel_calibrations = configured_channel_calibrations

        self.global_timings = sequence_reader.get_global_timings()
        self.livech_num = 0  # Will be modified by the dropdown

        # Before adding widgets lets configure the grid
        self.grid_columnconfigure(0, weight=0, pad=15, uniform="cols")
        self.grid_columnconfigure(1, weight=1, pad=15, uniform="cols")
        self.grid_columnconfigure(2, weight=1, pad=15, uniform="cols")
        self.grid_columnconfigure(3, weight=1, pad=15, uniform="cols")

        # Add the titles at the top of each column
        lab_font = ("Helvetica", 10)
        select_channel_label = tk.Label(self, text="Select channel", font=lab_font)
        #         time_col_label  = tk.Label(self, text=u"Time (\u03bcs)", font=lab_font)
        #         value_col_label  = tk.Label(self, text="Value (V)", font=lab_font)
        #         interval_col_label  = tk.Label(self, text="Interval style", font=lab_font)
        select_channel_label.grid(row=0, column=0)
        #         time_col_label.grid(row=0,column=1)
        #         value_col_label.grid(row=0,column=2)
        #         interval_col_label.grid(row=0,column=3)

        # Create all the row frames for the different channels
        self.rows, self.rowFrames = {}, {}
        for ch_num in self.sequence.get_channel_nums():
            self.rows[ch_num], self.rowFrames[ch_num] = self.create_rows_frame(ch_num)

        # Add the column select drop-down menu
        self.dropdown = self.create_channel_dropdown()
        self.dropdown.grid(row=1, column=0, sticky=tk.N)

    def refresh_rows(self, ch_num):
        self.rowFrames[ch_num].destroy()
        self.rows[ch_num], self.rowFrames[ch_num] = self.create_rows_frame(ch_num)
        self.channel_selected(self.liveChannel)

    #     def createrows_frame(self, ch_num):
    #         tV_pairs = self.sequence.get_tV_pairs(ch_num)
    #         V_intervalStyes = self.sequence.get_V_intervalStyles(ch_num)
    #
    #         rows_frame = tk.Frame(self)
    #         rows = []
    #         # Add a row for every configuer tV_pair on the sequence channel
    #         for i in range(0,len(tV_pairs)):
    #             try:
    #                 rows.append(Frame_ChannelEditorRow(rows_frame, tV_pairs[i], V_intervalStyes[i], self.global_timings))
    #             # It is possible for there to be one fewer interval styles than pairs if the last pair is on the
    #             # final step of the sequence - we presume that is the case here (if we are on the last pair of
    #             # course!) as validation is done when saving / loading the sequence.
    #             except IndexError as err:
    #                 if i != len(tV_pairs)-1:
    #                     raise err
    #
    #         # Add one extra blank row
    #         rows.append(Frame_ChannelEditorRow(rows_frame, global_timings=self.global_timings))
    #
    #         for r in rows:
    #             r.pack()
    #
    #         return rows, rows_frame

    def _on_frame_configure(self, rows_canvas):
        """Reset the scroll region to encompass the inner frame for a channel rows canvas"""
        rows_canvas.configure(scrollregion=rows_canvas.bbox("all"))

    def create_rows_frame(self, ch_num):
        tv_pairs = self.sequence.get_tv_pairs(ch_num)
        v_interval_styles = self.sequence.get_v_interval_styles(ch_num)

        top_frame = tk.Frame(self)

        # A load of jazz putting the frame in a canvas with a scrollbar just to get scrolling working
        rows_canvas = tk.Canvas(top_frame, borderwidth=0)
        scrollbar = tk.Scrollbar(top_frame, orient="vertical", command=rows_canvas.yview)
        rows_canvas.configure(yscrollcommand=scrollbar.set)

        rows_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        rows_frame = tk.Frame(rows_canvas)

        rows_canvas.create_window((0, 0), window=rows_frame, anchor=tk.NW)
        rows_frame.bind(
            "<Configure>", lambda event, canvas=rows_canvas: self._on_frame_configure(canvas)
        )

        # Get the channel calibration if it exists
        try:
            ch_calibration = self.configured_channel_calibrations[ch_num]
        except KeyError:
            ch_calibration = None

        # Set up whether we are building rows for a configured channel or not.
        value_units = ch_calibration[0] if ch_calibration else "V"

        rows = []
        # Add a row for every configure tV_pair on the sequence channel
        for i in range(0, len(tv_pairs)):
            try:
                rows.append(
                    ChannelEditorRowFrame(
                        rows_frame,
                        tv_pairs[i],
                        v_interval_styles[i],
                        ch_calibration,
                        self.global_timings,
                    )
                )
            # It is possible for there to be one fewer interval styles than pairs if the last pair is on the
            # final step of the sequence - we presume that is the case here (if we are on the last pair of
            # course!) as validation is done when saving / loading the sequence.
            except IndexError as err:
                if i != len(tv_pairs) - 1:
                    raise err

        # Add one extra blank row
        rows.append(
            ChannelEditorRowFrame(
                rows_frame,
                interval_style=IntervalStyle.FLAT,
                channel_calibration=ch_calibration,
                global_timings=self.global_timings,
            )
        )

        # Add column lables
        lab_font = ("Helvetica", 10)

        down_icon = Image.open("icons/down_icon.png").resize((12, 12))
        down_icon = ImageTk.PhotoImage(down_icon)
        up_icon = Image.open("icons/up_icon.png").resize((12, 12))
        up_icon = ImageTk.PhotoImage(up_icon)
        sort_rows_button = tk.Button(
            rows_frame,
            text="Time (\u03bcs)",
            font=lab_font,
            image=down_icon,
            compound=tk.RIGHT,
            relief=tk.FLAT,
        )
        sort_rows_button.down_icon = down_icon  # type: ignore
        sort_rows_button.up_icon = up_icon  # type: ignore
        sort_rows_button.downState = None  # type: ignore
        sort_rows_button.configure(
            command=lambda sort_button=sort_rows_button, rows=rows: self.sort_rows(
                sort_button, rows
            )
        )

        value_col_label = tk.Label(rows_frame, text=f"Value ({value_units})", font=lab_font)
        interval_col_label = tk.Label(rows_frame, text="Interval style", font=lab_font)

        sort_rows_button.grid(row=0, column=0)
        value_col_label.grid(row=0, column=1)
        interval_col_label.grid(row=0, column=2)

        i = 1
        for r in rows:
            r.grid(row=i, column=0, columnspan=3)
            i += 1

        icon = Image.open("icons/add_icon.png").resize((12, 12))
        icon = ImageTk.PhotoImage(icon)
        add_row_button = ImageButton(rows_frame, image=icon)
        add_row_button.image_ref = icon
        add_row_button.configure(
            command=lambda ch_num=ch_num, ch_calibration=ch_calibration: self.add_row(
                rows_frame, ch_num, ch_calibration, add_row_button
            )
        )
        add_row_button.grid(row=i, column=0, sticky=tk.W)

        return rows, top_frame

    def add_row(self, rows_frame, ch_num, ch_calibration, add_row_button):
        """Add another row for another time - value pair."""
        _, n_rows = rows_frame.grid_size()
        add_row_button.grid(row=n_rows, column=0, sticky=tk.W)

        new_row = ChannelEditorRowFrame(
            rows_frame,
            interval_style=IntervalStyle.FLAT,
            channel_calibration=ch_calibration,
            global_timings=self.global_timings,
        )
        self.rows[ch_num].append(new_row)
        new_row.grid(row=n_rows - 1, column=0, columnspan=3)

    def sort_rows(self, sort_button, rows):
        """The function called to sort the rows on a channel by time. Can either order in ascending or descending -
        will toggle between these functionalities on each call by toggling the .downState boolean on the button
        widget.  On the first call (i.e. before the rows have definatively been ordered) it will default to ascending."""

        # Find out what order we are sorting the rows into (i.e. the opposite of the current ordering.
        # Note is sort_button.downState is None (i.e. what it is after initialisation) then new_down_state is True.
        new_down_state = not sort_button.downState

        rows_with_args = [(row, row.grid_info()) for row in rows]
        populated_rows = sorted([x[1].pop("row") for x in rows_with_args])

        def get_time(row_with_args, undefined_is_postive):
            t = row_with_args[0].get_tV_pair()[0]
            # If t can't be converted to a float (i.e. the widget isn't fully filled in)
            # return infinity so it is ordered accordingly.
            try:
                float(t)
            except ValueError:
                t = np.inf if undefined_is_postive else -np.inf
            return t

        rows_with_args = sorted(
            rows_with_args, key=lambda x: get_time(x, new_down_state), reverse=not new_down_state
        )

        for row, args in rows_with_args:
            row.grid_forget()
            row.grid(row=populated_rows.pop(0), **args)

        # Set the new state of the widget and configure the direction of the arrow accordingly.
        sort_button.downState = new_down_state
        sort_button.configure(
            image=sort_button.down_icon if sort_button.downState else sort_button.up_icon
        )
        # print sort_button.state #AttributeError

    def create_channel_dropdown(self):

        channel_options = []

        for ch_num in self.sequence.get_channel_nums():
            channel_options.append(self.sequence_channel_labels[ch_num])

        self.liveChannel = tk.StringVar(self)
        self.liveChannel.set(channel_options[0])  # default value
        self.channel_selected(self.liveChannel)

        #         dropdown = applySamplingConfiguration(tk.OptionMenu, (self, liveChannel) + tuple(channel_options))
        dropdown = ttk.OptionMenu(
            self,
            self.liveChannel,
            channel_options[0],
            *channel_options,
            command=lambda x: self.channel_selected(self.liveChannel),
        )
        return dropdown

    def channel_selected(self, live_channel):
        self.rowFrames[self.livech_num].grid_forget()
        self.livech_num = next(
            x[0] for x in self.sequence_channel_labels.items() if x[1] == live_channel.get()
        )
        self.rowFrames[self.livech_num].grid(
            row=1, column=1, columnspan=3, sticky=tk.N + tk.S + tk.W + tk.E
        )

    def update_channel_labels(self, sequence_channel_labels):
        self.sequence_channel_labels = sequence_channel_labels
        #         self.currentChannel get

        channel_options = []
        for ch_num in self.sequence.get_channel_nums():
            channel_options.append(self.sequence_channel_labels[ch_num])
        #             self.dropdown['menu'].add_command(label=channel_options[-1], command=tk._setit(self.liveChannel, channel_options[-1]))

        self.dropdown.set_menu(
            self.liveChannel.get()
            if self.liveChannel.get() in channel_options
            else channel_options[0],
            *channel_options,
        )

    #         if not self.liveChannel.get() in channel_options:
    #             self.liveChannel.set(channel_options[0])

    def update_channel_calibrations(self, configured_channel_calibrations):
        self.configured_channel_calibrations = configured_channel_calibrations

        for ch_num in [k for k, _ in self.rows.items()]:
            self.refresh_rows(ch_num)

    def get_channel_sequence(self, ch_num):
        tv_pairs = []
        interval_styles = []

        for row in self.rows[ch_num]:
            if row.isComplete():
                tv_pairs.append(row.get_tV_pair())
                interval_styles.append(row.get_interval_style())

        return tv_pairs, interval_styles


class ChannelEditorRowFrame(tk.Frame):
    """
    A sub-class of a Tkinter.Frame to create a row in the sequence editor and have all it's widgets/values
    persist..
    """

    def __init__(
        self,
        parent,
        tv_pair=(None, None),
        interval_style=None,
        channel_calibration=None,
        global_timings=None,
        **kwargs,
    ):
        if global_timings is None:
            global_timings = []
        tk.Frame.__init__(self, parent, **kwargs)

        #         self.tV_pair = tV_pair
        #         self.interval_style = interval_style
        #         self.global_timings = global_timings

        self.tWid = TimeCombobox(
            self,
            tk.StringVar(),
            [x[0] for x in global_timings],
            [f"{x[0]} - {x[1]}" for x in global_timings],
        )

        self.vWid = (
            ValueEntry(self)
            if not channel_calibration
            else CalibratedValueEntry(self, *channel_calibration[1:3])
        )
        self.intervalWid = IntervalStyleDropdown(self, tk.StringVar(), IntervalStyle.get_all())
        #         self.intervalWid.configure('indicatoron'=False)

        # Set the initial values if a tV_pair was provided (no need to trigger an update as everything is being initialised)
        if tv_pair != (None, None):
            self.tWid.set_value(tv_pair[0], trigger_update=False)
            self.vWid.set_value(tv_pair[1], trigger_update=False)
        if interval_style is not None:
            self.intervalWid.set_value(interval_style, trigger_update=False)

        self.tWid.grid(row=0, column=0)
        self.vWid.grid(row=0, column=1)
        self.intervalWid.grid(row=0, column=2, sticky=tk.N + tk.E + tk.S + tk.W)

        self.grid_columnconfigure(0, weight=1, pad=3, uniform="cols")
        self.grid_columnconfigure(1, weight=1, pad=3, uniform="cols")
        self.grid_columnconfigure(2, weight=1, pad=3, uniform="cols")

    def get_tv_pair(self):
        return (self.tWid.value, self.vWid.value)

    def get_interval_style(self):
        return self.intervalWid.value

    def is_complete(self):
        return "" not in self.get_tv_pair() and self.get_interval_style() != ""


class TimeCombobox(ttk.Combobox):
    def __init__(self, parent, variable, value_options, value_labels, **kwargs):
        ttk.Combobox.__init__(self, parent, textvariable=variable, values=value_labels, **kwargs)
        self.value_options = value_options
        self.value_labels = value_labels
        self.value = self.get()

        self.bind("<<ComboboxSelected>>", self.on_validate)
        self.bind("<FocusOut>", self.on_validate)

    def set_value(self, new_value, trigger_update=True):
        """Set the stored widget value as an appropriate float and the displayed
        value as the appropriate label if one exists."""
        # If the newValue is a value label - register the value as the corresponding value_option
        try:
            self.value = float(self.value_options[self.value_labels.index(new_value)])
        except ValueError:
            self.value = float(new_value) if new_value != "" else new_value
        # If the new value corresponds to a value_label, display the label instead of the value
        try:
            self.set(self.value_labels[self.value_options.index(float(new_value))])
        except ValueError:
            self.set(new_value)

        if trigger_update:
            self.winfo_toplevel().updateLiveSequenceChannel()  # type: ignore

    def on_validate(self, event):
        if self.do_validation(self.get()):
            self.set_value(self.get(), trigger_update=True)
        else:
            self.set(self.value)

    def do_validation(self, new_value):
        # Pre-configured options are automatically valid
        if new_value in self.value_labels or new_value.strip() == "":
            return True
        # otherwise make sure the entry can be converted to a float
        else:
            try:
                float(new_value)
                return True
            except ValueError:
                return False


class ValueEntry(ttk.Entry):
    def __init__(self, parent):
        """
        Constructor
        """
        tk.Entry.__init__(self, parent)

        self.bind("<FocusOut>", self.focus_out)
        self.value = self.get()

    def set_value(self, new_value, trigger_update=True):
        self.value = new_value
        self.delete(0, tk.END)
        self.insert(0, self.value)

        if trigger_update:
            self.winfo_toplevel().updateLiveSequenceChannel()  # type: ignore

    def focus_out(self, params):
        # If the entry can be converted to a float it is valid, otherwise do not update
        # the stored value
        try:
            self.set_value(float(self.get()), trigger_update=True)
        except ValueError:
            # A blank entry is allowed
            if self.get().strip() == "":
                self.set_value("")
            else:
                self.set_value(self.value)


class CalibratedValueEntry(ValueEntry):
    """A value entry for a calibrated channel - subclasses ValueEntry but extends it
    to run user input values through a calibration function before storing/updating"""

    def __init__(self, parent, calibration_to_value_func, calibration_from_value_func):
        self.calibrationToValFunc = calibration_to_value_func
        self.calibrationFromValFunc = calibration_from_value_func
        ValueEntry.__init__(self, parent)

    def get(self):
        # If the entry is empty trying to run a calibration function is pointless
        if ValueEntry.get(self).strip() == "":
            return ""
        else:
            return self.calibrationToValFunc(float(ValueEntry.get(self)))

    def insert(self, index, string):
        ValueEntry.insert(self, index, self.calibrationFromValFunc(string))


class IntervalStyleDropdown(tk.OptionMenu):
    def __init__(self, parent, variable, value_options, **kwargs):
        tk.OptionMenu.__init__(
            self, parent, variable, *value_options, command=self.focus_out, **kwargs
        )
        self.variable = variable
        self.value = self.variable.get()

    def set_value(self, new_value, trigger_update=True):
        self.value = new_value
        self.variable.set(IntervalStyle.to_string(new_value))

        if trigger_update:
            self.winfo_toplevel().updateLiveSequenceChannel()  # type: ignore

    def focus_out(self, params):
        self.set_value(IntervalStyle.from_string(self.variable.get()), trigger_update=True)
