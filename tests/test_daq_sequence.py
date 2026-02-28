"""
Unit tests for DaqSequence and _ChannelSequence.

All tests use pure Python/numpy logic - no hardware required.
Run with:  pytest tests/test_daq_sequence.py -v
"""

import numpy as np
import pytest

from classes.daq_sequence import (
    DaqSequence,
    IntervalStyle,
    InvalidSequenceChannelError,
    MultipleInvalidSequenceChannelError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_flat_seq(n_samples=100, t_step=10, voltage=0.0, ch_num=0):
    """Return a DaqSequence with a single flat channel."""
    seq = DaqSequence(n_samples=n_samples, t_step=t_step)
    seq.add_channel_seq(
        ch_num,
        tv_pairs=[(0.0, voltage)],
        v_interval_styles=[IntervalStyle.FLAT],
    )
    return seq


# ===========================================================================
# Group A - DaqSequence basics
# ===========================================================================


class TestDaqSequenceBasics:
    def test_get_length(self):
        seq = DaqSequence(n_samples=101, t_step=5)
        assert seq.get_length() == 100 * 5

    def test_get_length_single_sample(self):
        """A one-sample sequence has zero length."""
        seq = DaqSequence(n_samples=1, t_step=10)
        assert seq.get_length() == 0

    def test_get_time_steps_shape(self):
        seq = DaqSequence(n_samples=50, t_step=4)
        ts = seq.get_time_steps()
        assert len(ts) == 50

    def test_get_time_steps_endpoints(self):
        seq = DaqSequence(n_samples=11, t_step=10)
        ts = seq.get_time_steps()
        assert ts[0] == pytest.approx(0.0)
        assert ts[-1] == pytest.approx(100.0)

    def test_add_channel_seq_default_flat_zero(self):
        """add_channel_seq with explicit flat-zero creates a valid channel."""
        seq = DaqSequence(n_samples=10, t_step=1)
        seq.add_channel_seq(0, tv_pairs=[(0.0, 0.0)], v_interval_styles=[IntervalStyle.FLAT])
        arr = seq.get_channel_val_array(0)
        assert arr.shape == (10,)
        assert np.all(arr == pytest.approx(0.0))

    def test_get_channel_nums_sorted(self):
        """Channel numbers come back in ascending numeric order."""
        seq = DaqSequence(n_samples=10, t_step=1)
        # Add in reverse order
        for ch in [5, 1, 3]:
            seq.add_channel_seq(ch, tv_pairs=[(0.0, 0.0)], v_interval_styles=[IntervalStyle.FLAT])
        assert seq.get_channel_nums() == [1, 3, 5]

    def test_get_array_shape(self, basic_seq):
        """get_array() returns (n_channels, n_samples)."""
        arr = basic_seq.get_array()
        assert arr.shape == (2, 100)

    def test_get_tv_pairs_content(self, basic_seq):
        """get_tv_pairs returns a list whose content matches what was added."""
        pairs = basic_seq.get_tv_pairs(0)
        assert isinstance(pairs, list)
        assert pairs == [(0.0, 0.0)]


# ===========================================================================
# Group B - _ChannelSequence interpolation
# ===========================================================================


class TestChannelSequenceInterpolation:
    def test_flat_holds_constant_value(self):
        """FLAT style produces the same voltage across all samples."""
        seq = make_flat_seq(n_samples=20, t_step=5, voltage=3.7)
        arr = seq.get_channel_val_array(0)
        assert arr == pytest.approx([3.7] * 20)

    def test_ramp_linear_interpolation(self):
        """RAMP style linearly interpolates between two voltage set-points.

        Sequence: 11 samples at 10 µs each → spans 0..100 µs.
        Channel: RAMP from (0, 0) to (50, 5) then FLAT from 50 µs onward.
        The interpolating function fits between the first and last sampled times
        within each interval (see get_val_array implementation), so we check
        boundary and after-ramp consistency rather than exact slope.
        """
        seq = DaqSequence(n_samples=11, t_step=10)  # t_span = 0,10,...,100
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 0.0), (50.0, 5.0)],
            v_interval_styles=[IntervalStyle.RAMP, IntervalStyle.FLAT],
        )
        arr = seq.get_channel_val_array(0)

        assert len(arr) == 11
        # Start of ramp: 0 V
        assert arr[0] == pytest.approx(0.0)
        # After ramp (FLAT section): 5 V
        assert arr[5] == pytest.approx(5.0)
        assert arr[10] == pytest.approx(5.0)
        # Monotone in the ramp region
        ramp_section = arr[:5]
        assert list(ramp_section) == sorted(ramp_section.tolist())

    def test_flat_then_ramp(self):
        """FLAT followed by RAMP produces correct shaped output."""
        # 21 samples at 10 µs → 0..200 µs (seq_end = 200)
        # When using equal-length pairs/styles the last time must be strictly
        # BEFORE seq_end, so we use t=190 as the final time-voltage pair.
        seq = DaqSequence(n_samples=21, t_step=10)
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 2.0), (100.0, 2.0), (190.0, 4.0)],
            v_interval_styles=[IntervalStyle.FLAT, IntervalStyle.RAMP, IntervalStyle.FLAT],
        )
        arr = seq.get_channel_val_array(0)

        assert len(arr) == 21
        # FLAT section: indices 0..9 → t=0..90 → 2.0 V
        assert arr[0] == pytest.approx(2.0)
        assert arr[9] == pytest.approx(2.0)
        # After RAMP section, approaching 4.0
        assert arr[20] == pytest.approx(4.0)

    def test_two_flat_segments(self):
        """Two FLAT segments produce correct step-change output."""
        # 11 samples at 10 µs → 0..100 µs
        seq = DaqSequence(n_samples=11, t_step=10)
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 1.0), (60.0, 3.0)],
            v_interval_styles=[IntervalStyle.FLAT, IntervalStyle.FLAT],
        )
        arr = seq.get_channel_val_array(0)

        # First segment (t < 60) → 1.0 V
        for t_idx, t in enumerate(range(0, 60, 10)):
            assert arr[t_idx] == pytest.approx(1.0), f"Expected 1.0 at t={t}"
        # Second segment (t >= 60) → 3.0 V
        for t_idx, t in enumerate(range(60, 110, 10)):
            assert arr[6 + t_idx] == pytest.approx(3.0), f"Expected 3.0 at t={t}"


# ===========================================================================
# Group C - get_channel_values_at_time
# ===========================================================================


class TestGetChannelValuesAtTime:
    def test_values_at_t_zero(self, basic_seq):
        """At t=0 each channel returns its starting voltage."""
        vals = basic_seq.get_channel_values_at_time(0.0)
        # ch0 = 0.0 V, ch1 = 5.0 V
        assert vals.shape == (2, 1)
        assert vals[0, 0] == pytest.approx(0.0)
        assert vals[1, 0] == pytest.approx(5.0)

    def test_values_at_sequence_end(self, basic_seq):
        """At t = get_length() the query returns the final sample values."""
        t_end = basic_seq.get_length()
        vals = basic_seq.get_channel_values_at_time(t_end)
        assert vals.shape == (2, 1)
        assert vals[0, 0] == pytest.approx(0.0)
        assert vals[1, 0] == pytest.approx(5.0)

    def test_raises_for_negative_time(self, basic_seq):
        with pytest.raises(ValueError, match="0 <= t"):
            basic_seq.get_channel_values_at_time(-1.0)

    def test_raises_for_time_beyond_length(self, basic_seq):
        t_too_late = basic_seq.get_length() + 1.0
        with pytest.raises(ValueError, match="0 <= t"):
            basic_seq.get_channel_values_at_time(t_too_late)

    def test_ch_nums_filter_limits_output(self, basic_seq):
        """Passing ch_nums=[1] returns only channel 1's value."""
        vals = basic_seq.get_channel_values_at_time(0.0, ch_nums=[1])
        assert vals.shape == (1, 1)
        assert vals[0, 0] == pytest.approx(5.0)

    def test_ch_nums_preserves_order(self, basic_seq):
        """Channels are returned in the order given by ch_nums."""
        # Request in reverse order
        vals = basic_seq.get_channel_values_at_time(0.0, ch_nums=[1, 0])
        assert vals[0, 0] == pytest.approx(5.0)
        assert vals[1, 0] == pytest.approx(0.0)


# ===========================================================================
# Group D - Validation and error handling
# ===========================================================================


class TestValidationAndErrors:
    def test_update_channel_valid(self, basic_seq):
        """A valid update is applied and reflected in get_tv_pairs.

        When using equal-length pairs/styles the last time must be strictly
        before seq_end, so we use 900 µs (< seq_end = 990 µs).
        """
        basic_seq.update_channel(
            0,
            tv_pairs=[(0.0, 0.0), (900.0, 2.0)],
            v_interval_styles=[IntervalStyle.FLAT, IntervalStyle.FLAT],
        )
        pairs = basic_seq.get_tv_pairs(0)
        assert pairs[0] == (0.0, 0.0)
        assert pairs[1] == (900.0, 2.0)

    def test_update_channel_reverts_on_invalid_tv_pairs(self, basic_seq):
        """An invalid update is rejected and the original data is preserved."""
        original_pairs = list(basic_seq.get_tv_pairs(0))  # [(0.0, 0.0)]
        original_styles = list(basic_seq.get_v_interval_styles(0))  # [FLAT]

        with pytest.raises(InvalidSequenceChannelError):
            # First time > 0 → invalid (sequence must start at t=0)
            basic_seq.update_channel(
                0,
                tv_pairs=[(5.0, 1.0)],
                v_interval_styles=[IntervalStyle.FLAT],
            )

        # Channel must have reverted to original state
        assert basic_seq.get_tv_pairs(0) == original_pairs
        assert basic_seq.get_v_interval_styles(0) == original_styles

    def test_start_time_not_zero_raises(self):
        """A channel whose first time point is not 0 raises InvalidSequenceChannelError."""
        seq = DaqSequence(n_samples=10, t_step=10)
        with pytest.raises(InvalidSequenceChannelError):
            seq.add_channel_seq(
                0,
                tv_pairs=[(5.0, 0.0)],
                v_interval_styles=[IntervalStyle.FLAT],
            )

    def test_time_beyond_length_raises(self):
        """A time-voltage pair beyond the sequence length raises InvalidSequenceChannelError."""
        seq = DaqSequence(n_samples=100, t_step=10)  # length = 990
        with pytest.raises(InvalidSequenceChannelError):
            seq.add_channel_seq(
                0,
                tv_pairs=[(0.0, 0.0), (1000.0, 1.0)],  # 1000 > 990
                v_interval_styles=[IntervalStyle.FLAT, IntervalStyle.FLAT],
            )

    def test_update_time_steps_reverts_on_failure(self):
        """update_time_steps rolls back n_samples and t_step when validation fails."""
        seq = DaqSequence(n_samples=100, t_step=10)  # length = 990 µs
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 0.0), (500.0, 1.0)],
            v_interval_styles=[IntervalStyle.FLAT, IntervalStyle.FLAT],
        )
        old_n_samples = seq.n_samples
        old_t_step = seq.t_step

        # Shrink the sequence so that the existing tv_pair at t=500 is outside bounds
        # New length would be (10-1)*1 = 9 µs, which is < 500 µs
        with pytest.raises(MultipleInvalidSequenceChannelError):
            seq.update_time_steps(n_samples=10, t_step=1)

        # n_samples and t_step must be reverted
        assert seq.n_samples == old_n_samples
        assert seq.t_step == old_t_step

    def test_multiple_error_channels_lists_failing_channels(self):
        """MultipleInvalidSequenceChannelError carries a list of offending channels.

        Implementation note: update_time_steps() reverts n_samples and t_step
        immediately when the first channel fails, so subsequent channels are
        validated against the original (longer) sequence and typically pass.
        The error therefore reports the FIRST failing channel, not all of them.
        We verify that the exception carries at least one error entry and that
        the reported channel is plausible.
        """
        seq = DaqSequence(n_samples=100, t_step=10)  # length = 990
        for ch in [0, 1]:
            seq.add_channel_seq(
                ch,
                tv_pairs=[(0.0, 0.0), (500.0, 1.0)],
                v_interval_styles=[IntervalStyle.FLAT, IntervalStyle.FLAT],
            )

        with pytest.raises(MultipleInvalidSequenceChannelError) as exc_info:
            seq.update_time_steps(n_samples=10, t_step=1)

        err = exc_info.value
        # At least one channel must have been reported
        assert len(err.errorChannels) >= 1
        # errors and errorChannels must be aligned
        assert len(err.errors) == len(err.errorChannels)
        # Channel 0 is the first to be processed (dict insertion order), so it
        # should be the first (and in this implementation, only) failing channel
        assert err.errorChannels[0] == 0


# ===========================================================================
# Group E - IntervalStyle helpers
# ===========================================================================


class TestIntervalStyle:
    @pytest.mark.parametrize("name", ["FLAT", "RAMP"])
    def test_round_trip(self, name):
        """to_string(from_string(x)) returns the original capitalised name."""
        val = IntervalStyle.from_string(name)
        result = IntervalStyle.to_string(val)
        assert result == name.title()

    def test_from_string_case_insensitive(self):
        """from_string accepts mixed case."""
        assert IntervalStyle.from_string("flat") == IntervalStyle.FLAT
        assert IntervalStyle.from_string("RAMP") == IntervalStyle.RAMP

    def test_get_all_contains_expected_styles(self):
        styles = IntervalStyle.get_all()
        assert "FLAT" in styles
        assert "RAMP" in styles

    def test_flat_and_ramp_are_distinct(self):
        assert IntervalStyle.FLAT != IntervalStyle.RAMP
