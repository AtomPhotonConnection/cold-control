"""Buffered data handler for photon-production experiments.

This module contains pure data-processing logic with no tkinter dependency.
It polls a queue fed by the experiment thread, accumulates count-rate data
and builds a STIRAP histogram for the live UI to read.

Classes:
    PhotonProductionBufferedDataHandler
"""

import contextlib
import logging
import queue
import threading
import time

import numpy as np

logger = logging.getLogger(__name__)


class PhotonProductionBufferedDataHandler:
    def __init__(self, n_hist_bins: int = 30, t_stirap_length: float = 800):

        self.data_queue: queue.Queue = queue.Queue()
        self.analysis_buffer: list = []
        self.data_analysis_thread = threading.Thread()

        self._lock = threading.Lock()
        self.new_data_waiting = False
        self.completed_iterations = 0
        self.count_rate: list[int] = [0]

        # Configure the stirap histogram: n_bins and total length (in microseconds).
        self.n_hist_bins = n_hist_bins
        self.t_stirap_length = t_stirap_length

        self.hist_stirap, self.hist_stirap_bin_edges = np.histogram(
            [], bins=self.n_hist_bins, range=(0, t_stirap_length)
        )

        self.keep_polling_queue = True
        self.polling_thread = self.start_polling_queue()

    def poll_queue(self, delay_ms: int = 1) -> None:
        """Poll the data queue and start analysis if data is available.

        Data will be tuple of (throw_number, [(channel, t_Stirap, t_mot, pulse_number),...])
        """
        if not self.data_analysis_thread.is_alive():
            # Pull all queued data into analysis buffer
            self.analysis_buffer = []
            if not self.data_queue.empty():
                with contextlib.suppress(queue.Empty):
                    self.analysis_buffer.append(self.data_queue.get_nowait())
                self.data_analysis_thread = threading.Thread(
                    name="Photon_production_buffered_data_handler.__analyse_buffer",
                    target=self.__analyse_buffer,
                )

                self.data_analysis_thread.start()

    def start_polling_queue(self, delay_ms: int = 1) -> threading.Thread:
        """Start a background thread that continuously polls the data queue."""

        def poll_loop():
            while self.keep_polling_queue:
                self.poll_queue()
                time.sleep(delay_ms * 10**-3)

        thread = threading.Thread(
            name="Photon_production_buffered_data_handler.__poll_queue", target=poll_loop
        )
        thread.start()
        return thread

    def stop_polling_queue(self) -> None:
        """Signal the polling thread to stop."""
        self.keep_polling_queue = False

    def __analyse_buffer(self) -> None:
        """Analyse the current analysis buffer, updating shared state under a lock."""

        with self._lock:
            self.completed_iterations = self.analysis_buffer[-1][0]
            self.count_rate += [len(data[1]) for data in self.analysis_buffer]

        # Get histogram contributions from new data.  list slicing is to get t_Stirap only
        # and *10**6 converts from picoseconds to microseconds.
        if self.analysis_buffer != []:
            t_stiraps = (
                np.concatenate(
                    [
                        np.array(data[1])[:, 1] if data[1] != [] else np.array([])
                        for data in self.analysis_buffer
                    ]
                )
                * 10**-6
            )
            with self._lock:
                self.hist_stirap += np.histogram(
                    t_stiraps, bins=self.n_hist_bins, range=(0, self.t_stirap_length)
                )[0]
                self.new_data_waiting = True
        else:
            logger.debug("No detections on counter channels in buffer.")

    def get_last_count_rate(self) -> int:
        """Return the most recent count rate (thread-safe)."""
        with self._lock:
            return self.count_rate[-1]

    def get_completed_iterations(self) -> int:
        """Return the number of completed iterations (thread-safe)."""
        with self._lock:
            logger.debug("returning comp iters: %d", self.completed_iterations)
            return self.completed_iterations
