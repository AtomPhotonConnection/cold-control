"""Live experiment dashboard windows.

These ``tk.Toplevel`` windows are displayed while an experiment is running,
providing real-time feedback and a stop button.

Classes:
    AlignmentLiveUI             - MOT Fluorescence Alignment live dashboard.
    PhotonProductionLiveUI      - Photon-production live dashboard with plots.
"""

import time
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

import matplotlib.pyplot as plt
from PIL import Image, ImageTk

from classes.buffered_data_handler import PhotonProductionBufferedDataHandler
from classes.experimental_runner import (
    MotFluorescenceAlignmentExperiment,
    PhotonProductionExperiment,
)
from UI_classes.Experimental_UI import ExperimentalParamFrame
from UI_classes.live_plot_widgets import CountRatePlotLive, StirapHistPlotLive
from UI_classes.UI_helpers import ImageButton


# =======================================================================================
# MARK: Alignment Live UI
# =======================================================================================
class AlignmentLiveUI(tk.Toplevel):
    """Live UI for the MOT Fluorescence Alignment experiment.

    Displays the current fluorescence metric prominently (colour-coded to
    indicate improvement/degradation), a scrollable history of past values,
    and a **Stop** button to end the alignment loop.
    """

    def __init__(
        self,
        parent,
        alignment_experiment: MotFluorescenceAlignmentExperiment,
        **kwargs,
    ):
        tk.Toplevel.__init__(self, parent, **kwargs)

        self.alignment_experiment = alignment_experiment
        self._last_displayed_count: int = 0

        self.wm_title("MOT Fluorescence Alignment — Live")
        self.minsize(420, 480)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # --- Status label ---
        self.status_label = tk.Label(
            self, text="Waiting for first result...", font=("Helvetica", 12)
        )
        self.status_label.pack(pady=(10, 2))

        # --- Shot counter ---
        shot_frame = tk.Frame(self)
        tk.Label(shot_frame, text="Shot:", font=("Helvetica", 12)).pack(side=tk.LEFT)
        self.shot_var = tk.StringVar(value="0")
        tk.Label(shot_frame, textvariable=self.shot_var, font=("Helvetica", 12, "bold")).pack(
            side=tk.LEFT, padx=(5, 0)
        )
        shot_frame.pack(pady=2)

        # --- Large metric display ---
        self.metric_label = tk.Label(self, text="—", font=("Helvetica", 48, "bold"), fg="grey")
        self.metric_label.pack(pady=(5, 0))

        self.metric_name_label = tk.Label(self, text="", font=("Helvetica", 14))
        self.metric_name_label.pack(pady=(0, 5))

        # --- Change indicator ---
        self.change_label = tk.Label(self, text="", font=("Helvetica", 16))
        self.change_label.pack(pady=(0, 10))

        # --- History ---
        history_frame = tk.LabelFrame(self, text="History", font=("Helvetica", 11))
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.history_text = ScrolledText(
            history_frame, height=10, width=45, font=("Courier", 10), state=tk.DISABLED
        )
        self.history_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Stop button ---
        self.stop_button = tk.Button(
            self,
            text="Stop Alignment",
            command=self._stop_experiment,
            bg="red",
            fg="white",
            font=("Helvetica", 14, "bold"),
            height=2,
            width=20,
        )
        self.stop_button.pack(pady=10)

    # ---- Polling -----------------------------------------------------------

    def poll_results(self, delay_ms: int = 500) -> None:
        """Periodically check for new results from the experiment thread."""
        self._update_display()

        if self.alignment_experiment.is_running:
            self.after(delay_ms, lambda: self.poll_results(delay_ms))
        else:
            # Final update then allow closing
            self._update_display()
            self._update_for_finished()

    # ---- Display helpers ---------------------------------------------------

    def _update_display(self) -> None:
        n_results = len(self.alignment_experiment.results)
        self.shot_var.set(str(self.alignment_experiment.shot_count))

        if n_results == 0 or n_results == self._last_displayed_count:
            return

        self._last_displayed_count = n_results
        value = self.alignment_experiment.results[-1]
        label = self.alignment_experiment.current_result_label or "Metric"

        # Update prominent metric display
        self.metric_label.configure(text=f"{value:.6f}")
        self.metric_name_label.configure(text=label)
        self.status_label.configure(text=f"Iteration {n_results} complete")

        # Colour-code direction
        if n_results >= 2:
            prev = self.alignment_experiment.results[-2]
            delta = value - prev
            if delta > 0:
                self.metric_label.configure(fg="green4")
                self.change_label.configure(text=f"\u25b2 +{delta:.6f}", fg="green4")
            elif delta < 0:
                self.metric_label.configure(fg="red")
                self.change_label.configure(text=f"\u25bc {delta:.6f}", fg="red")
            else:
                self.metric_label.configure(fg="grey")
                self.change_label.configure(text="— no change", fg="grey")
        else:
            self.metric_label.configure(fg="blue")
            self.change_label.configure(text="(first measurement)", fg="grey")

        # Append to history
        self.history_text.configure(state=tk.NORMAL)
        self.history_text.insert(tk.END, f"  #{n_results:>3d}   {label} = {value:.6f}\n")
        self.history_text.see(tk.END)
        self.history_text.configure(state=tk.DISABLED)

    def _update_for_finished(self) -> None:
        self.status_label.configure(text="Alignment complete", fg="blue")
        self.stop_button.configure(text="Close", command=self._destroy, bg="grey")

    # ---- Actions -----------------------------------------------------------

    def _stop_experiment(self) -> None:
        self.alignment_experiment.stop()
        self.status_label.configure(text="Stopping after current iteration...")
        self.stop_button.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        if self.alignment_experiment.is_running:
            self._stop_experiment()
            return  # wait for experiment to finish; poll_results will call _update_for_finished
        self._destroy()

    def _destroy(self) -> None:
        self.grab_release()
        for wid in self.winfo_children():
            wid.destroy()
        self.destroy()


# =======================================================================================
# MARK: Photon Production Live UI
# =======================================================================================
class PhotonProductionLiveUI(tk.Toplevel):
    def __init__(
        self,
        parent,
        photon_production_experiment: PhotonProductionExperiment,
        auto_close=False,
        **kwargs,
    ):
        """Live dashboard for photon-production experiments.

        Shows iteration counter, count-rate plot, STIRAP histogram,
        and stop/close buttons.
        """
        tk.Toplevel.__init__(self, parent, **kwargs)

        self.auto_close = auto_close

        self.photon_production_experiment = photon_production_experiment
        self.data_hander = PhotonProductionBufferedDataHandler(
            t_stirap_length=0.5 * photon_production_experiment.get_total_wfm_time() * 10**6
        )

        # Configure the push function in the experimental runner so we can get data on the fly.
        self.photon_production_experiment.configure_data_queue(self.data_hander.data_queue)
        self.UI_update_started = False

        self.wm_title("Photon production - Live")
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_window)

        butt_opts = {"font": ("Helvetica", 12), "height": 25, "width": 150, "compound": tk.LEFT}

        # add STOP button
        icon = ImageTk.PhotoImage(Image.open("icons/stop_icon.png").resize((30, 30)))
        self.stop_button = ImageButton(
            self,
            image=icon,
            text="Stop experiment",
            command=self.stop_experiment,
            background="red",
            **butt_opts,
        )
        self.stop_button.image_ref = icon

        # add CLOSE button
        icon = ImageTk.PhotoImage(Image.open("icons/delete_icon.png").resize((30, 30)))
        self.close_button = ImageButton(
            self,
            image=icon,
            text="Exit",
            command=self.close_window,
            background="red",
            state=tk.DISABLED,
            **butt_opts,
        )
        self.close_button.image_ref = icon

        # Add a completed iterations counter
        self.completed_iterations_frame = f = tk.Frame(self)
        self.completed_iterations_entry = tk.Entry(f, width=7)
        self.completed_iterations_entry.insert(0, "0")
        self.completed_iterations_entry.configure(state=tk.DISABLED)

        self.completed_iterations_label = tk.Label(
            f, width=20, text="Completed iterations", anchor="w"
        )

        self.completed_iterations_label.grid(row=0, column=0)
        self.completed_iterations_entry.grid(row=0, column=1)

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1, pad=2)

        # add iterations entry
        self.total_iterations_frame = ExperimentalParamFrame(
            self,
            "Total iterations",
            initial_value=photon_production_experiment.iterations,
            data_type=int,
            help_text="The number of times the experimental sequence will be run.",
            action=lambda n_iters: self.photon_production_experiment.set_iterations(n_iters),
        )

        # add MOT time entry
        self.reload_time_frame = ExperimentalParamFrame(
            self,
            "MOT reload time (s):",
            initial_value=self.photon_production_experiment.mot_reload_time,
            data_type=float,
            help_text="The delay between successive iterations.",
            action=lambda reload_time: self.photon_production_experiment.set_mot_reload_time(
                reload_time
            ),
        )

        # add basic analytics (e.g. count rate)
        self.count_rate_wid = tk.Entry(self, width=10, font="Helvetica 44 bold")
        self.count_rate_wid.insert(0, "N/A")

        self.count_rate_plot = CountRatePlotLive(
            self, n_lines=2, line_labels=["Count rate", "half Count rate"]
        )

        self.stirap_hist_plot = StirapHistPlotLive(
            self,
            hist_values=self.data_hander.hist_stirap,
            bin_edges=self.data_hander.hist_stirap_bin_edges,
            width=self.data_hander.t_stirap_length / self.data_hander.n_hist_bins,
        )

        self.completed_iterations_frame.pack()
        self.total_iterations_frame.pack()
        self.reload_time_frame.pack()
        self.count_rate_wid.pack()
        self.stop_button.pack()
        self.close_button.pack()
        self.count_rate_plot.pack(side=tk.LEFT)
        self.stirap_hist_plot.pack(side=tk.RIGHT)

    def poll_live_data(self, delay_ms=1, final_update_timeout_ms=5000, timeout_start_time=None):
        """
        Poll the data_handler for new data. When it is found, update the UI.
        """
        if self.data_hander.new_data_waiting and not self.UI_update_started:
            self.update_display()
        # If the photon_production_experiment is still running, keep polling for data
        if self.photon_production_experiment.is_live:
            self.after(delay_ms, lambda: self.poll_live_data(delay_ms, final_update_timeout_ms))
        # If the photon_production_experiment has finished, wait for any final data to be analysed and
        # poll once for any final data, then stop.
        else:
            if timeout_start_time is None:
                timeout_start_time = time.time()
            if (
                int(self.completed_iterations_entry.get()) != self.total_iterations_frame.value
                and time.time() - timeout_start_time < final_update_timeout_ms * 10**-3
            ):
                self.after(
                    delay_ms,
                    lambda: self.poll_live_data(delay_ms, timeout_start_time=timeout_start_time),
                )
            else:
                if time.time() - timeout_start_time < final_update_timeout_ms * 10**-3:
                    print(
                        f"Final UI update timed out after {final_update_timeout_ms * 10**-3} seconds"
                    )
                self.data_hander.stop_polling_queue()
                self.update_for_finished_experiment()

    def update_display(self):
        print("Updating the display")
        self.UI_update_started = True
        self.data_hander.new_data_waiting = False

        focussed_wid = self.focus_get()
        n_iters = self.data_hander.get_completed_iterations()

        self.count_rate_plot.update_plot([self.data_hander.count_rate], n_iters)
        self.stirap_hist_plot.update_plot(self.data_hander.hist_stirap)

        if focussed_wid is not None:
            focussed_wid.focus_set()

        self.UI_update_started = False

    def update_for_finished_experiment(self):
        if self.auto_close and not self.photon_production_experiment.forced_stop:
            self.close_window()
        else:
            self.stop_button.configure(state=tk.DISABLED)
            self.close_button.configure(state=tk.ACTIVE)

    def stop_experiment(self):
        self.photon_production_experiment.is_live = False
        self.photon_production_experiment.forced_stop = True
        self.update_for_finished_experiment()

    def close_window(self):
        """Close the window — refuses if experiment is still live."""
        if self.photon_production_experiment.is_live:
            return
        plt.close("all")
        self.__destroy()

    def __destroy(self):
        self.grab_release()
        for wid in self.winfo_children():
            wid.destroy()
        self.destroy()
