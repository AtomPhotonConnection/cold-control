"""
Created on 25 Mar 2016

@author: tombarrett
"""

import copy
import math
import tkinter as tk
from tkinter import filedialog as tk_file_dialog
from tkinter import messagebox as tk_message_box
from typing import Any

import numpy as np
from PIL import Image, ImageTk

import UI_classes.ToolTip_UI as tooltip
from classes.config_readers import DaqReader
from classes.daq import DAQChannel, DAQController
from UI_classes.UI_helpers import ImageButton


class DaqUI(tk.Frame):
    def __init__(
        self, parent, config_fname, font=("Helvetica", 16), development_mode=False, **kwargs
    ):
        tk.Frame.__init__(self, parent, **kwargs)

        self.parent = parent
        self.reader = DaqReader(config_fname)
        if not development_mode:
            self.daq_controller: DAQController = self.reader.load_daq_controller()
        else:
            print("Running in development mode...\nLoading Dummy DAQ cards")
            self.daq_controller = self.reader.load_dummy_daq_controller()  # type: ignore

        self.Frame_Channels = tk.LabelFrame(self, text="DAQ channels", font=font)
        self.Frame_DIOs = tk.LabelFrame(self, text="Digital outputs", font=font)

        self.channelFrames: list[FrameDAQChannel] = []

        for channel in self.daq_controller.get_channels(only_visible=True):
            self.channelFrames.append(
                FrameDAQChannel(self.Frame_Channels, channel, self.daq_controller)
            )

        # Lay out all the tk obects created
        num_cols = np.ceil(len(self.channelFrames) / 8.0)

        grid_config: dict[str, Any] = {"padx": 5, "pady": 2}

        for c, column in enumerate(
            [
                self.channelFrames[i : i + int(len(self.channelFrames) / int(num_cols))]
                for i in range(
                    0,
                    int(len(self.channelFrames) + 1),
                    int(np.ceil(len(self.channelFrames) / num_cols)),
                )
            ]
        ):
            for r, ch in enumerate(column):
                ch.grid(row=r, column=c, **grid_config)

        grid_size = self.Frame_Channels.grid_size()

        icon = Image.open("icons/config_icon.png").resize((20, 20))
        icon = ImageTk.PhotoImage(icon)
        self.configButton = ImageButton(
            self.Frame_Channels, image=icon, command=self.daq_config_button, height=20, width=20
        )
        self.configButton.image_ref = icon
        self.configButton.grid(
            row=grid_size[1], column=grid_size[0] - 1, sticky=tk.E + tk.S, **grid_config
        )
        tooltip.create_tool_tip(self.configButton, "Configure DAQ channels", open_delay=2000)

        icon = Image.open("icons/power_icon.png").resize((20, 20))
        icon = ImageTk.PhotoImage(icon)
        self.daqOutputButton = ImageButton(
            self.Frame_Channels,
            image=icon,
            bg="red",
            command=self.toggle_daq_button,
            height=20,
            width=20,
        )
        self.daqOutputButton.image_ref = (
            icon  # store the image as a variable in the widget to prevent garbage collection.
        )
        self.daqOutputButton.grid(row=grid_size[1], column=0, sticky=tk.W + tk.S, **grid_config)
        tooltip.create_tool_tip(self.daqOutputButton, "Start/stop DAQ channels", open_delay=2000)

        cols, rows = self.Frame_Channels.grid_size()
        for c in range(0, cols):
            self.Frame_Channels.grid_columnconfigure(c, weight=1, pad=3, uniform="cols")
        for r in range(0, rows):
            self.Frame_Channels.grid_rowconfigure(r, weight=0, pad=0, uniform="rows")

        #         self.dioFrames = []
        #         r = 0
        #         for dio in sorted(self.daq_controller.get_dios(), key=lambda dio: dio.dio_num):
        #             frame = Frame_DIOline(self.Frame_DIOs, dio)
        #             self.dioFrames.append(frame)
        #             frame.grid(row=r, column=0, **gridConfig)
        #             r+=1
        #
        # 1. Initialize the frames
        self.dioFrames = [
            DioLineFrame(self.Frame_DIOs, dio)
            for dio in sorted(self.daq_controller.get_dios(), key=lambda dio: dio.dio_num)
        ]

        # 2. Grid with wrapping logic
        max_cols = 3
        for index, dio_frame in enumerate(self.dioFrames):
            row = index // max_cols  # Every 3 items, the row increments
            col = index % max_cols  # The column resets to 0, 1, 2

            dio_frame.grid(row=row, column=col, **grid_config)

        # 3. Configure columns for equal spacing (0 to 2)
        for c in range(max_cols):
            self.Frame_DIOs.grid_columnconfigure(c, weight=1, uniform="group1")

        # 4. Final layout
        self.Frame_Channels.pack(side=tk.TOP, fill=tk.X)
        self.Frame_DIOs.pack(side=tk.BOTTOM, fill=tk.X)

    def update_for_new_daq_config(self):
        for ch_frame in self.channelFrames:
            ch_frame.reload()

    def toggle_daq_button(self):
        self.daq_controller.toggle_continuous_output()
        if self.daq_controller.continuousOutput:
            self.daqOutputButton.configure(bg="green")
        else:
            self.daqOutputButton.configure(bg="red")

    def daq_config_button(self):
        daq_config_ui = DaqConfigUI(self, self.daq_controller)
        self.winfo_toplevel().wait_window(daq_config_ui.top)
        self.daq_controller = daq_config_ui.controller
        if daq_config_ui.triggerDAQUpdates:
            self.update_for_new_daq_config()
            """TODO : NOT WORKING"""
            if self.daq_controller.continuousOutput:
                self.daq_controller.write_channel_values()


class FrameDAQChannel(tk.Frame):
    """
    A sub-class of a Tkinter.Frame to create entry widgets and decorations for setting DAQ channels.
    """

    def __init__(self, parent, daq_channel: DAQChannel, daq_controller):
        """
        Constructor
        """
        tk.Frame.__init__(self, parent)

        self.DAQchannel = daq_channel
        self.DAQcontroller = daq_controller
        self.frame = tk.Frame(self)

        self.add_entry()

        self.frame.pack(fill=tk.X, padx=5, pady=5)

        self.tooltip = tooltip.create_tool_tip(
            self, self.DAQchannel.get_help_text(), open_delay=2000
        )

    def add_entry(self):
        self.entry = DaqChannelEntry(self.frame, self.DAQcontroller, self.DAQchannel)
        self.lab = tk.Label(self.frame, width=20, text=self.DAQchannel.chName, anchor="w")
        self.entry.pack(side=tk.RIGHT, fill=tk.X)
        self.lab.pack(side=tk.LEFT)

    def reload(self):
        self.entry.destroy()
        self.lab.destroy()
        self.add_entry()
        self.tooltip.text = self.DAQchannel.get_help_text()


class DioLineFrame(tk.Frame):
    """
    A sub-class of a Tkinter.Frame to create entry widgets and decorations for setting Digital IO lines.
    """

    def __init__(self, parent, daq_dio):
        """
        Constructor
        """
        tk.Frame.__init__(self, parent)

        self.daq_dio = daq_dio

        self.lab = tk.Label(self, width=22, text=self.daq_dio.dio_name, anchor="w")

        self.on_icon = ImageTk.PhotoImage(Image.open("icons/toggle_on_icon.png").resize((25, 20)))
        self.off_icon = ImageTk.PhotoImage(Image.open("icons/toggle_off_icon.png").resize((25, 20)))

        self.button = tk.Button(self, command=self.toggle_button, height=20, width=30)
        self.daq_dio.write(not self.daq_dio.enabled_state)
        self.update_button_icon(self.daq_dio.read())

        self.button.pack(side=tk.RIGHT)
        self.lab.pack(side=tk.LEFT, fill=tk.X)

        self.tooltip = tooltip.create_tool_tip(self, self.daq_dio.get_help_text(), open_delay=2000)

    def toggle_button(self):
        new_state = self.daq_dio.toggle_state(return_state=True)
        self.update_button_icon(new_state)

    def update_button_icon(self, new_state):
        if new_state == self.daq_dio.enabled_state:
            self.button.configure(image=self.on_icon, bg="green", relief=tk.SUNKEN)
        else:
            self.button.configure(image=self.off_icon, bg="red", relief=tk.RAISED)


class DaqChannelEntry(tk.Entry):
    """
    A sub-class of a Tkinter.Entry to create entry widgets for setting DAQ channels.
    """

    def __init__(self, parent, daq_controller, daq_channel):
        """
        Constructor
        """
        tk.Entry.__init__(self, parent)

        self.controller = daq_controller
        self.channel = daq_channel

        self.chLimits = (
            self.channel.chLimits
            if not self.channel.isCalibrated
            else sorted(self.channel.calibrationFromVFunc(self.channel.chLimits))
        )
        self.defaultValue = (
            self.channel.defaultValue
            if not self.channel.isCalibrated
            else self.channel.calibrationFromVFunc(self.channel.defaultValue)
        )
        if not self.chLimits[0] <= self.defaultValue <= self.chLimits[1]:
            print(
                "WARNING: Default value for DAQ channel of",
                self.defaultValue,
                "is not within set limits of",
                self.chLimits,
                "\nChannel will be set to mid-range of limits",
            )
            self.defaultValue = sum(self.chLimits) / 2
        self.chValue = float(self.defaultValue)

        self.widget = tk.Entry(self, justify=tk.CENTER)

        self.widget.insert(0, str(self.chValue))
        self.widget.bind("<FocusOut>", self.focus_out)
        self.widget.bind("<Return>", self.focus_out)
        self.widget.bind("<Up>", self.arrow_key)
        self.widget.bind("<Down>", self.arrow_key)
        self.widget.pack()

    def flash(self, col, length=500):
        """
        Flashes the background of the entry widget a colour (col) for a length of time (length) in ms.
        Usually used during validation to indicate whether the new value entered is valid.
        """
        self.widget.config(bg=col)
        self.widget.after(length, lambda: self.widget.configure(bg="white"))

    def arrow_key(self, event):
        """
        Called when the Up or Down arrow key is pressed.
        Increments the value on the DAQ channel accordingly.
        """

        # Count the number of places between the decimal place in the float and the cursor index
        # to calculate the order of the incrementation, i.e 0.01, 0.1, 1, 10, ...
        current_text = self.widget.get()
        decimal_index = current_text.index(".")
        cursor_index = self.widget.index(tk.INSERT)
        increment_order = decimal_index - cursor_index

        # Track the cursor offset relative to the decimal point so it can be restored correctly
        # even when the number of digits changes (e.g. 9.5 -> 10.5 or -0.5 -> 0.5).
        offset_from_decimal = cursor_index - decimal_index

        # If the increment order is -1 the cursor is on the decimal point so do nothing.
        if increment_order != -1:
            if increment_order < -1:
                increment_order += 1
            # Calculate the amount to change the value by.  The sign is determined by the key pressed.
            iterator = (
                math.pow(10, increment_order)
                if event.keysym == "Up"
                else -1 * math.pow(10, increment_order)
            )

            # We have to count the number of decimal places of the number and round the iterated
            # value back to this level due to Python's imprecision with floats.
            ndp = current_text[::-1].find(".")

            self.widget.delete(0, tk.END)
            self.widget.insert(0, str(round(float(current_text) + iterator, ndp)))
            self.focus_out(event)

            # Restore the cursor at the same position relative to the decimal point so that
            # repeated arrow key presses continue to increment the same digit, regardless of
            # whether the string length changed (e.g. 9 -> 10 or 10 -> 9).
            new_text = self.widget.get()
            new_decimal_index = new_text.index(".")
            new_cursor_index = max(0, min(len(new_text), new_decimal_index + offset_from_decimal))
            self.widget.icursor(new_cursor_index)

    def focus_out(self, params):
        flash_col = None
        try:
            if self.chLimits[0] <= float(self.widget.get()) <= self.chLimits[1]:
                if self.chValue != float(self.widget.get()):
                    self.chValue = float(self.widget.get())
                    flash_col = "green"
            else:
                flash_col = "red"
        except ValueError:
            flash_col = "red"
        finally:
            self.widget.delete(0, tk.END)
            self.widget.insert(0, str(self.chValue))

        if flash_col:
            self.flash(flash_col)
        # Update channel value (after converting it to a voltage if the channel is calibrated)
        self.controller.update_channel_value(
            self.channel.chNum,
            self.chValue
            if not self.channel.isCalibrated
            else self.channel.calibrationToVFunc(self.chValue),
        )


class DaqConfigUI:
    def __init__(self, parent, daq_control: DAQController):
        """This object creates a copy of the DAQ controller as backup and then a top level window to edit the origional.
        On exit from the top level window the changes are either kept or we revert to the original controller.  The
        edited controller must then be fetched from this object by code that wishes to use it."""
        self.controllerOrig = copy.deepcopy(daq_control)
        self.controller = daq_control
        # A flag for whether the rest of the UI needs to update due to changes made.
        self.triggerDAQUpdates = False

        self.top = tk.Toplevel(parent)
        self.top.wm_title("DAQ configuration")
        self.top.columnconfigure(0, weight=1)

        self.configure_for_current_controller()

        # Changes the close button to call my close function.
        self.top.protocol("WM_DELETE_WINDOW", self.close_window)

        self.top.grab_set()

    def configure_for_current_controller(self):
        """This method creates, configures and draws all the elements of the UI that are dependent on the currently loaded DAQ controller
        Primarily it is just an extension of the __init__ for the class however this section of code needs to be run to re-configure the
        UI for a new DAQ config if one is loaded."""
        # Destroy any widgets that have already been created (i.e. clear the frame before re-drawing)
        for wid in self.top.winfo_children():
            wid.destroy()

        frame_config = {"font": ("Helvetica", 16)}
        label_config = {"font": ("Helvetica", 10, "bold"), "padx": 5}

        self.cardsFrame = self.get_cards_frame(frame_config, label_config)
        self.channelsFrame, self.channels = self.get_channels_frame(frame_config, label_config)
        self.buttonsFrame = self.get_buttons_frame()

        self.cardsFrame.grid(row=0, column=0, sticky=tk.N + tk.E + tk.S + tk.W)
        self.channelsFrame.grid(row=1, column=0, sticky=tk.N + tk.E + tk.S + tk.W)
        self.buttonsFrame.grid(row=2, column=0, sticky=tk.E)

        self.top.grid_columnconfigure(0, weight=1, pad=5)

    def get_cards_frame(self, frame_config=None, label_config=None):
        if label_config is None:
            label_config = {}
        if frame_config is None:
            frame_config = {}
        card_frame = tk.LabelFrame(self.top, text="DAQ cards", **frame_config)

        tk.Label(card_frame, text="Card Number", **label_config).grid(row=0, column=0)
        tk.Label(card_frame, text="Master", **label_config).grid(row=0, column=1)
        tk.Label(card_frame, text="Channels", **label_config).grid(row=0, column=2)

        for card in [self.controller.master, *self.controller.slaves]:
            r = card_frame.grid_size()[1]
            tk.Label(card_frame, text=card.card).grid(row=r, column=0)

            # It's worth noting these checkbuttons are currently not coded to do anything.
            # They display which card is the master and offer the possibility of changing
            # this if I decided that's relevant at some point...
            var = tk.IntVar()
            checkbutton = tk.Checkbutton(card_frame, variable=var)
            checkbutton.configure(
                command=lambda wid=checkbutton, num=card.card, var=var: self.master_selected(
                    wid, num, var
                )
            )
            checkbutton.grid(row=r, column=1)
            # Select the checkbutton for the first card row darwn (i.e. the master)
            if r == 1:
                checkbutton.select()
            checkbutton.configure(state=tk.DISABLED)

            tk.Label(
                card_frame, text=str([ch.chNum for ch in card.channels]), font=("Helvetica", 10)
            ).grid(row=r, column=2)

        #         cardFrame.grid_configure(ipadx=20)

        return card_frame

    def get_channels_frame(self, frame_config=None, label_config=None):
        if label_config is None:
            label_config = {}
        if frame_config is None:
            frame_config = {}
        channels_frame = tk.LabelFrame(self.top, text="Channels", **frame_config)

        controller_channels: list[DAQChannel] = self.controller.get_channels()

        channel_options = [
            self.get_channel_dropdown_label(ch.chNum, ch.chName)
            for ch in sorted(controller_channels, key=lambda x: x.chNum)
        ]
        self.dropdownVar = tk.StringVar()
        self.dropdownVar.set(channel_options[0])
        self.dropdown = tk.OptionMenu(
            channels_frame,
            self.dropdownVar,
            *channel_options,
            command=lambda var=self.dropdownVar: self.channel_selected(var),
        )

        channels = {}
        ch_lab_grid_opts: dict[str, Any] = {"sticky": tk.W}
        ch_wid_grid_opts: dict[str, Any] = {"sticky": tk.E + tk.W}

        for ch in controller_channels:
            frame = tk.Frame(channels_frame)

            channels[self.get_channel_dropdown_label(ch.chNum, ch.chName)] = frame

            r = 0

            tk.Label(frame, text="Channel number:", **label_config).grid(
                row=r, column=0, **ch_lab_grid_opts
            )
            # ch_num_wid = tk.Label(frame, text=ch.chNum).grid(row=r, column=1, **ch_wid_grid_opts)
            r += 1

            tk.Label(frame, text="Channel name:", **label_config).grid(
                row=r, column=0, **ch_lab_grid_opts
            )
            ch_name_wid = e = tk.Entry(frame)
            e.insert(0, ch.chName)
            e.grid(row=r, column=1, **ch_wid_grid_opts)
            r += 1

            tk.Label(frame, text="Lower limit (V):", **label_config).grid(
                row=r, column=0, **ch_lab_grid_opts
            )
            ch_low_lim_wid = e = tk.Entry(frame)
            e.insert(0, ch.chLimits[0])
            e.grid(row=r, column=1, **ch_wid_grid_opts)
            r += 1

            tk.Label(frame, text="Upper limit (V):", **label_config).grid(
                row=r, column=0, **ch_lab_grid_opts
            )
            ch_up_lim_wid = e = tk.Entry(frame)
            e.insert(0, ch.chLimits[1])
            e.grid(row=r, column=1, **ch_wid_grid_opts)
            r += 1

            ch_def_val_lab = tk.Label(
                frame,
                text="Default value ({}):".format(
                    "V" if not ch.isCalibrated else ch.calibrationUnits
                ),
                **label_config,
            )
            ch_def_val_lab.grid(row=r, column=0, **ch_lab_grid_opts)
            ch_def_val_wid = e = tk.Entry(frame)
            value = ""
            if ch.calibrationFromVFunc is not None:
                value = str(ch.calibrationFromVFunc(ch.defaultValue))
            e.insert(0, str(ch.defaultValue) if not ch.isCalibrated else value)
            e.grid(row=r, column=1, **ch_wid_grid_opts)
            r += 1

            tk.Label(frame, text="UI visable:", **label_config).grid(
                row=r, column=0, **ch_lab_grid_opts
            )
            cb_var = tk.IntVar()
            c = tk.Checkbutton(
                frame,
                variable=cb_var,
                command=lambda ch=ch, var=cb_var: self.ch_ui_v_is_updated(ch, var),
            )
            if ch.isUIVisible:
                c.select()
            c.grid(row=r, column=1, **ch_wid_grid_opts)

            tk.Label(frame, text="Calibration file:", **label_config).grid(
                row=r, column=0, **ch_lab_grid_opts
            )

            calib_frame = tk.Frame(frame)

            calib_fname_wid = e = tk.Entry(calib_frame)
            e.insert(0, ch.calibrationFname if ch.isCalibrated else "None")
            e.pack(side=tk.LEFT)

            icon = Image.open("icons/delete_icon.png").resize((20, 20))
            icon = ImageTk.PhotoImage(icon)
            remove_calib_button = ImageButton(
                calib_frame,
                image=icon,
                command=lambda ch=ch, wid=calib_fname_wid, def_val_lab=ch_def_val_lab, def_val_wid=ch_def_val_wid: (
                    self.remove_calib_file_button(ch, wid, def_val_lab, def_val_wid)
                ),
                height=16,
                width=16,
            )
            remove_calib_button.image_ref = icon
            remove_calib_button.pack(side=tk.RIGHT)

            icon = Image.open("icons/folder_icon.png").resize((20, 20))
            icon = ImageTk.PhotoImage(icon)
            add_calib_button = ImageButton(
                calib_frame,
                image=icon,
                command=lambda ch=ch, wid=calib_fname_wid, def_val_lab=ch_def_val_lab, def_val_wid=ch_def_val_wid: (
                    self.select_calibration_file_button(ch, wid, def_val_lab, def_val_wid)
                ),
                height=16,
                width=16,
            )
            add_calib_button.image_ref = (
                icon  # store the image as a variable in the widget to prevent garbage collection.
            )
            add_calib_button.pack(side=tk.RIGHT)

            calib_frame.grid(row=r, column=1, **ch_wid_grid_opts)

            ch_name_wid.bind(
                "<FocusOut>",
                lambda event, ch=ch, wid=ch_name_wid: self.ch_name_updated(event, ch, wid),
            )
            ch_name_wid.bind(
                "<Return>",
                lambda event, ch=ch, wid=ch_name_wid: self.ch_name_updated(event, ch, wid),
            )

            ch_low_lim_wid.bind(
                "<FocusOut>",
                lambda event, ch=ch, lim_wids=[ch_low_lim_wid, ch_up_lim_wid], def_val_wid=ch_def_val_wid: (
                    self.ch_limits_updated(event, ch, lim_wids, def_val_wid)
                ),
            )
            ch_low_lim_wid.bind(
                "<Return>",
                lambda event, ch=ch, lim_wids=[ch_low_lim_wid, ch_up_lim_wid], def_val_wid=ch_def_val_wid: (
                    self.ch_limits_updated(event, ch, lim_wids, def_val_wid)
                ),
            )

            ch_up_lim_wid.bind(
                "<FocusOut>",
                lambda event, ch=ch, lim_wids=[ch_low_lim_wid, ch_up_lim_wid], def_val_wid=ch_def_val_wid: (
                    self.ch_limits_updated(event, ch, lim_wids, def_val_wid)
                ),
            )
            ch_up_lim_wid.bind(
                "<Return>",
                lambda event, ch=ch, lim_wids=[ch_low_lim_wid, ch_up_lim_wid], def_val_wid=ch_def_val_wid: (
                    self.ch_limits_updated(event, ch, lim_wids, def_val_wid)
                ),
            )

            ch_def_val_wid.bind(
                "<FocusOut>",
                lambda event, ch=ch, wid=ch_def_val_wid: self.ch_def_val_updated(event, ch, wid),
            )
            ch_def_val_wid.bind(
                "<Return>",
                lambda event, ch=ch, wid=ch_def_val_wid: self.ch_def_val_updated(event, ch, wid),
            )

            calib_fname_wid.bind(
                "<FocusOut>",
                lambda event, ch=ch, wid=calib_fname_wid, def_val_lab=ch_def_val_lab, def_val_wid=ch_def_val_wid: (
                    self.ch_calib_file_updated(event, ch, wid, def_val_lab, def_val_wid)
                ),
            )
            calib_fname_wid.bind(
                "<Return>",
                lambda event, ch=ch, wid=calib_fname_wid, def_val_lab=ch_def_val_lab, def_val_wid=ch_def_val_wid: (
                    self.ch_calib_file_updated(event, ch, wid, def_val_lab, def_val_wid)
                ),
            )

            frame.grid_columnconfigure(0, weight=1)
            frame.grid_columnconfigure(1, weight=1, pad=5)
            frame.grid(row=0, column=1, sticky=tk.N + tk.W + tk.E)
            frame.grid_remove()

        self.dropdown.grid(row=0, column=0, sticky=tk.N + tk.W)

        channels[
            self.get_channel_dropdown_label(
                controller_channels[0].chNum, controller_channels[0].chName
            )
        ].grid()

        channels_frame.grid_columnconfigure(0, weight=0)
        channels_frame.grid_columnconfigure(1, weight=1)

        return channels_frame, channels

    def get_buttons_frame(self):
        buttons_frame = tk.Frame(self.top)
        apply_button = tk.Button(
            buttons_frame, text="Apply", command=self.apply, width=15, bg="green"
        )
        cancel_button = tk.Button(
            buttons_frame, text="Cancel", command=self.cancel, width=15, bg="red"
        )
        apply_button.grid(row=0, column=1, sticky=tk.E)
        cancel_button.grid(row=1, column=1, sticky=tk.E)

        return buttons_frame

    def _update_channel_dropdown(self, options, initial_val=None):
        """reset the values in the option menu"""
        menu = self.dropdown["menu"]
        menu.delete(0, "end")

        def callback(var=self.dropdownVar):
            return self.channel_selected(var)

        for v in options:
            menu.add_command(label=v, command=tk._setit(self.dropdownVar, v, callback))
        if initial_val is not None:
            self.dropdownVar.set(initial_val)

    def master_selected(self, widget, card_number, state):
        """Function called when a 'master' checkbox is selected/deselected.
        widget - the checkbox widget clicked on
        cardNumber - the card number assosiated with the widget
        state - 0/1, checkbox is now deselected/selected"""
        print(widget, card_number, state.get())

    def channel_selected(self, channel_label):
        for _, wid in self.channels.items():
            wid.grid_remove()
        self.channels[channel_label].grid()

    def get_channel_dropdown_label(self, ch_num, ch_name):
        return f"Ch {ch_num!s}: {ch_name}"

    def ch_name_updated(self, event, ch, wid):
        """Updates the channel dictionary and the channel dropdown with the new channel name"""
        old_ch_label = self.get_channel_dropdown_label(ch.chNum, ch.chName)
        ch.chName = wid.get()
        new_ch_label = self.get_channel_dropdown_label(ch.chNum, ch.chName)
        self.channels[new_ch_label] = self.channels.pop(old_ch_label)
        self._update_channel_dropdown(
            [
                self.get_channel_dropdown_label(ch.chNum, ch.chName)
                for ch in sorted(self.controller.get_channels(), key=lambda x: x.chNum)
            ],
            new_ch_label,
        )
        self.channel_selected(new_ch_label)
        self._flash(wid, "green")

    def ch_limits_updated(self, event, ch: DAQChannel, lim_wids: list[Any], def_val_wid):
        old_limits = ch.chLimits
        flash_col = "green"

        # Check the new limits are valid (can be floats and min <= max)
        try:
            new_limits = [float(w.get()) for w in lim_wids]

            if not new_limits[0] <= new_limits[1]:
                raise ValueError("Lower limit must be less than upper limit")

            # Must be valid if we got here
            ch.chLimits = new_limits
            if not new_limits[0] <= ch.defaultValue <= new_limits[1]:
                def_val_wid.delete(0, tk.END)
                def_val_wid.insert(0, np.clip(ch.defaultValue, new_limits[0], new_limits[1]))
                self.ch_def_val_updated(None, ch, def_val_wid)

        except (ValueError, IndexError):
            flash_col = "red"

            # revert changes
            for i in [0, 1]:
                lim_wids[i].delete(0, tk.END)
                lim_wids[i].insert(0, old_limits[i])

        for wid in lim_wids:
            self._flash(wid, flash_col)

    def ch_def_val_updated(self, event, ch: DAQChannel, wid):
        old_default_val = ch.defaultValue
        flash_col = "green"

        try:
            # 1. Extract and convert the input string to float once
            raw_val = float(wid.get())

            # 2. Handle Calibration logic with explicit None checks for Pylance
            if ch.isCalibrated and ch.calibrationToVFunc is not None:
                new_default_value = float(ch.calibrationToVFunc(raw_val))
            else:
                new_default_value = raw_val

            # 3. Validation against limits
            if not (ch.chLimits[0] <= new_default_value <= ch.chLimits[1]):
                raise ValueError("Value out of bounds")

            # 4. Success Path
            ch.defaultValue = new_default_value

            # If calibrated, update the widget (in case the function modified/clipped the value)
            if ch.isCalibrated and ch.calibrationFromVFunc is not None:
                wid.delete(0, tk.END)
                wid.insert(0, ch.calibrationFromVFunc(new_default_value))

        except (ValueError, TypeError, IndexError):
            # 5. Failure Path
            flash_col = "red"
            wid.delete(0, tk.END)

            if ch.isCalibrated and ch.calibrationFromVFunc is not None:
                wid.insert(0, ch.calibrationFromVFunc(old_default_val))
            else:
                wid.insert(0, old_default_val)

        self._flash(wid, flash_col)

    def ch_ui_v_is_updated(self, ch: DAQChannel, var):
        ch.isUIVisible = var.get()

    def ch_calib_file_updated(
        self, event, ch: DAQChannel, wid, default_value_label, default_value_widget
    ):
        # Get the old value of the widget to restore it if the calibration fails.
        old_widget_value = ch.calibrationFname if ch.isCalibrated else "None"
        try:
            ch.calibrate(wid.get())
            default_value_label.configure(text=f"Default value ({ch.calibrationUnits}):")
            default_value_widget.delete(0, tk.END)
            if ch.calibrationFromVFunc is not None:
                value = ch.calibrationFromVFunc(ch.defaultValue)
            else:
                raise ValueError("Calibration function is None")
            default_value_widget.insert(0, value)
            flash_col = "green"
        except OSError:
            # If the calibration failed as a bad file was selected, reset the widget to it's previous state
            wid.delete(0, tk.END)
            wid.insert(0, old_widget_value)
            flash_col = "red"
        self._flash(wid, flash_col)

    def _flash(self, wid, flash_col, delay=500):
        wid.config(bg=flash_col)
        wid.after(delay, lambda: wid.configure(bg="white"))

    def select_calibration_file_button(self, ch, wid, default_value_label, default_value_wid):
        fname = tk_file_dialog.askopenfilename(
            parent=self.top, title="Select a calibration file", initialdir=""
        )
        # Seems to be a tkinter bug that the parent is shown on top after a file dialog - so let's fix that
        self.top.lift()

        # Check for empty filenames (i.e. when the user cancelled the action)
        if fname != "":
            wid.delete(0, tk.END)
            wid.insert(0, fname)
            self.ch_calib_file_updated(None, ch, wid, default_value_label, default_value_wid)

    def remove_calib_file_button(self, ch, wid, default_value_lab, default_val_wid):
        """Remove the calibration from the channel and re-set the relevant UI labels and entries"""
        ch.remove_calibration()
        wid.delete(0, tk.END)
        wid.insert(0, "None")
        default_value_lab.configure(text="Default value (V):")
        default_val_wid.delete(0, tk.END)
        default_val_wid.insert(0, ch.defaultValue)

    def apply(self):
        self.triggerDAQUpdates = True
        self.close_window(False)

    def cancel(self):
        self.revert_changes()
        self.triggerDAQUpdates = False
        self.close_window(False)

    #     def save(self):
    #         fname = tk_file_dialog.asksaveasfilename(title="Save a DAQ configuration")
    #         # Check for empyy filenames (i.e. when the user cancelled the acion)
    #         if fname!= '':
    #             writer = DaqWriter(fname)
    #             writer.save(self.controller.master, *self.controller.slaves)
    #
    #         # Seems to be a tkinter bug that the parent is shown on top after a file dialog - so let's fix that
    #         self.top.lift()
    #
    #     def load(self):
    #         fname = tk_file_dialog.askopenfilename(master=self, title="Load a DAQ configuration", initialdir="")
    #
    #         # Check for empty filenames (i.e. when the user cancelled the action)
    #         if fname!= '':
    #             self.controller.release_all()
    #             self.controller = DaqReader(fname).load_daq_controller()
    #
    #             self.configureForCurrentController()
    #
    #         # Seems to be a tkinter bug that the parent is shown on top after a file dialog - so let's fix that
    #         self.top.lift()

    def revert_changes(self):
        self.controller = self.controllerOrig

    def close_window(self, ask_to_apply_changes=True):
        """Close the window."""
        if ask_to_apply_changes:
            apply_on_exit = tk_message_box.askyesnocancel(
                "Confirm exit",
                "Would you like to apply your changes before you exit?",
                parent=self.top,
            )
            if apply_on_exit is None:
                return
            elif not apply_on_exit:
                self.revert_changes()
        self.top.grab_release()
        self.top.destroy()
