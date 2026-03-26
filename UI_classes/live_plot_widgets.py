"""Reusable live-updating matplotlib plot widgets for embedding in tkinter UIs.

Classes:
    StirapHistPlotLive  - live bar-chart for STIRAP photon-arrival histograms.
    CountRatePlotLive   - live line-plot for photon count-rate over iterations.
"""

import tkinter as tk

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class StirapHistPlotLive(tk.LabelFrame):
    def __init__(
        self,
        parent,
        hist_values,
        bin_edges,
        width,
        xlabel="t (us)",
        ylabel="counts",
        text="Stirap hist.",
        font=("Helvetica", 16),
        **kwargs,
    ):
        tk.LabelFrame.__init__(self, parent, text=text, font=font, **kwargs)

        self.bin_edges = bin_edges
        self.bin_centers = np.array(
            [bin_edges[i] + bin_edges[i + 1] for i in range(len(bin_edges) - 1)]
        )
        self.width = width

        self.fig, self.ax = plt.subplots()

        self.rects = self.ax.bar(self.bin_edges[:-1], hist_values, self.width, color="blue")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def update_plot(self, hist_values):
        """Update plot with new data."""
        for i, rect in enumerate(self.rects):
            rect.set_height(hist_values[i])
        self.ax.set_ylim(0.0, (max(hist_values) + 9) // 10 * 10)
        self.canvas.draw()


class CountRatePlotLive(tk.LabelFrame):
    def __init__(
        self,
        parent,
        n_lines=1,
        line_labels=None,
        text="Count rate",
        font=("Helvetica", 16),
        n_iters_update_buffer=10,
        **kwargs,
    ):
        if line_labels is None:
            line_labels = ["Count rate"]
        tk.LabelFrame.__init__(self, parent, text=text, font=font, **kwargs)

        self.fig, self.ax = plt.subplots()

        self.y_max = 1
        self.n_iters_update_buffer = n_iters_update_buffer
        self.n_iters_update_counter = 0

        # A dictionary to store the 2dLine matplotlib objects relating to each plotted channel
        self.lines = []

        for label in line_labels[:n_lines]:
            (line,) = self.ax.plot([0], [0], label=label)
            self.lines.append(line)

        self.ax.set_xlim((0, self.n_iters_update_buffer))
        self.ax.set_ylim((0, self.y_max))

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def update_plot(self, lines_data, n_iters):
        """Update each line plot with new data."""
        x_data = range(n_iters + 1)
        for data, line in zip(lines_data, self.lines, strict=True):
            if max(data) > self.y_max:
                self.y_max = max(data)
                self.ax.set_ylim((0, self.y_max * 1.05))

            line.set_ydata(data)
            line.set_xdata(x_data)

            if self.n_iters_update_counter >= self.n_iters_update_buffer:
                self.ax.set_xlim((0, len(x_data) + self.n_iters_update_buffer))
                self.n_iters_update_counter = 0
            else:
                self.n_iters_update_counter += 1
            try:
                self.canvas.draw()
            except RuntimeError as err:
                # Sometimes data gets out of sync and the plot fails.
                # Just print a message and move on - hopefully it will re-sync!
                print("Runtime error caught and ignored:", str(err))
                pass
