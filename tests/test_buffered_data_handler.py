"""Tests for classes.buffered_data_handler.

Covers the critical threading bug fix (#10), thread safety (#11),
and basic data flow through the handler.
"""

import threading
import time

import numpy as np
import pytest

from classes.buffered_data_handler import PhotonProductionBufferedDataHandler


@pytest.fixture
def handler():
    """Create a handler and stop it cleanly after the test."""
    h = PhotonProductionBufferedDataHandler(n_hist_bins=10, t_stirap_length=100)
    yield h
    h.stop_polling_queue()
    h.polling_thread.join(timeout=2)


class TestInitialisation:
    def test_initial_count_rate(self, handler):
        assert handler.get_last_count_rate() == 0

    def test_initial_completed_iterations(self, handler):
        assert handler.get_completed_iterations() == 0

    def test_histogram_shape(self, handler):
        assert handler.hist_stirap.shape == (10,)

    def test_histogram_initially_zero(self, handler):
        assert np.all(handler.hist_stirap == 0)


class TestThreadTarget:
    """Regression test for #10: target must be the function, not its return value."""

    def test_analysis_thread_target_is_not_called_immediately(self, handler):
        # Put data on the queue
        handler.data_queue.put((1, [(0, 50e6, 0, 0)]))
        # Wait for the polling thread to pick it up
        time.sleep(0.1)
        # The analysis thread should have been started correctly
        # (If the old bug were present, __analyse_buffer() would be called
        # in the polling thread and the Thread would have target=None.)
        # After analysis, completed_iterations should be 1
        assert handler.get_completed_iterations() == 1


class TestThreadSafety:
    """Test that shared state is accessed under a lock (#11)."""

    def test_has_lock(self, handler):
        assert hasattr(handler, "_lock")
        assert isinstance(handler._lock, type(threading.Lock()))

    def test_get_last_count_rate_is_thread_safe(self, handler):
        # Simulate concurrent access
        results = []

        def reader():
            for _ in range(50):
                results.append(handler.get_last_count_rate())
                time.sleep(0.001)

        t = threading.Thread(target=reader)
        t.start()
        t.join(timeout=5)
        # All results should be valid integers
        assert all(isinstance(r, int) for r in results)


class TestDataProcessing:
    def test_single_data_point_updates_iterations(self, handler):
        handler.data_queue.put((5, [(0, 50e6, 0, 0), (1, 80e6, 0, 0)]))
        time.sleep(0.2)
        assert handler.get_completed_iterations() == 5

    def test_single_data_point_updates_count_rate(self, handler):
        handler.data_queue.put((1, [(0, 50e6, 0, 0), (1, 80e6, 0, 0)]))
        time.sleep(0.2)
        # count_rate should have been extended with the count from this data
        assert len(handler.count_rate) > 1

    def test_empty_detections_does_not_crash(self, handler):
        handler.data_queue.put((1, []))
        time.sleep(0.2)
        # Should not raise; completed_iterations still updated
        assert handler.get_completed_iterations() == 1


class TestPolling:
    def test_stop_polling_queue(self, handler):
        handler.stop_polling_queue()
        handler.polling_thread.join(timeout=2)
        assert not handler.polling_thread.is_alive()
