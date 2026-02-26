"""
Created on 10 Apr 2016

@author: Tom Barrett
"""

import numpy as np


class Sequence:
    """
    A class containing all the information needed to create a sequence for multiple DAQ channel.

    Note t_step is in microseconds
    """

    def __init__(self, n_samples, t_step=1):
        self.n_samples = n_samples
        self.chSeqs: dict[int, _ChannelSequence] = {}
        self.t_step = t_step

    def get_array(self):
        """Return the sequence as a numpy array of all channels"""
        return np.asarray([self.chSeqs[chNum].get_val_array() for chNum in self.get_channel_nums()])

    def get_length(self):
        return (self.n_samples - 1) * self.t_step

    def get_time_steps(self):
        return np.linspace(0.0, self.get_length(), self.n_samples)

    def add_channel_seq(self, ch_num, tv_pairs=None, v_interval_styles=None):
        if v_interval_styles is None:
            v_interval_styles = []
        if tv_pairs is None:
            tv_pairs = [(0.0, 0.0)]
        self.chSeqs[ch_num] = _ChannelSequence(self, tv_pairs, v_interval_styles)

    def get_channel_nums(self):
        return sorted(self.chSeqs.keys(), key=lambda x: int(x))

    def get_channel_val_array(self, ch_num):
        return self.chSeqs[ch_num].get_val_array()

    def get_channel_values_at_time(self, t, ch_nums=None):
        """
        Returns a list of the value of channels at a specified time, ordered as provided in chNums.
        The values are returned in the form: [[val1],[val2],[val3],...].
            t - the time (in microseconds) after the start of the sequence to get channel values at
            chNum - a list of channel numbers. If None returns all channels
        """
        if t < 0 or t > self.get_length():
            raise ValueError(
                "t must be within the sequence duration: 0 <= t <= (n_samples-1)*t_step"
            )
        if ch_nums is None:
            ch_nums = self.get_channel_nums()
        col = int(np.floor(t / self.t_step))

        return np.array(
            [[chArr[col]] for chArr in [self.get_channel_val_array(n) for n in ch_nums]]
        )

    def get_tv_pairs(self, ch_num) -> list:
        return self.chSeqs[ch_num].tV_pairs

    def get_v_interval_styles(self, ch_num) -> list:
        return self.chSeqs[ch_num].V_interval_styles

    def update_channel(self, ch_num, tv_pairs, v_interval_styles):
        channel: _ChannelSequence = self.chSeqs[ch_num]
        old_tv_pairs, old_v_interval_styles = channel.tV_pairs, channel.V_interval_styles
        try:
            tv_sorted, v_interval_sorted = zip(
                *sorted(zip(tv_pairs, v_interval_styles), key=lambda x: x[0][0])
            )
            channel.tV_pairs = list(tv_sorted)
            channel.V_interval_styles = list(v_interval_sorted)
            channel.validate()
        except InvalidSequenceChannelError as err:
            channel.tV_pairs = old_tv_pairs
            channel.V_interval_styles = old_v_interval_styles
            raise err

    def update_time_steps(self, n_samples, t_step, channels_to_update=None):
        """Update the sequence level variables.  Takes an optional dictionary of changes to make
        to individual channels before validate the sequence in the form:
            key = channel number
            value = (tV_pairs, V_interval_styles)"""
        # Store origional values for reverting to then change to new values.
        if channels_to_update is None:
            channels_to_update = {}
        old_n_samples, old_t_step = self.n_samples, self.t_step
        self.n_samples = n_samples
        self.t_step = t_step

        validation_errors = []
        error_channels = []

        # For each channel, apply any changes as provided in channelsToUpdate, then validate each channel.
        for ch_num in self.chSeqs:
            try:
                # Update the channel (if required) and validate - note validate is called in self.updateChannel
                # so it is only explicitly called here if no updates were required.
                if ch_num in channels_to_update:
                    self.update_channel(
                        ch_num, channels_to_update[ch_num][0], channels_to_update[ch_num][1]
                    )
                else:
                    self.chSeqs[ch_num].validate()

            # revert changes if validation threw errors, store these errors to be raised en-masse later.
            except InvalidSequenceChannelError as err:
                self.n_samples = old_n_samples
                self.t_step = old_t_step
                validation_errors.append(err)
                error_channels.append(ch_num)

        # If there were validation errors raise them now.
        if validation_errors != []:
            raise MultipleInvalidSequenceChannelError(
                f"{len(validation_errors)} validation errors were found when updating the sequence",
                errors=validation_errors,
                error_channels=error_channels,
            )


class _ChannelSequence:
    """
    A class containing all the information needed to create a sequence for one DAQ channel.
    """

    def __init__(
        self,
        parent_sequence,
        tv_pairs=None,
        v_interval_styles=None,
    ):
        if v_interval_styles is None:
            v_interval_styles = []
        if tv_pairs is None:
            tv_pairs = [(0.0, 0.0)]
        self.parent = parent_sequence

        self.tV_pairs, self.V_interval_styles = map(
            list, zip(*sorted(zip(tv_pairs, v_interval_styles), key=lambda x: x[0][0]))
        )

        self.validate()

    def get_val_array(self):
        t_span = self.parent.getTimeSteps()
        v_span = np.array([], dtype=np.float64)
        num_intervals = len(self.V_interval_styles)
        #
        #         if numIntervals == 1:
        #             # If there is only one interval it's just a constant value for the whole sequence.
        #             (t_0, V_0) = self.tV_pairs[0]
        #             (t_1, V_1) = self.parent.getTimeSteps()[-1], V_0
        #             changeStyle = self.V_interval_styles[0]
        #
        #             changeFunc = self.getChangeFunc(changeStyle, (t_0, V_0), (t_1, V_1))
        #             V_span = np.append(V_span, map(changeFunc, t_span))
        #
        #         else:
        for i in range(0, num_intervals):
            (t_0, v_0) = self.tV_pairs[i]
            try:
                (t_1, v_1) = self.tV_pairs[i + 1]
            except IndexError as err:
                # If there is an index error tHis could be because we are on the final sequence interval.
                if i == num_intervals - 1 and self.V_interval_styles[i] == IntervalStyle.FLAT:
                    # If we are, and the final interval style is Flat then we know the final voltage.
                    (t_1, v_1) = t_span[-1], v_0
                else:
                    # Otherwise I don't know why it broke so I'm throwing the error back!
                    raise err
            change_style = self.V_interval_styles[i]

            t_interval = (
                [t for t in t_span if t_0 <= t <= t_1]
                if i == num_intervals - 1
                else [t for t in t_span if t_0 <= t < t_1]
            )

            # Note we use t_interval[0] and t_interval[1] rather than t_0 and t_1.  This is because he function fits expected values
            # between the time points provided - so if t_0 and t_1 are not in t_span then some unwanted values will be set!

            try:
                change_func = self.get_change_func(
                    change_style, (t_interval[0], v_0), (t_interval[-1], v_1)
                )
                if change_func is None:
                    raise ValueError(f"Invalid change style {change_style} provided")
                v_span = np.append(
                    v_span, np.array(list(map(change_func, t_interval)), dtype=np.float64)
                )
            except IndexError:
                # If t_interval is an empty list wel'll catch that here - it just means that t_0 and t_1
                # are so close together (or identical) so no times in t_span are between them.  The card
                # can't update that quick so there is nothing to add to V_span anyway.
                pass

        return v_span

    def get_change_func(self, style, t_0_v_0, t_1_v_1):
        t_0, v_0 = t_0_v_0
        t_1, v_1 = t_1_v_1
        if style == IntervalStyle.FLAT:
            """ TODO - MAKE PIECEWISE?"""
            return lambda t: v_0
        if style == IntervalStyle.RAMP:
            return lambda t: ((v_1 - v_0) / (t_1 - t_0)) * (t - t_0) + v_0

    def validate(self):
        """Validate the sequence information provided for consistency with itself and the parent sequence."""
        if (
            len(self.tV_pairs) == len(self.V_interval_styles) + 1
            and self.tV_pairs[-1][0] != self.parent.getTimeSteps()[-1]
        ):
            raise InvalidSequenceChannelError(
                f"Sequence validation error: If {len(self.tV_pairs)} time-voltage pairs and {len(self.V_interval_styles)} styles of how to move between them are provided - the last time must be the final data point of the sequence ({self.parent.getTimeSteps()[-1]})."
            )

        elif len(self.tV_pairs) == len(self.V_interval_styles):
            if self.tV_pairs[-1][0] >= self.parent.getTimeSteps()[-1]:
                raise InvalidSequenceChannelError(
                    f"Sequence validation error: If the same number of time-voltage pairs and interval styles ({len(self.tV_pairs)}) are provided - the final time provided must be before the end of the sequence length.."
                )
            elif self.V_interval_styles[-1] != IntervalStyle.FLAT:
                raise InvalidSequenceChannelError(
                    f"Sequence validation error: If the same number of time-voltage pairs and interval styles ({len(self.tV_pairs)}) are provided - the final interval style must be Flat."
                )

        elif (
            len(self.tV_pairs) != len(self.V_interval_styles)
            and len(self.tV_pairs) != len(self.V_interval_styles) + 1
        ):
            raise InvalidSequenceChannelError(
                f"Sequence validation error: If is not possible to create a sequence out from {len(self.tV_pairs)} time-voltage pairs and {len(self.V_interval_styles)} interval styles."
            )

        if int(self.tV_pairs[0][0]) != 0:
            raise InvalidSequenceChannelError(
                f"Every channels sequence must begin at t=0 (here t={self.tV_pairs[0][0]} is the first time provided)."
            )

        if self.tV_pairs[-1][0] > self.parent.getLength():
            raise InvalidSequenceChannelError(
                f"A channel sequence cannot be created with a time-voltage pair ({self.tV_pairs[-1]}) outside the total running time of it's parent sequence ({self.parent.getLength()})"
            )


class InvalidSequenceChannelError(Exception):
    def __init__(self, message, errors=None):

        # Call the base class constructor with the parameters it needs
        if errors is None:
            errors = []
        super().__init__(message)
        self.errors = errors


class MultipleInvalidSequenceChannelError(Exception):
    def __init__(self, message, errors=None, error_channels=None):

        # Call the base class constructor with the parameters it needs
        if error_channels is None:
            error_channels = []
        if errors is None:
            errors = []
        super().__init__(message)
        self.errors = errors
        self.errorChannels = error_channels


class IntervalStyle:
    FLAT, RAMP = range(2)

    @classmethod
    def to_string(cls, val):
        for k, v in vars(cls).items():
            if v == val:
                return k.title()

    @classmethod
    def from_string(cls, str):
        return getattr(cls, str.upper(), None)

    @classmethod
    def get_all(cls):
        return [
            x
            for x in cls.__dict__
            if not isinstance(cls.__dict__[x], classmethod) and not x.startswith("__")
        ]
