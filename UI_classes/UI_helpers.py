import math
import tkinter as tk
from pathlib import Path
from tkinter import messagebox as tk_message_box

from PIL import Image, ImageTk

# Resolve icon paths relative to the project root (parent of UI_classes/).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ImageButton(tk.Button):
    """Important class to prevent image being garbage collected.
    Usage:
    self.addButton = ImageButton(..., image=icon)
    self.addButton.image_ref=icon
    """

    image_ref: ImageTk.PhotoImage


def load_icon(path: str, size: tuple[int, int] = (30, 30)) -> ImageTk.PhotoImage:
    """Load an icon from *path*, resize it to *size*, and return a PhotoImage.

    If *path* is relative it is resolved against the project root directory so
    that icon loading works regardless of the current working directory.

    The caller must keep a reference to the returned object to prevent
    garbage collection (e.g. ``widget.image_ref = load_icon(...)``).
    """
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = _PROJECT_ROOT / resolved
    return ImageTk.PhotoImage(Image.open(resolved).resize(size))


def arrow_key_increment(widget: tk.Entry, event, data_type: type = float, validate_fn=None):
    """Shared arrow-key increment logic for numeric entry widgets.

    Increments or decrements the value in *widget* based on the cursor position
    relative to the decimal point. The digit under the cursor determines the
    order of magnitude of the change.

    Parameters
    ----------
    widget : tk.Entry
        The entry widget containing the numeric value.
    event : tk.Event
        The key event (must have ``keysym`` of ``"Up"`` or ``"Down"``).
    data_type : type
        ``int`` or ``float`` — controls rounding of the result.
    validate_fn : callable or None
        Optional callback invoked after the value is updated (e.g. to write
        the new value to hardware).
    """
    current_text = widget.get()
    try:
        decimal_index = current_text.index(".")
    except ValueError:
        decimal_index = len(current_text)

    cursor_index = widget.index(tk.INSERT)
    increment_order = decimal_index - cursor_index

    # Track the cursor offset relative to the decimal point so it can be
    # restored correctly even when the number of digits changes.
    offset_from_decimal = cursor_index - decimal_index

    # If the increment order is -1 the cursor is on the decimal point — do nothing.
    if increment_order == -1:
        return

    if increment_order < -1:
        increment_order += 1

    iterator = (
        math.pow(10, increment_order)
        if event.keysym == "Up"
        else -1 * math.pow(10, increment_order)
    )

    ndp = current_text[::-1].find(".")
    if ndp < 0:
        ndp = 0

    new_value = data_type(round(float(current_text) + iterator, ndp))
    widget.delete(0, tk.END)
    widget.insert(0, str(new_value))

    if validate_fn is not None:
        validate_fn(event)

    # Restore cursor at the same position relative to the decimal point.
    new_text = widget.get()
    try:
        new_decimal_index = new_text.index(".")
    except ValueError:
        new_decimal_index = len(new_text)
    new_cursor_index = max(0, min(len(new_text), new_decimal_index + offset_from_decimal))
    widget.icursor(new_cursor_index)


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
