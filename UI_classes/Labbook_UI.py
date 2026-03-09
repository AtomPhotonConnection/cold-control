"""
Created on 25 Mar 2016

@author: tombarrett
"""

from __future__ import annotations

import re
import time
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

from PIL import Image, ImageTk

from UI_classes.UI_helpers import ImageButton


class LabbookUI(tk.LabelFrame):
    def __init__(
        self,
        parent,
        labbook_dir=None,
        text="Labbook",
        f_ext=".txt",
        font=("Helvetica", 16),
        **kwargs,
    ):
        if labbook_dir is None:
            labbook_dir = Path.cwd() / "labbook"
        tk.LabelFrame.__init__(self, parent, text=text, font=font, **kwargs)

        self.parent = parent

        self.textWid = scrolledtext.ScrolledText(self)

        self.labbook_dir = labbook_dir
        self.fExt = f_ext

        r = re.compile(r"\d{1,2}-\d{1,2}-\d{2,4}.*" + self.fExt)
        self.dropdownOptions = self.sort_dates(
            [
                y.group()
                for y in [r.match(x.name) for x in self.labbook_dir.iterdir()]
                if y is not None
            ]
        )
        self.dropdownVar = tk.StringVar()

        self.configure_for_current_date()

        top_frame = tk.Frame(self)

        self.dropdown = ttk.OptionMenu(
            top_frame,
            self.dropdownVar,
            self.dropdownVar.get(),
            *self.dropdownOptions,
            command=lambda x: self.labbook_selected(self.dropdownVar),
            style="Files.TMenubutton",
        )

        icon = Image.open("icons/refresh_icon.png").resize((20, 20))
        icon = ImageTk.PhotoImage(icon)
        self.refreshButton = ImageButton(
            top_frame, image=icon, command=self.configure_for_current_date, height=20, width=20
        )
        self.refreshButton.image_ref = icon

        self.dropdown.pack(side=tk.LEFT)
        self.refreshButton.pack(side=tk.RIGHT)

        top_frame.pack(side=tk.TOP, fill=tk.X, padx=15, pady=5)
        self.textWid.pack(expand=1)

    def configure_for_current_date(self):
        self.fname: Path | None = None
        for fname in [time.strftime("%d-%m-%y") + self.fExt, time.strftime("%d-%m-%Y") + self.fExt]:
            if fname in self.dropdownOptions:
                self.dropdownVar.set(fname)
                self.fname = self.labbook_dir / fname
                break
        if self.fname is None:
            self.dropdownOptions.insert(0, time.strftime("%d-%m-%y") + self.fExt)
            self.dropdownVar.set(self.dropdownOptions[0])
            self.fname = self.labbook_dir / time.strftime("%d-%m-%y") / self.fExt
            # File doesn't exist so let's make it!
            self.fname.parent.mkdir(parents=True, exist_ok=True)
            self.fname.open("a").close()

        self.open()
        self.autosave()

    def labbook_selected(self, dropdown_var):
        self.write()
        self.fname = self.labbook_dir / dropdown_var.get()
        self.open()

    def open(self):
        assert self.fname is not None
        with self.fname.open() as f:
            print("open: ", self.fname)
            self.textWid.delete(1.0, tk.END)
            self.textWid.insert(tk.END, f.read())

    def write(self):
        assert self.fname is not None
        with self.fname.open("w") as f:
            print("write: ", self.fname)
            f.write(self.textWid.get("1.0", tk.END))

    def autosave(self):
        """Register a write event to save the labbook every 5 minutes"""
        self.write()
        self.after(300000, self.autosave)

    def sort_dates(self, date_files):
        """Takes a list of date files as strings of the form dd-mm-yy.txt or dd-mm-yyyy.txt
        and sorts them (earliest to latest)"""

        def sorting(filename):
            split = filename.split(".")[0].split("-")
            return split[2][-2:], split[1], split[0]

        date_files.sort(key=sorting, reverse=True)
        return date_files
