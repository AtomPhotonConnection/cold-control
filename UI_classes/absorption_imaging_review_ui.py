"""Post-experiment review UI for absorption imaging.

Classes:
    AbsorptionImagingReviewUI - Displays processed/raw/background images
        and lets the user save them with notes or discard.
"""

import re
import tkinter as tk
from tkinter import messagebox as tk_message_box
from tkinter.scrolledtext import ScrolledText
from typing import Any

from PIL import Image, ImageTk

from classes.experimental_runner import AbsorptionImagingExperiment


class AbsorptionImagingReviewUI(tk.Toplevel):
    def __init__(
        self, parent, absorption_imaging_experiment: AbsorptionImagingExperiment, **kwargs
    ):
        """
        This object the absorption images taken and offers the user the chance to save them with notes or discard them.
        """
        tk.Toplevel.__init__(self, parent, **kwargs)

        self.absorption_imaging_experiment = absorption_imaging_experiment

        if not self.absorption_imaging_experiment.results_ready:
            raise Exception(
                "The absorption imaging experiment has not been run yet. There are no results to review."
            )

        self.wm_title("Absorption imaging review")
        self.grab_set()
        # Changes the close button to call my close function.
        self.protocol("WM_DELETE_WINDOW", self.close_window)

        img_arrs, bkg_arrs, raw_images, labels = self.absorption_imaging_experiment.get_results()

        if img_arrs is None and bkg_arrs is None:
            raise Exception("There are no images to review")

        self.image_types_list = []
        self.images_frames_dict = {}
        self.image_frame_opts = {
            "bd": 2,
            "relief": tk.SUNKEN,
            "font": ("Helvetica", 16),
            "img_dims": (480, 360),
            "img_buffer": 30,
        }
        if img_arrs is not None:
            self.image_types_list.append("Processed images")
            self.images_frames_dict[self.image_types_list[-1]] = self.__get_images_frame(
                img_arrs, labels, text=self.image_types_list[-1], **self.image_frame_opts
            )
        if bkg_arrs is not None:
            self.image_types_list.append("Average backrounds")
            self.images_frames_dict[self.image_types_list[-1]] = self.__get_images_frame(
                bkg_arrs, labels, text=self.image_types_list[-1], **self.image_frame_opts
            )
        if raw_images is not None:
            self.image_types_list.append("Raw images")
            self.images_frames_dict[self.image_types_list[-1]] = self.__get_images_frame(
                raw_images, labels, text=self.image_types_list[-1], **self.image_frame_opts
            )

        self.images_frames_dropdown = self.__get_image_type_dropdown()

        self.save_notes_frame, self.save_notes_wid = self.__get_save_notes_frame(
            text="Notes", font=("Helvetica", 16)
        )

        self.buttons_frame = self.__get_buttons_frame()

        self.image_frame_grid_opts = {
            "row": 0,
            "column": 0,
            "columnspan": 3,
            "sticky": tk.N + tk.S + tk.E + tk.W,
        }

        self.images_frames_dict[self.image_types_list[0]].grid(**self.image_frame_grid_opts)
        self.displayed_images_frame_key = self.image_types_list[0]

        self.images_frames_dropdown.grid(row=1, column=0, sticky=tk.N)
        self.save_notes_frame.grid(row=1, column=1, sticky=tk.N + tk.S + tk.E + tk.W)
        self.buttons_frame.grid(row=1, column=2, sticky=tk.N)

        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=3)
        self.columnconfigure(2, weight=2)

        self.grid_propagate(False)
        self.configure(
            width=3 * self.image_frame_opts["img_dims"][0]
            + 2 * self.image_frame_opts["img_buffer"],
            height=1.5 * self.image_frame_opts["img_dims"][1],
        )

    def __get_images_frame(self, img_arrs, labels, img_dims=(480, 360), img_buffer=30, **kwargs):
        """
        Returns a scrollable frame that contains all the images from img_arrs stacked horizontally.
            img_arrs - The images to display as arrays of pixel values.
            img_dims - The dimensions (width, height) in pixels to display the images in.
            img_buffer - How many pixels to leave between images.
            kwargs - Keyword arguments that are passed straight through to the returned LabelFrame.
        """
        images_frame = tk.LabelFrame(self, **kwargs)
        images_frame.grid_rowconfigure(0, weight=1)
        images_frame.grid_columnconfigure(0, weight=1)

        x_scrollbar = tk.Scrollbar(images_frame, orient=tk.HORIZONTAL)
        x_scrollbar.grid(row=1, column=0, sticky=tk.E + tk.W)

        images_canvas = tk.Canvas(images_frame, bd=0, xscrollcommand=x_scrollbar.set)

        images_canvas.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        x_scrollbar.config(command=images_canvas.xview)

        images_canvas._image_cache = []  # type: ignore[attr-defined]
        canvas_img_items = []
        for i, (img_arr, label) in enumerate(
            sorted(
                zip(img_arrs, labels, strict=True),
                key=lambda x: int(re.findall(r"\d+", str(x[1]))[-1]),
            )
        ):
            x_coord, y_coord = 0.5 * img_dims[0] + i * (img_dims[0] + img_buffer), img_dims[1]

            img = ImageTk.PhotoImage(Image.fromarray(img_arr).resize(img_dims))
            canvas_img_items.append(
                images_canvas.create_image(x_coord, y_coord, anchor=tk.S, image=img, tags=label)
            )
            images_canvas._image_cache.append(img)  # type: ignore[attr-defined]  # avoid garbage collection

            images_canvas.create_text(x_coord, y_coord, anchor=tk.N, text=label)

        images_canvas.config(scrollregion=images_canvas.bbox(tk.ALL))
        images_canvas.configure(height=images_canvas.bbox(tk.ALL)[-1])

        return images_frame

    def __get_image_type_dropdown(self):
        """
        Get a dropdown of all available images frames.
        """
        self.image_type_var = var = tk.StringVar()
        var.set(next(iter(self.images_frames_dict.keys())))

        return tk.OptionMenu(
            self,
            var,
            *self.images_frames_dict.keys(),
            command=lambda x=var: self.__image_type_dropdown_selected(x),
        )

    def __image_type_dropdown_selected(self, key):
        """
        Hide any widgets that are currently displayed where we want the images to be, then display the images frame.
        """
        # Remove current frame and display selected frame
        frame_grid = self.images_frames_dict.get(self.displayed_images_frame_key)
        if frame_grid is not None:
            frame_grid.grid_remove()
        frame_no_grid = self.images_frames_dict.get(key)
        if frame_no_grid is not None:
            frame_no_grid.grid(**self.image_frame_grid_opts)
        self.displayed_images_frame_key = key

    def __get_save_notes_frame(self, **kwargs):
        """
        Returns a frame containing a user editable text field.  Notes entered into this field will be saved along with the images.
        """
        save_notes_frame = tk.LabelFrame(self, **kwargs)
        save_notes_wid = ScrolledText(save_notes_frame)
        save_notes_wid.pack(expand=1)
        return save_notes_frame, save_notes_wid

    def __get_buttons_frame(self):
        """
        A frame containing the action buttons for the UI.
        """
        buttons_frame = tk.Frame(self)

        button_opts: dict[str, Any] = {"width": 25, "padx": 3, "pady": 3}
        save_button = tk.Button(
            buttons_frame, text="Save", command=self.save, bg="green", **button_opts
        )
        discard_button = tk.Button(
            buttons_frame,
            text="Discard",
            command=lambda: self.close_window(ask_to_save_images=False),
            bg="red",
            **button_opts,
        )

        save_button.pack(side=tk.TOP)
        discard_button.pack(side=tk.BOTTOM)
        return buttons_frame

    def save(self):
        """
        Save the images and close the UI.
        """
        self.absorption_imaging_experiment.save_processed_images(
            notes=self.save_notes_wid.get(1.0, tk.END)
        )
        self.close_window(ask_to_save_images=False)

    def close_window(self, ask_to_save_images=True):
        """Close the top window."""
        if ask_to_save_images:
            save_on_exit = tk_message_box.askyesnocancel(
                "Confirm exit", "Would you like to save these images?"
            )
            if save_on_exit is None:
                # A bug that puts the parent back on top even though it doesn't have focus - fixed here
                self.lift()
                return
            elif save_on_exit:
                self.save()
        self.grab_release()
        for wid in self.winfo_children():
            wid.destroy()
        self.destroy()
