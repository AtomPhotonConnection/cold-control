"""
Edge-case unit tests for DaqSequence.

These complement the core tests in test_daq_sequence.py with boundary
conditions and less common scenarios.

Run with:  pytest tests/test_daq_sequence_edge_cases.py -v
"""

import pytest

from classes.daq_sequence import (
    DaqSequence,
    IntervalStyle,
    InvalidSequenceChannelError,
)


class TestDaqSequenceEdgeCases:
    """Edge case tests for DaqSequence."""

    def test_single_sample_sequence(self):
        """Sequence with a single sample has zero length."""
        seq = DaqSequence(1, 10)
        assert seq.get_length() == 0

    def test_first_time_must_be_zero(self):
        """Adding channel with first time != 0 should raise."""
        seq = DaqSequence(100, 10)
        with pytest.raises(InvalidSequenceChannelError):
            seq.add_channel_seq(
                0,
                tv_pairs=[(5.0, 1.0)],
                v_interval_styles=[IntervalStyle.FLAT],
            )

    def test_last_time_exceeds_length(self):
        """Adding channel where last time > sequence length should raise."""
        seq = DaqSequence(100, 10)  # length = 990
        with pytest.raises(InvalidSequenceChannelError):
            seq.add_channel_seq(
                0,
                tv_pairs=[(0.0, 0.0), (10000.0, 5.0)],
                v_interval_styles=[IntervalStyle.FLAT, IntervalStyle.RAMP],
            )

    def test_ramp_full_sequence(self):
        """RAMP style linearly interpolates across the entire sequence."""
        seq = DaqSequence(101, 1)  # length = 100
        # Equal-length: 2 pairs + 2 styles, last style FLAT with last time < length
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 0.0), (99.0, 10.0)],
            v_interval_styles=[IntervalStyle.RAMP, IntervalStyle.FLAT],
        )
        arr = seq.get_channel_val_array(0)
        assert arr[0] == pytest.approx(0.0)
        assert arr[50] == pytest.approx(5.05, abs=0.15)
        # Last sample should be the FLAT extension of 10.0
        assert arr[100] == pytest.approx(10.0)

    def test_flat_then_ramp_boundary(self):
        """Sequence with FLAT then RAMP sections preserves boundary values."""
        seq = DaqSequence(101, 1)  # length = 100
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 5.0), (50.0, 5.0), (99.0, 10.0)],
            v_interval_styles=[IntervalStyle.FLAT, IntervalStyle.RAMP, IntervalStyle.FLAT],
        )
        arr = seq.get_channel_val_array(0)
        # First 50 samples should be flat at 5.0
        assert arr[0] == pytest.approx(5.0)
        assert arr[25] == pytest.approx(5.0)
        # Last sample should be FLAT at 10.0
        assert arr[100] == pytest.approx(10.0)

    def test_update_channel_rollback_on_error(self):
        """update_channel reverts to old state if validation fails."""
        seq = DaqSequence(100, 10)
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 0.0)],
            v_interval_styles=[IntervalStyle.FLAT],
        )

        old_pairs = seq.get_tv_pairs(0)

        with pytest.raises(InvalidSequenceChannelError):
            # First time != 0 → invalid
            seq.update_channel(
                0,
                tv_pairs=[(5.0, 1.0)],
                v_interval_styles=[IntervalStyle.FLAT],
            )

        # Should still have original values
        assert seq.get_tv_pairs(0) == old_pairs

    def test_get_channel_values_at_negative_time(self):
        """get_channel_values_at_time raises ValueError for negative time."""
        seq = DaqSequence(100, 10)
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 0.0)],
            v_interval_styles=[IntervalStyle.FLAT],
        )

        with pytest.raises(ValueError):
            seq.get_channel_values_at_time(-1.0)

    def test_get_channel_values_at_time_beyond_length(self):
        """get_channel_values_at_time raises ValueError for time beyond length."""
        seq = DaqSequence(100, 10)  # length = 990
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 0.0)],
            v_interval_styles=[IntervalStyle.FLAT],
        )

        with pytest.raises(ValueError):
            seq.get_channel_values_at_time(1000.0)

    def test_empty_sequence_get_array(self):
        """get_array on sequence with no channels returns empty array."""
        seq = DaqSequence(100, 10)
        arr = seq.get_array()
        # With no channels, the list comprehension produces an empty list
        assert arr.shape == (0,)

    def test_multiple_channels(self):
        """Multiple channels can be added to the same sequence."""
        seq = DaqSequence(100, 10)  # length = 990
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 1.0)],
            v_interval_styles=[IntervalStyle.FLAT],
        )
        seq.add_channel_seq(
            1,
            tv_pairs=[(0.0, 2.0)],
            v_interval_styles=[IntervalStyle.FLAT],
        )
        seq.add_channel_seq(
            5,
            tv_pairs=[(0.0, 3.0)],
            v_interval_styles=[IntervalStyle.FLAT],
        )

        assert sorted(seq.get_channel_nums()) == [0, 1, 5]
        arr = seq.get_array()
        assert arr.shape == (3, 100)

    def test_update_time_steps(self):
        """update_time_steps changes n_samples and t_step."""
        seq = DaqSequence(100, 10)
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 0.0)],
            v_interval_styles=[IntervalStyle.FLAT],
        )

        seq.update_time_steps(
            200,
            5,
            channels_to_update={
                0: ([(0.0, 0.0)], [IntervalStyle.FLAT]),
            },
        )

        assert seq.n_samples == 200
        assert seq.t_step == 5

    def test_get_time_steps_array(self):
        """get_time_steps returns correct time array."""
        seq = DaqSequence(11, 10)  # 0, 10, 20, ..., 100
        ts = seq.get_time_steps()
        assert len(ts) == 11
        assert ts[0] == pytest.approx(0.0)
        assert ts[-1] == pytest.approx(100.0)

    def test_channel_values_at_midpoint(self):
        """get_channel_values_at_time returns correct value at a mid-sequence time."""
        seq = DaqSequence(11, 10)  # length = 100
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 0.0), (50.0, 10.0)],
            v_interval_styles=[IntervalStyle.RAMP, IntervalStyle.FLAT],
        )
        vals = seq.get_channel_values_at_time(50.0)
        assert vals[0][0] == pytest.approx(10.0)

    def test_multiple_channels_flat_values(self):
        """Multiple flat channels produce expected constant values in the array."""
        seq = DaqSequence(10, 1)  # length = 9
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 3.14)],
            v_interval_styles=[IntervalStyle.FLAT],
        )
        seq.add_channel_seq(
            2,
            tv_pairs=[(0.0, 2.72)],
            v_interval_styles=[IntervalStyle.FLAT],
        )
        arr = seq.get_array()
        assert arr[0] == pytest.approx([3.14] * 10)
        assert arr[1] == pytest.approx([2.72] * 10)
