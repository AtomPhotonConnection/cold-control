"""Configuration dialogs for experiments.

Classes:
    AbsorptionImagingConfigurationUi  - Full-featured editor for absorption-
        imaging experiment parameters (channels, trigger levels, camera
        settings, etc.).
    GenericExperimentConfigUi          - Lightweight dialog that lets the user
        swap experiment config files.
"""

import ast
import copy
import tkinter as tk
from tkinter import filedialog as tk_file_dialog
from tkinter import messagebox as tk_message_box
from typing import Any

import numpy as np
from PIL import Image, ImageTk

from classes.config_readers import ExperimentConfigReader
from UI_classes.Experimental_UI import ExperimentalParamFrame
from UI_classes.UI_helpers import ImageButton


class AbsorptionImagingConfigurationUi:
    def __init__(
        self,
        parent,
        absorbtion_imaging_configuration,
        daq_controller,
        sequence_length,
        sequence_t_step,
    ):
        """This object presents for editing the settings for absorbtion imaging experiments.  It takes and edits a
        copy of the Absorbtion Imaging Configuration.  A flag then exists to indicate whether the user wants these
        edits to be applied or not when the window is closed."""

        # A flag that denotes is the user confirms or cancels edits they make in this window when exiting.
        self.apply_changes = False

        self.config = self.c = copy.copy(absorbtion_imaging_configuration)
        self.daq_controller = daq_controller
        self.sequence_length = sequence_length
        self.sequence_t_step = sequence_t_step

        self.top = self.configure_window(parent)

        self.top.wm_title("Absorbtion imaging configuration")
        self.top.grab_set()
        # Changes the close button to call my close function.
        self.top.protocol("WM_DELETE_WINDOW", self.close_window)

    def configure_window(self, parent):
        """
        Build all the widget enteries for this UI.
        """
        top = tk.Toplevel(parent)
        frame = tk.Frame(top)

        labels, widgets, fns_to_bind = [], [], []

        controller_channels = self.daq_controller.get_channels()
        channel_opts_dict: dict[Any, Any] = dict(
            zip(
                [
                    self.get_channel_dropdown_label(ch.chNum, ch.chName)
                    for ch in sorted(controller_channels, key=lambda x: x.chNum)
                ],
                [x.chNum for x in controller_channels],
                strict=True,
            )
        )
        channel_opts = sorted(channel_opts_dict.keys(), key=channel_opts_dict.__getitem__)

        labels.append("Camera trigger channel:")
        self.c.camera_trig_ch_var = var = tk.StringVar()
        var.set(
            next(key for key, value in channel_opts_dict.items() if value == self.c.camera_trig_ch)
        )
        camera_trig_ch_dropdown = tk.OptionMenu(
            frame,
            var,
            *channel_opts,
            command=lambda x=var: self.update_camera_trig_ch(
                camera_trig_levs_wid,
                n_bkg_wid,
                next(ch for ch in controller_channels if ch.chNum == channel_opts_dict[x]),
            ),
        )
        widgets.append(camera_trig_ch_dropdown)
        fns_to_bind.append(None)

        labels.append("Imaging power channel:")
        self.c.imag_power_ch_var = var = tk.StringVar()
        var.set(
            next(key for key, value in channel_opts_dict.items() if value == self.c.imag_power_ch)
        )
        imag_power_ch_dropdown = tk.OptionMenu(
            frame,
            var,
            *channel_opts,
            command=lambda x=var: self.update_imag_power_ch(
                imag_power_levs_wid,
                n_bkg_wid,
                next(ch for ch in controller_channels if ch.chNum == channel_opts_dict[x]),
            ),
        )
        widgets.append(imag_power_ch_dropdown)
        fns_to_bind.append(None)

        labels.append("Camera trigger levels:")
        camera_trig_levs_wid = e = tk.Entry(frame)
        camera_trig_levs_wid.insert(0, "{}, {}".format(*self.c.camera_trig_levs))
        widgets.append(camera_trig_levs_wid)

        def update_cam_trigger_levs(new_levs):
            self.c.camera_trig_levs = new_levs

        fns_to_bind.append(
            lambda event: self.trig_levs_focus_out(
                event.widget,
                next(ch for ch in controller_channels if ch.chNum == self.c.camera_trig_ch),
                lambda new_levs, f=update_cam_trigger_levs: f(new_levs),
            )
        )

        labels.append("Imaging power levels:")
        imag_power_levs_wid = e = tk.Entry(frame)
        imag_power_levs_wid.insert(0, "{}, {}".format(*self.c.imag_power_levs))
        widgets.append(imag_power_levs_wid)

        def update_imag_power_levs(new_levs):
            self.c.imag_power_levs = new_levs

        fns_to_bind.append(
            lambda event: self.trig_levs_focus_out(
                event.widget,
                next(ch for ch in controller_channels if ch.chNum == self.c.imag_power_ch),
                lambda new_levs, f=update_imag_power_levs: f(new_levs),
            )
        )

        labels.append("Camera pulse width (\u03bcs):")
        # camera_pulse_width_wid = e = tk.Entry(frame)
        e.insert(0, self.c.camera_pulse_width)
        widgets.append(e)
        fns_to_bind.append(lambda event: self.camera_pulse_width_focus_out(event.widget))

        labels.append("Imaging flash width (\u03bcs):")
        # imag_pulse_width_wid = e = tk.Entry(frame)
        e.insert(0, self.c.imag_pulse_width)
        widgets.append(e)
        fns_to_bind.append(lambda event: self.imag_pulse_width_focus_out(event.widget))

        labels.append("t images (\u03bcs):")
        # t_imag_wid = e = tk.Entry(frame)
        e.insert(0, self.c.t_imgs)
        widgets.append(e)
        fns_to_bind.append(lambda event: self.t_img_focus_out(event.widget))

        labels.append("MOT reload time (ms):")
        # mot_reload_time_wid = e = tk.Entry(frame)
        e.insert(0, self.c.mot_reload_time)
        widgets.append(e)
        fns_to_bind.append(lambda event: self.mot_reload_time_focus_out(event.widget))

        labels.append("# backgrounds:")
        n_bkg_wid = e = tk.Entry(frame)
        e.insert(0, self.c.n_backgrounds)
        widgets.append(e)
        fns_to_bind.append(lambda event: self.n_backgrounds_focus_out(event.widget))

        labels.append("Background off channels:")
        # bkg_off_channels_wid = e = tk.Entry(frame)
        e.insert(0, self.c.bkg_off_channels)
        widgets.append(e)
        fns_to_bind.append(lambda event: self.bkg_off_channels_focus_out(event.widget))

        labels.append("Save location:")
        # save_location_wid = e = tk.Label(frame, text=self.c.save_location)
        widgets.append(e)
        fns_to_bind.append(None)

        labels.append("Auto-save options:")
        # save_options_wid = e = tk.Frame(frame)

        check_frames = []
        checkbuttons = []
        check_vars = []
        for check_label in [
            "Save raw images:",
            "Save processed images:",
            "Review processed images:",
        ]:
            check_frame = tk.Frame(e)

            lab = tk.Label(check_frame, text=check_label)
            var = tk.IntVar()
            checkbutton = tk.Checkbutton(check_frame, variable=var)

            check_frames.append(check_frame)
            checkbuttons.append(checkbutton)
            check_vars.append(var)

            lab.pack(side=tk.LEFT)
            checkbutton.pack(side=tk.RIGHT)

        # Bind methods to checkbuttons
        checkbuttons[0].configure(command=lambda var=check_vars[0]: self.save_raw_checkbutton(var))
        checkbuttons[1].configure(
            command=lambda var=check_vars[1]: self.save_processed_checkbutton(var)
        )
        checkbuttons[2].configure(
            command=lambda var=check_vars[2], save_var=check_vars[1], save_wid=checkbuttons[1]: (
                self.review_imgs_checkbutton(var, save_var, save_wid)
            )
        )

        # Set checkbuttons initial values and invoke bound methods (so the buttons are consistent, e.g. save_processed_images is disabled if review_processed images is selected).
        for _button, var, init_val in zip(
            checkbuttons,
            check_vars,
            [self.c.save_raw_images, self.c.save_processed_images, self.c.review_processed_images],
            strict=True,
        ):
            var.set(init_val)
        if check_vars[2].get():
            self.review_imgs_checkbutton(check_vars[2], check_vars[1], checkbuttons[1])

        for check_frame in check_frames:
            check_frame.pack(side=tk.LEFT)

        widgets.append(e)
        fns_to_bind.append(None)

        labels.append("Camera gain:")
        cam_gain_frame = tk.Frame(frame)
        cam_gain_entry_wid = e = tk.Entry(cam_gain_frame)
        cam_gain_slider_wid = s = tk.Scale(
            cam_gain_frame,
            from_=self.c.cam_gain_lims[0],
            to=self.c.cam_gain_lims[1],
            command=lambda value: self.cam_gain_slider_focus_out(value, cam_gain_entry_wid),
            orient=tk.HORIZONTAL,
            showvalue=False,
        )
        e.bind(
            "<FocusOut>",
            lambda event: self.cam_gain_entry_focus_out(event.widget, cam_gain_slider_wid),
        )
        e.bind(
            "<Return>",
            lambda event: self.cam_gain_entry_focus_out(event.widget, cam_gain_slider_wid),
        )
        e.insert(0, self.c.cam_gain)
        s.set(self.c.cam_gain)

        e.grid(row=0, column=0)
        s.grid(row=0, column=1, sticky=tk.E + tk.W)
        cam_gain_frame.grid_columnconfigure(0, weight=0)
        cam_gain_frame.grid_columnconfigure(1, weight=1, pad=5)
        cam_gain_frame.grid(row=0, column=1, sticky=tk.N + tk.W + tk.E)

        widgets.append(cam_gain_frame)
        fns_to_bind.append(None)

        labels.append("Camera exposure (s):")
        cam_exposure_frame = tk.Frame(frame)
        cam_exposure_entry_wid = e = tk.Entry(cam_exposure_frame)
        cam_exposure_slider_wid = s = tk.Scale(
            cam_exposure_frame,
            from_=self.c.cam_exposure_lims[1],
            to=self.c.cam_exposure_lims[0],
            command=lambda value: self.cam_exposure_slider_focus_out(value, cam_exposure_entry_wid),
            orient=tk.HORIZONTAL,
            showvalue=False,
        )
        e.bind(
            "<FocusOut>",
            lambda event: self.cam_exposure_entry_focus_out(event.widget, cam_exposure_slider_wid),
        )
        e.bind(
            "<Return>",
            lambda event: self.cam_exposure_entry_focus_out(event.widget, cam_exposure_slider_wid),
        )
        e.insert(0, self.exposure_to_string(1 / self.c.cam_exposure))
        s.set(self.c.cam_exposure)

        e.grid(row=0, column=0)
        s.grid(row=0, column=1, sticky=tk.E + tk.W)
        cam_exposure_frame.grid_columnconfigure(0, weight=0)
        cam_exposure_frame.grid_columnconfigure(1, weight=1, pad=5)
        cam_exposure_frame.grid(row=0, column=1, sticky=tk.N + tk.W + tk.E)

        widgets.append(cam_exposure_frame)
        fns_to_bind.append(None)

        labels.append("Scan imaging freq:")
        scan_img_freqs_var = tk.IntVar()
        scan_img_freqs_var.set(self.c.scan_abs_img_freq)
        scan_img_freqs_checkbutton = tk.Checkbutton(frame, variable=scan_img_freqs_var)
        widgets.append(scan_img_freqs_checkbutton)
        fns_to_bind.append(None)

        labels.append("Imaging freq. channel:")
        self.c.abs_img_freq_ch_var = var = tk.StringVar()
        var.set(
            next(key for key, value in channel_opts_dict.items() if value == self.c.abs_img_freq_ch)
        )
        abs_img_freq_ch_dropdown = tk.OptionMenu(
            frame,
            var,
            *channel_opts,
            command=lambda x=var: self.update_imaging_freq_ch(
                abs_img_freqs_entry_wid,
                next(ch for ch in controller_channels if ch.chNum == channel_opts_dict[x]),
            ),
        )
        fns_to_bind.append(None)
        widgets.append(abs_img_freq_ch_dropdown)

        try:
            calib_units, _, from_v_func = self.daq_controller.get_channel_calibration_dict()[
                self.c.abs_img_freq_ch
            ]
        except KeyError:
            calib_units, _, from_v_func = "V", None, lambda x: x

        labels.append(f"Imaging freqs ({calib_units}):")
        abs_img_freqs_entry_wid = e = tk.Entry(frame)
        e.insert(0, str([from_v_func(freq) for freq in self.c.abs_img_freqs]))
        widgets.append(e)
        fns_to_bind.append(
            lambda event: self.imaging_freqs_focus_out(
                event.widget,
                next(ch for ch in controller_channels if ch.chNum == self.c.abs_img_freq_ch),
            )
        )

        scan_img_freqs_checkbutton.configure(
            command=lambda var=scan_img_freqs_var: self.scan_imaging_freqs_checkbutton(
                var, [abs_img_freq_ch_dropdown, abs_img_freqs_entry_wid]
            )
        )

        if not self.c.scan_abs_img_freq:
            abs_img_freq_ch_dropdown.configure(state=tk.DISABLED)
            abs_img_freqs_entry_wid.configure(state=tk.DISABLED)

        lab_grid_opts: dict[str, Any] = {"sticky": tk.W}
        wid_grid_opts = {"sticky": tk.E + tk.W}
        lab_config = {"font": ("Helvetica", 10, "bold"), "padx": 5}
        for r, (lab, wid, fn) in enumerate(zip(labels, widgets, fns_to_bind, strict=True)):
            tk.Label(frame, text=lab, **lab_config).grid(row=r, column=0, **lab_grid_opts)
            wid.grid(row=r, column=1, **wid_grid_opts)
            if fn is not None:
                wid.bind("<FocusOut>", fn)
                wid.bind("<Return>", fn)

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1, pad=5)
        frame.grid(row=0, column=0, sticky=tk.N + tk.W + tk.E)

        button_frame = tk.Frame(top)

        apply_button = tk.Button(
            button_frame, text="Apply", command=self.apply, width=15, bg="green"
        )
        cancel_button = tk.Button(
            button_frame, text="Cancel", command=self.cancel, width=15, bg="red"
        )
        apply_button.grid(row=0, column=0, sticky=tk.E)
        cancel_button.grid(row=1, column=0, sticky=tk.E)

        button_frame.grid(row=1, column=0, sticky=tk.E)

        return top

    def scan_imaging_freqs_checkbutton(self, var, linked_wids):
        scan_abs_img_freqs = bool(var.get())
        self.c.scan_abs_img_freq = scan_abs_img_freqs
        linked_wids_state = tk.NORMAL if scan_abs_img_freqs else tk.DISABLED
        for wid in linked_wids:
            wid.configure(state=linked_wids_state)

    def update_imaging_freq_ch(self, img_freqs_wid, new_img_freq_ch):
        self.c.abs_img_freq_ch = new_img_freq_ch.chNum

        self.imaging_freqs_focus_out(img_freqs_wid, new_img_freq_ch)

    def imaging_freqs_focus_out(self, imaging_freqs_widget, configured_imaging_freq_channel):
        try:
            flash_col = "green"
            try:
                entered_freqs = list(map(float, ast.literal_eval(imaging_freqs_widget.get())))
            except TypeError:
                # If a single value is entered, map() will throw a TypeError as the second arg is not iterable.
                entered_freqs = [float(ast.literal_eval(imaging_freqs_widget.get()))]
            # Check only two levels were entered
            if len(entered_freqs) == 0:
                raise ValueError
            new_entered_freqs = tuple(
                map(
                    lambda x: np.clip(
                        x,
                        *configured_imaging_freq_channel.chLimits
                        if not configured_imaging_freq_channel.isCalibrated
                        else configured_imaging_freq_channel.calibrationFromVFunc(
                            configured_imaging_freq_channel.chLimits
                        ),
                    ),
                    entered_freqs,
                )
            )
            # If we reach this point, everything was succesful so update the stored values.
            self.c.abs_img_freqs = (
                new_entered_freqs
                if not configured_imaging_freq_channel.isCalibrated
                else list(
                    map(configured_imaging_freq_channel.calibrationToVFunc, new_entered_freqs)
                )
            )
        # If there was an error while converting the entered text to the correct form, catch it and flash red.
        except (NameError, ValueError, SyntaxError):
            flash_col = "red"
        # Update the display text and flash the widget accordingly.
        imaging_freqs_widget.delete(0, tk.END)
        imaging_freqs_widget.insert(
            0,
            self.c.abs_img_freqs
            if not configured_imaging_freq_channel.isCalibrated
            else list(
                map(configured_imaging_freq_channel.calibrationFromVFunc, self.c.abs_img_freqs)
            ),
        )
        imaging_freqs_widget.config(bg=flash_col)
        imaging_freqs_widget.after(500, lambda: imaging_freqs_widget.configure(bg="white"))

    def update_camera_trig_ch(self, trig_levs_wid, bkg_off_channels_wid, new_trig_ch):
        # Update the stored values and trigger an update of the trigger level widget.
        self.c.camera_trig_ch = new_trig_ch.chNum

        def update_cam_trigger_levs(new_levs):
            self.c.camera_trig_levs = new_levs

        self.trig_levs_focus_out(
            trig_levs_wid, new_trig_ch, lambda new_levs, f=update_cam_trigger_levs: f(new_levs)
        )
        self.bkg_off_channels_focus_out(bkg_off_channels_wid)

    def update_imag_power_ch(self, trig_levs_widget, bkg_off_channels_wid, new_power_ch):
        # Update the stored values and trigger an update of the trigger level widget.
        self.c.imag_power_ch = new_power_ch.chNum

        def update_image_power_levs(new_levs):
            self.c.imag_power_levs = new_levs

        self.trig_levs_focus_out(
            trig_levs_widget, new_power_ch, lambda new_levs, f=update_image_power_levs: f(new_levs)
        )
        self.bkg_off_channels_focus_out(bkg_off_channels_wid)

    def trig_levs_focus_out(self, trig_levs_widget, configured_trigger_channel, update_levs_func):
        """
        Handles updates to the trigger level enteries.
        """
        new_trig_levs = None

        # If the entered values can be converted to the correct form, do so and update the stored values.
        try:
            flash_col = "green"
            entered_trig_levs = tuple(map(float, ast.literal_eval(trig_levs_widget.get())))
            # Check only two levels were entered
            if len(entered_trig_levs) != 2:
                raise ValueError
            new_trig_levs = tuple(
                map(
                    lambda x: np.clip(
                        x,
                        *configured_trigger_channel.chLimits
                        if not configured_trigger_channel.isCalibrated
                        else configured_trigger_channel.calibrationFromVFunc(
                            configured_trigger_channel.chLimits
                        ),
                    ),
                    entered_trig_levs,
                )
            )
            # If the values were clipped to fit to the channel limits, flash the widget yellow as a warning.
            if new_trig_levs != entered_trig_levs:
                flash_col = "yellow"
            # If we reach this point, everything was sucessful so update the stored values.
            update_levs_func(new_trig_levs)
        # If there was an error whilst converting the entered text to the correct form, catch it and flash red.
        except (NameError, ValueError, SyntaxError, TypeError):
            flash_col = "red"
        # Update the display text and flash the widget accordingly.
        trig_levs_widget.delete(0, tk.END)
        if new_trig_levs is not None:
            trig_levs_widget.insert(0, "{}, {}".format(*new_trig_levs))
        trig_levs_widget.config(bg=flash_col)
        trig_levs_widget.after(500, lambda: trig_levs_widget.configure(bg="white"))

    def pulse_width_focus_out(self, default_value, widget):
        """
        Ensure that any pulse width entered is at least as long as the smallest time step in the sequence and shorter
        than the total sequence length.
        """
        new_width = default_value
        info_msg = None
        try:
            flash_col = "green"
            new_width = float(widget.get())
            if new_width < self.sequence_t_step:
                info_msg = f"A step change in the sequence must be longer than the smallest time step of the sequence (currently {self.sequence_t_step}\u03bcs)."
                flash_col = "yellow"
                new_width = self.sequence_t_step
            if new_width > self.sequence_length:
                info_msg = f"A step change in the sequence must be shorter than the total sequence length (currently {self.sequence_length}\u03bcs)."
                flash_col = "red"
                new_width = self.sequence_t_step
        except ValueError:
            flash_col = "red"
        # Update the display text and flash the widget accordingly.
        widget.delete(0, tk.END)
        widget.insert(0, new_width)
        widget.config(bg=flash_col)
        widget.after(500, lambda: widget.configure(bg="white"))
        if info_msg is not None:
            self.display_warning(info_msg)
        return new_width

    def camera_pulse_width_focus_out(self, widget):
        self.c.camera_pulse_width = self.pulse_width_focus_out(self.c.camera_pulse_width, widget)

    def imag_pulse_width_focus_out(self, widget):
        self.c.imag_pulse_width = self.pulse_width_focus_out(self.c.imag_pulse_width, widget)

    def t_img_focus_out(self, widget):
        """
        Ensure that all the times request for images are valid inputs and within the length of the sequence.
        """
        info_msg = None
        try:
            flash_col = "green"
            try:
                entered_t_imgs = list(map(float, ast.literal_eval(widget.get())))
            except TypeError:
                # If a single value is entered, map() will throw a TypeError as the second arg is not iterable.
                entered_t_imgs = [float(ast.literal_eval(widget.get()))]
            new_t_imgs = [t for t in entered_t_imgs if 0 <= t <= self.sequence_length]
            # If the values were removed to fit the sequence length, flash the widget yellow as a warning.
            if entered_t_imgs != new_t_imgs:
                info_msg = f"You can only take images with the length of the currently configured sequence (which is {self.sequence_length}\u03bcs)."
                flash_col = "yellow"
            # If we reach this point, everything was sucessful so update the stored values.
            self.c.t_imgs = new_t_imgs
        # If there was an error while converting the entered text to the correct form, catch it and flash red.
        except (NameError, ValueError, SyntaxError):
            flash_col = "red"
        # Update the display text and flash the widget accordingly.
        widget.delete(0, tk.END)
        widget.insert(0, self.c.t_imgs)
        widget.config(bg=flash_col)
        widget.after(500, lambda: widget.configure(bg="white"))
        if info_msg is not None:
            self.display_warning(info_msg)

    def mot_reload_time_focus_out(self, widget):
        """
        Enforce the a positive number or zero is set for the mot reload time.
        """
        try:
            flash_col = "green"
            new_mot_reload_time = float(widget.get())
            if new_mot_reload_time < 0:
                raise ValueError
            # If we reach this point, everything was sucessful so update the stored values.
            self.c.mot_reload_time = new_mot_reload_time  # in ms
        # If there was an error while converting the entered text to the correct form, catch it and flash red.
        except (NameError, ValueError, SyntaxError, TypeError):
            flash_col = "red"
        # Update the display text and flash the widget accordingly.
        widget.delete(0, tk.END)
        widget.insert(0, self.c.mot_reload_time)  # in ms
        widget.config(bg=flash_col)
        widget.after(500, lambda: widget.configure(bg="white"))

    def n_backgrounds_focus_out(self, widget):
        """
        Enforce that a positive integer is set for the number of backgrounds to take.
        """
        try:
            flash_col = "green"
            new_n_backgrounds = int(widget.get())
            if new_n_backgrounds <= 0:
                raise ValueError
            # If we reach this point, everything was sucessful so update the stored values.
            self.c.n_backgrounds = new_n_backgrounds
        # If there was an error while converting the entered text to the correct form, catch it and flash red.
        except (NameError, ValueError, SyntaxError, TypeError):
            flash_col = "red"
        # Update the display text and flash the widget accordingly.
        widget.delete(0, tk.END)
        widget.insert(0, self.c.n_backgrounds)
        widget.config(bg=flash_col)
        widget.after(500, lambda: widget.configure(bg="white"))

    def bkg_off_channels_focus_out(self, widget):
        """
        Ensure that a list of valid channel numbers is entered and that the camera trigger and imaging flash channels are not turned off.
        """
        info_msgs = []
        try:
            flash_col = "green"
            # Try to convert the entered string into a list of channel numbers
            try:
                entered_bkg_off_channels = list(map(int, ast.literal_eval(widget.get())))
            except TypeError:
                # A type error can be thrown when converting a single interger as a string to a list. Add a comma to avoid this,
                # i.e. list(ast.literal_eval('7')) -> TypeError, list(ast.literal_eval('7,')) = [7]
                entered_bkg_off_channels = list(map(int, ast.literal_eval(widget.get() + ",")))
            new_bkg_off_channels = [
                x
                for x in entered_bkg_off_channels
                if x in [ch.chNum for ch in self.daq_controller.get_channels()]
            ]
            if new_bkg_off_channels != entered_bkg_off_channels:
                flash_col = "yellow"
                info_msgs.append("Unrecognised channel numbers have been removed.")
            if self.c.camera_trig_ch in new_bkg_off_channels:
                flash_col = "yellow"
                info_msgs.append(
                    f"The camera trigger channel (channel {self.c.camera_trig_ch}) cannot be turned off when taking background images."
                )
                new_bkg_off_channels.remove(self.c.camera_trig_ch)
            if self.c.imag_power_ch in new_bkg_off_channels:
                flash_col = "yellow"
                info_msgs.append(
                    f"The imaging flash channel (channel {self.c.imag_power_ch}) cannot be turned off when taking background images."
                )
                new_bkg_off_channels.remove(self.c.imag_power_ch)
            if new_bkg_off_channels == []:
                flash_col = "yellow"
                info_msgs.append(
                    "No channels are turned off when taking a background image.\nTo take a background image I suggest at least turning off the MOT repump."
                )
            # If we reach this point, everything was sucessful so update the stored values.
            self.c.bkg_off_channels = new_bkg_off_channels
        except (NameError, ValueError, SyntaxError, TypeError):
            flash_col = "red"
        # Update the display text and flash the widget accordingly.
        widget.delete(0, tk.END)
        widget.insert(0, self.c.bkg_off_channels)
        widget.config(bg=flash_col)
        widget.after(500, lambda: widget.configure(bg="white"))
        for info_msg in info_msgs:
            self.display_warning(info_msg)

    def save_raw_checkbutton(self, var):
        self.c.save_raw_images = bool(var.get())

    def save_processed_checkbutton(self, var):
        self.c.save_processed_images = bool(var.get())

    def review_imgs_checkbutton(self, var, save_processed_var, save_processed_wid):
        state = bool(var.get())

        # If the review processed images checkbutton is selected, deselect and disable
        # the auto-saving of processed images (as autosaving before reviewing is daft).
        if state:
            save_processed_var.set(False)
            self.save_processed_checkbutton(save_processed_var)
            save_processed_wid.configure(state=tk.DISABLED)
        else:
            save_processed_wid.configure(state=tk.NORMAL)

        self.c.review_processed_images = state

    def cam_gain_entry_focus_out(self, entry_wid, slider_wid):
        try:
            flash_col = "green"
            entered_cam_gain = float(entry_wid.get())
            new_cam_gain = np.clip(entered_cam_gain, *self.c.cam_gain_lims)
            if new_cam_gain != entered_cam_gain:
                flash_col = "yellow"

            # If we reach this point, everything was sucessful so update the stored values.
            self.c.cam_gain = int(new_cam_gain)
        except ValueError:
            flash_col = "red"

        # Update the display and flash the widget accordingly.
        entry_wid.delete(0, tk.END)
        entry_wid.insert(0, self.c.cam_gain)
        slider_wid.set(self.c.cam_gain)

        entry_wid.config(bg=flash_col)
        entry_wid.after(500, lambda: entry_wid.configure(bg="white"))

    def cam_gain_slider_focus_out(self, slider_value, entry_wid):
        # Slider doesn't not allow invalid values to be set.
        self.c.cam_gain = int(slider_value)
        # Update entry widget
        entry_wid.delete(0, tk.END)
        entry_wid.insert(0, self.c.cam_gain)

    def cam_exposure_entry_focus_out(self, entry_wid, slider_wid):
        try:
            flash_col = "green"
            parsed_entered_cam_exposure = entry_wid.get().split("/")
            if len(parsed_entered_cam_exposure) == 1:
                # A fraction wasn't entered so the entered exposure is 1/x where x is the entered exposure time.
                entered_cam_exposure = int(1 / float(parsed_entered_cam_exposure[0]))
            elif len(parsed_entered_cam_exposure) == 2:
                # A fraction was entred so take it's reciprocal.
                entered_cam_exposure = int(
                    float(parsed_entered_cam_exposure[1]) / float(parsed_entered_cam_exposure[0])
                )
            else:
                # Can't parse this into a number, raise an exception.
                raise ValueError
            new_cam_exposure = int(np.clip(entered_cam_exposure, *sorted(self.c.cam_exposure_lims)))
            if new_cam_exposure != entered_cam_exposure:
                flash_col = "yellow"
            # If we reach this point, everything was sucessful so update the stored values.
            self.c.cam_exposure = new_cam_exposure
        except ValueError:
            flash_col = "red"

        print(self.c.cam_exposure)
        # Update the display and flash the widget accordingly.
        entry_wid.delete(0, tk.END)
        entry_wid.insert(0, self.exposure_to_string(1.0 / self.c.cam_exposure))
        slider_wid.set(self.c.cam_exposure)

        entry_wid.config(bg=flash_col)
        entry_wid.after(500, lambda: entry_wid.configure(bg="white"))

    def cam_exposure_slider_focus_out(self, slider_value, entry_wid):
        # Slider doesn't not allow invalid values to be set.
        self.c.cam_exposure = int(slider_value)
        # Update entry widget
        entry_wid.delete(0, tk.END)
        entry_wid.insert(0, self.exposure_to_string(1.0 / self.c.cam_exposure))

    def exposure_to_string(self, exposure_time):
        """
        Converts a camera exposure to a string for presenting in the UI. The time will be
        put into the form 1/x and, if necessary, rounded so that x is an integer.
        """
        if exposure_time != 0:
            return f"1/{int(1.0 / exposure_time)}" if exposure_time != 1 else "1"
        else:
            return str(1 / self.c.cam_exposure_lims[0])

    def display_warning(self, message, delay=4000):
        """Create an unobtrusive warning label that disappears after a delay."""
        n_col, n_row = self.top.grid_size()
        warning_label = tk.Label(self.top, text=message, bg="yellow", height=1)
        warning_label.grid(row=n_row, column=0, columnspan=n_col, sticky=tk.N + tk.E + tk.W + tk.S)
        self.top.after(delay, warning_label.destroy)

    def get_channel_dropdown_label(self, ch_num, ch_name):
        return f"Ch {ch_num!s}: {ch_name}"

    def apply(self):
        self.apply_changes = True
        self.close_window(False)

    def cancel(self):
        self.apply_changes = False
        self.close_window(False)

    def close_window(self, ask_to_apply_changes=True):
        """Close the top window."""
        if ask_to_apply_changes:
            apply_on_exit = tk_message_box.askyesnocancel(
                "Confirm exit",
                "Would you like to apply your changes before you exit?",
                parent=self.top,
            )
            if apply_on_exit is None:
                return
            elif apply_on_exit:
                self.apply_changes = True
        self.top.grab_release()
        for wid in self.top.winfo_children():
            wid.destroy()
        self.top.destroy()


class GenericExperimentConfigUi:
    def __init__(self, parent, expt_config, expt_config_reader: ExperimentConfigReader):
        """
        This class provides a UI for allowing a generic experiment configuration to be
        changed by loading a different config file. There are no options to modify the
        config file in the UI but this can be done by editing the config file directly,
        saving it and then reloading it into the UI.
        """

        # A flag that denotes is the user confirms or cancels edits they make in this window when exiting.
        self.apply_changes = False

        self.experiment_config = self.conf = copy.copy(expt_config)
        self.conf_reader = copy.copy(expt_config_reader)
        self.top = self.configure_window(parent)

        self.top.wm_title("Experiment configuration")
        self.top.grab_set()
        # Changes the close button to call my close function.
        self.top.protocol("WM_DELETE_WINDOW", self.close_window)

    def configure_window(self, parent):
        """
        Build all the widget enteries for this UI.
        """
        top = tk.Toplevel(parent)
        frame = tk.Frame(top)

        label_frame_font_opts = ("Helvetica", 12, "bold", "italic")
        file_frame = tk.LabelFrame(top, text="Config File Locations", font=label_frame_font_opts)

        widgets = []

        frame = tk.LabelFrame(file_frame, text="Experimental Config", font=label_frame_font_opts)

        fname_frame = tk.Frame(frame)

        fname_wid = ExperimentalParamFrame(
            fname_frame,
            label="Config file location:",
            initial_value=self.conf_reader.fname,
            data_type=str,
            help_text="File path to the config file for this experiment.",
            action=None,
            state=tk.DISABLED,
        )
        fname_wid.pack(side=tk.LEFT)

        icon = Image.open("icons/folder_icon.png").resize((20, 20))
        icon = ImageTk.PhotoImage(icon)
        load_config_button = ImageButton(
            fname_frame,
            image=icon,
            command=lambda wid=fname_wid: self.load_config(wid),
            height=16,
            width=16,
        )
        load_config_button.image_ref = (
            icon  # store the image as a variable in the widget to prevent garbage collection.
        )
        load_config_button.pack(side=tk.RIGHT)

        fname_frame.pack()

        widgets.append(frame)

        for wid in widgets:
            wid.pack()

        button_frame = tk.Frame(top)

        apply_button = tk.Button(
            button_frame, text="Apply", command=self.apply, width=15, bg="green"
        )
        cancel_button = tk.Button(
            button_frame, text="Cancel", command=self.cancel, width=15, bg="red"
        )
        apply_button.grid(row=0, column=0, sticky=tk.E)
        cancel_button.grid(row=1, column=0, sticky=tk.E)

        r = 1
        for frame in [file_frame, button_frame]:
            frame.grid(row=r, column=0, sticky=tk.E + tk.W)
            r += 1

        return top

    def load_config(self, fname_wid: ExperimentalParamFrame):
        fname = tk_file_dialog.askopenfilename(
            parent=self.top, title="Choose a config file", initialdir="configs"
        )

        # Check for empty filenames (i.e. when the user cancelled the action)
        if fname != "":
            self.conf_reader = ExperimentConfigReader(fname)
            self.experiment_config = self.conf_reader.get_correct_config()

            fname_wid.update_entry(fname)

        # Seems to be a tkinter bug that the parent is shown on top after a file dialog - so let's fix that
        self.top.lift(self.top.master)

    def apply(self):
        self.apply_changes = True
        self.close_window(False)

    def cancel(self):
        self.apply_changes = False
        self.close_window(False)

    def close_window(self, ask_to_apply_changes=True):
        """Close the top window."""
        if ask_to_apply_changes:
            apply_on_exit = tk_message_box.askyesnocancel(
                "Confirm exit",
                "Would you like to apply your changes before you exit?",
                parent=self.top,
            )
            if apply_on_exit is None:
                return
            elif apply_on_exit:
                self.apply_changes = True

        self.top.grab_release()
        for wid in self.top.winfo_children():
            wid.destroy()
        self.top.destroy()
