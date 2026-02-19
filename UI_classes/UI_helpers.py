import tkinter as tk

from PIL import ImageTk


class ImageButton(tk.Button):
    """Important class to prevent image being garbage collected.
    Usage: 
    self.addButton = ImageButton(..., image=icon)
    self.addButton.image_ref=icon
    """
    image_ref: ImageTk.PhotoImage
