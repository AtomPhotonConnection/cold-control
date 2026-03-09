"""
Created on 10 Apr 2016

@author: Tom Barrett
"""

import contextlib
import tkinter as tk


class ToolTip:
    def __init__(self, widget, text, open_delay=2000):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.text = text
        self.openDelay = open_delay
        self.x = self.y = 0

    def update_text(self, text):
        self.text = text

    def spawntip(self):
        self.id = self.widget.after(self.openDelay, self.showtip)

    def showtip(self):
        """Display text in tooltip window"""
        if self.tipwindow or not self.text:
            return
        x, y, _cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 27
        y = y + cy + self.widget.winfo_rooty() + 27
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        # For Mac OS
        with contextlib.suppress(tk.TclError):
            tw.tk.call(
                "::tk::unsupported::MacWindowStyle",
                "style",
                tw._w,  # type: ignore[attr-defined]
                "help",
                "noActivates",
            )
        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            font=("tahoma", 8, "normal"),
        )
        label.pack(ipadx=1)

    def hidetip(self):
        try:
            self.widget.after_cancel(self.id)
        except Exception:
            pass
        finally:
            tw = self.tipwindow
            self.tipwindow = None
            if tw:
                tw.destroy()


def create_tool_tip(widget, text, open_delay=1000):
    tool_tip = ToolTip(widget, text, open_delay)

    def enter(event):
        tool_tip.spawntip()

    def leave(event):
        tool_tip.hidetip()

    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)
    return tool_tip
