import tkinter as tk
from tkinter import messagebox as tk_message_box

from PIL import Image, ImageTk


class ImageButton(tk.Button):
    """Important class to prevent image being garbage collected.
    Usage:
    self.addButton = ImageButton(..., image=icon)
    self.addButton.image_ref=icon
    """

    image_ref: ImageTk.PhotoImage


def load_icon(path: str, size: tuple[int, int] = (30, 30)) -> ImageTk.PhotoImage:
    """Load an icon from *path*, resize it to *size*, and return a PhotoImage.

    The caller must keep a reference to the returned object to prevent
    garbage collection (e.g. ``widget.image_ref = load_icon(...)``).
    """
    return ImageTk.PhotoImage(Image.open(path).resize(size))


class BaseConfigDialog:
    """Mixin that provides the standard apply / cancel / close_window pattern
    shared by all configuration dialog windows in the application.

    Subclasses should:
      1. Call ``BaseConfigDialog.__init__(self, parent, title)`` early in their
         own ``__init__``.
      2. Override ``configure_window(parent)`` to build the dialog contents
         inside ``self.top``.

    The mixin handles:
      * Creating the ``tk.Toplevel``, setting ``grab_set`` and
        ``WM_DELETE_WINDOW``.
      * The ``apply_changes`` flag, ``apply()``, ``cancel()``, and
        ``close_window()`` with yes/no/cancel confirmation.
      * Widget cleanup and ``grab_release`` on close.
    """

    apply_changes: bool
    top: tk.Toplevel

    def __init__(self, parent, title: str = "Configuration"):
        self.apply_changes = False
        self.top = tk.Toplevel(parent)
        self.top.wm_title(title)
        self.top.grab_set()
        self.top.protocol("WM_DELETE_WINDOW", self.close_window)

    # -- Override point -------------------------------------------------------

    def configure_window(self, parent):
        """Build all widget entries for this dialog.  Override in subclasses."""
        raise NotImplementedError

    # -- apply / cancel / close -----------------------------------------------

    def apply(self):
        self.apply_changes = True
        self.close_window(ask_to_apply_changes=False)

    def cancel(self):
        self.apply_changes = False
        self.close_window(ask_to_apply_changes=False)

    def close_window(self, ask_to_apply_changes: bool = True):
        """Close the top window, optionally prompting the user first."""
        if ask_to_apply_changes:
            result = tk_message_box.askyesnocancel(
                "Confirm exit",
                "Would you like to apply your changes before you exit?",
                parent=self.top,
            )
            if result is None:
                return  # user pressed Cancel — stay open
            elif result:
                self.apply_changes = True
        self.top.grab_release()
        for wid in self.top.winfo_children():
            wid.destroy()
        self.top.destroy()

    # -- Helpers --------------------------------------------------------------

    def display_warning(self, message: str, delay: int = 4000):
        """Create an unobtrusive warning label that disappears after *delay* ms."""
        n_col, n_row = self.top.grid_size()
        warning_label = tk.Label(self.top, text=message, bg="yellow", height=1)
        warning_label.grid(row=n_row, column=0, columnspan=n_col, sticky=tk.N + tk.E + tk.W + tk.S)
        self.top.after(delay, warning_label.destroy)

    @staticmethod
    def get_apply_cancel_buttons(parent, apply_cmd, cancel_cmd) -> tk.Frame:
        """Return a frame containing Apply and Cancel buttons."""
        button_frame = tk.Frame(parent)
        tk.Button(button_frame, text="Apply", command=apply_cmd, width=15, bg="green").grid(
            row=0, column=0, sticky=tk.E
        )
        tk.Button(button_frame, text="Cancel", command=cancel_cmd, width=15, bg="red").grid(
            row=1, column=0, sticky=tk.E
        )
        return button_frame
