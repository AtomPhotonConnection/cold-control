"""
awg_control2 — WX218x AWG configuration and waveform upload.

This module configures a Keysight/LeCroy WX218x arbitrary waveform generator
for triggered, multi-channel operation. It builds channel and marker data from
an AwgConfiguration (waveforms, sequence, lags, stitch delays), aligns lengths,
uploads waveforms and marker settings to the instrument, and arms the AWG so
it waits for an external trigger.

Workflow:
  1. Connect and put the AWG in a safe state: abort any running generation and
     disable channel outputs so no waveforms are produced during programming.
  2. Compute timing: channel offsets from lags, stitch delays for interleaved
     waveforms, and marker positions.
  3. Build per-channel waveform and marker arrays (with padding for offsets and
     stitch delays), then combine markers from marked channels and align all
     lengths to the AWG’s requirements (multiple of 16).
  4. Configure marker output, clear waveform/sequence memory, set trace mode.
  5. For each channel: set trigger mode/source/level/slope, burst count, upload
     waveform, set gain. All of this is done with outputs disabled.
  6. Enable all configured channels and call initiate_generation() so the AWG
     arms and waits for trigger. Output only starts after this step.

Usage:
  from instruments.WX218x.awg_control2 import run_awg
  awg, duration_s = run_awg(awg_config, marked_wfs=[1], dev_mode=False, plot=False, optimised=False)

See AwgConfiguration and Waveform in classes.ExperimentalConfigs for config structure.
"""
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple
import os

from classes.ExperimentalConfigs import AwgConfiguration, Waveform

def _is_dev_mode() -> bool:
    return str(os.environ.get("COLD_CONTROL_DEVELOPMENT_MODE", "0")).strip().lower() in (
        "1", "true", "t", "yes", "y"
    )

# AWG imports – use dummy in dev mode
try:
    from instruments.WX218x.WX218x_awg import WX218x_awg, Channel
except Exception:
    if not _is_dev_mode():
        raise
    from instruments.WX218x.WX218x_awg_dummy import DummyWX218x_awg as WX218x_awg
    from instruments.WX218x.WX218x_awg import Channel

try:
    from instruments.WX218x.WX218x_DLL import (
        WX218x_OutputMode, WX218x_OperationMode, WX218x_TriggerMode,
        WX218x_TriggerSlope, WX218x_TraceMode
    )
except Exception:
    from instruments.WX218x.WX218x_dll_compat_shim import (
        WX218x_OperationMode, WX218x_OutputMode, WX218x_TraceMode,
        WX218x_TriggerMode, WX218x_TriggerSlope,
    )

# Marker configuration
MARKER_LOW = 0.0
MARKER_HIGH = 1.2
MARKER_WF_LOW = 0.0
MARKER_WF_HIGH = 1
MARKER_WIDTH_FACTOR = 1e-6
ABSOLUTE_OFFSET_FACTOR = 1e-6
DEFAULT_MARKER_OFFSET = 50  # samples; increase to delay marker pulse

MARKER_WF_LEVS = (MARKER_WF_LOW, MARKER_WF_HIGH)
MARKER_LEVS = (MARKER_LOW, MARKER_HIGH)

VALID_CHANNELS = (Channel.CHANNEL_1, Channel.CHANNEL_2, Channel.CHANNEL_3, Channel.CHANNEL_4)

def calculate_offsets(channel_lags: List[float], sample_rate: float, optimised=False
                      ) -> np.ndarray:
    """
    Calculate absolute channel offsets using vectorized NumPy operations.
    
    Returns:
        np.ndarray: Array of absolute offsets (integers).
    """

    # Calculate channel offsets
    lags = np.asarray(channel_lags)
    raw_offsets = np.rint(lags * sample_rate * ABSOLUTE_OFFSET_FACTOR).astype(int)

    # Normalize so the most negative lag becomes 0 (the reference point)
    #    This ensures all resulting offsets are >= 0 (positive delays).
    min_lag = np.min(raw_offsets)
    absolute_offsets = raw_offsets - min_lag

    if not optimised:
        print("\n DEBUG: Channel offsets:")
        for i, offset in enumerate(absolute_offsets):
            print(f"  Channel {i+1}: abs_offset = {offset}, rel_offset = {max(absolute_offsets) - offset}")
        
    return absolute_offsets

def expand_waveform_sequence(waveforms:List[Waveform], waveform_sequence:List[List[int]]):
    """
    Translates a sequence of waveform IDs into their actual waveform objects.
    """
    # This list comprehension replaces the IDs in waveform_sequence 
    # with the actual objects from the 'waveforms' dictionary.

    #NOTE: This should be changed to use waveforms as a Dict[int, Waveform] later

    return [[waveforms[i] for i in ch_waveforms] for ch_waveforms in waveform_sequence]


def calculate_stitch_delays(stitch_delays, waveforms:List[Waveform], optimised = False):
    """
    Calculates delays required to stitch waveforms.
    Returns a list of calculated delays.
    """
    calculated_delays = []

    if not optimised:
        print("\nDEBUG: Stitch delays before applying")
        for i, delay_info in enumerate(stitch_delays):
            print(f"  Channel {i+1}: stitch_delay = {delay_info}")

    print('Interleaving waveforms')

    # Unpack the list entry directly into variables for readability
    for direction, target_wf_ids in stitch_delays:
        if direction not in [-1, 1]:
            raise ValueError(f'Invalid stitch direction {direction}. Must be -1 or +1.')

        # Calculate total samples (handles empty lists automatically)
        # We use 'or []' to handle cases where target_wf_ids might be None
        current_ids = target_wf_ids or []
        total_samples = sum(waveforms[wf_id].get_n_samples() for wf_id in current_ids)

        # 1 * samples = positive delay
        # -1 * samples = negative delay
        calculated_delays.append(direction * total_samples)

    print('Stitch delays are', calculated_delays)
    return calculated_delays


def get_multiwaveform_marker_data(inp_data, marker_positions=[], marker_levels=(0,1), 
                                  marker_width=50, n_pad_right=0, n_pad_left=0) -> np.ndarray:
    '''
    Returns a marker waveform.
    Inputs:
        - inp_data (int): the length of the waveform data
        - marker_positions (list): positions within the waveform to start each marker segment
        - marker_levels (tuple): levels to be used in the waveform in the form (low, high)
        - marker_width (int): width of each marker pulse
        - n_pad_right, n_pad_left (int): number of padding elements to add at the end and beginning (respectively) of the waveform
    '''
    data = np.array( [marker_levels[0]] * (n_pad_left + inp_data + n_pad_right))# Use a np array for ease of setting array slices to contant values.
    for pos in marker_positions:
        data[int(pos):int(pos+marker_width)] = marker_levels[1]
    
    if data[0]==1:# This is a big fix. If the first element of the sequence is 1 (i.e. max high level)
        data[0]=0# then the channel remains high at the end of the sequence. Don't know why...

    return data


def align_data_length(seq_waveform_data:List[np.ndarray], seq_marker_data: np.ndarray
                      ) -> Tuple[List[np.ndarray], np.ndarray]:
    '''
    Ensure we write the same number of points to each channel.
    '''
    max_len = max(len(x) for x in seq_waveform_data)
    
    # Ensure multiple of 16 (AWG requirement)
    if max_len % 16 != 0:
        padding_needed = 16 - (max_len % 16)
        print(f'{padding_needed} points added to ensure multiple of 16.')
        max_len += padding_needed

    # Pad all waveforms to max_len
    aligned_wfs = []
    for wf in seq_waveform_data:
        current_len = len(wf)
        if current_len < max_len:
            # Pad end with zeros
            padded = np.pad(wf, (0, max_len - current_len), 'constant')
            aligned_wfs.append(padded)
        else:
            aligned_wfs.append(wf)
            
    # Align marker data
    l_mark = len(seq_marker_data)
    if l_mark < max_len:
        seq_marker_data = np.pad(seq_marker_data, (0, max_len - l_mark), 'constant')
    elif l_mark > max_len:
        seq_marker_data = seq_marker_data[:max_len]
        
    return aligned_wfs, seq_marker_data


def write_markers(marker_data, awg: WX218x_awg, awg_chs, marker_width):
    """Configure marker output on the AWG from combined marker data."""
    marker_starts = np.where(np.diff(marker_data, prepend=0) > 0)[0]
    print('Marker_starts:', marker_starts)

    if len(marker_starts) > 1:
        print('ERROR: There are more markers required than can be set currently using the marker channels!')
        marker_starts = marker_starts[:1]

    if len(marker_starts) == 1:
        awg.configure_marker(awg_chs[0],
                             index=1,
                             position=marker_starts[0] - marker_width / 4,
                             levels=MARKER_LEVS,
                             width=marker_width / 2)
    else:
        print("No markers defined, not using a marker")

    awg.clear_arbitrary_sequence()
    awg.clear_arbitrary_waveform()


def configure_awg(awg_config: AwgConfiguration, marked_wfs=None, dev_mode=False, plot=False, optimised=False):
    """
    Configure the AWG from awg_config and arm it for triggered generation.

    Channels and markers are programmed with outputs disabled; outputs are
    enabled and generation is initiated only at the end, so no waveforms
    are produced during the upload.

    Args:
        awg_config: Sample rate, channels, waveforms, sequence, lags, markers, etc.
        marked_wfs: Indices of waveform segments that get a marker (e.g. for
            photon detection). Default [1] marks the second segment; use [0]
            to mark the first (e.g. single-waveform case).
        dev_mode: If True, skip hardware; compute and return (None, duration).
        plot: If True and not optimised, plot combined marker data.
        optimised: If True, suppress debug prints.

    Returns:
        (awg, duration_s): AWG instance (or None in dev_mode) and waveform
        length in seconds.
    """
    if marked_wfs is None:
        marked_wfs = [1]
    if dev_mode:
        print("Running in Dev Mode: No hardware communication.")
    
    awg = None
    if not dev_mode:
        awg = WX218x_awg()
        awg.open(reset=False)
        awg.clear_arbitrary_sequence()
        awg.clear_arbitrary_waveform()

        # Stop any running output and disable channels so nothing outputs during programming
        awg.abort_generation()
        for ch in awg_config.waveform_output_channels:
            awg.disable_channel(ch)

        # 1. Global Configuration
        awg.configure_sample_rate(awg_config.sample_rate)
        awg.configure_output_mode(WX218x_OutputMode.ARBITRARY)
        awg.configure_couple_enabled(True)
    

    # 2. Timing Calculations
    abs_offsets = calculate_offsets(awg_config.waveform_output_channel_lags,
                                    awg_config.sample_rate, optimised=optimised)
    marker_wid = int(awg_config.marker_width * MARKER_WIDTH_FACTOR * awg_config.sample_rate)
    
    wf_list = expand_waveform_sequence(awg_config.waveforms, awg_config.waveform_sequence)
    
    # Calculate stitch delays (handles inter-channel interleaving)
    if awg_config.interleave_waveforms:
        stitch_delays = calculate_stitch_delays(awg_config.waveform_stitch_delays,
                                                awg_config.waveforms, optimised=optimised)
    else:
        stitch_delays = [0] * len(awg_config.waveform_output_channels)

    all_channel_data = []
    combined_marker_data = np.array([])

    # 3. Data Preparation Loop
    for i, (ch_name, waveforms, s_delay, ch_offset) in enumerate(
        zip(awg_config.waveform_output_channels, wf_list, stitch_delays, abs_offsets)):
        
        # Create the raw concatenated waveform
        raw_chunks = [np.array(w.get(sample_rate=awg_config.sample_rate)) for w in waveforms]
        full_wf = np.concatenate(raw_chunks)
        
        # Padding for stitch delays
        pad_l = abs(s_delay) if s_delay < 0 else 0
        pad_r = abs(s_delay) if s_delay > 0 else 0
        full_wf = np.pad(full_wf, (pad_l, pad_r), 'constant')

        # Marker Logic: match original — single waveform gets one marker; multi uses marked_wfs
        m_pos = []
        if len(waveforms) == 1:
            seg_length = waveforms[0].get_n_samples() + pad_l + pad_r + abs(int(ch_offset))
            if ch_offset <= seg_length:
                m_pos.append(pad_l + ch_offset + DEFAULT_MARKER_OFFSET)
        else:
            current_idx = pad_l + ch_offset + DEFAULT_MARKER_OFFSET
            for idx, w in enumerate(waveforms):
                if idx in marked_wfs:
                    m_pos.append(current_idx)
                current_idx += w.get_n_samples()

        ch_marker = get_multiwaveform_marker_data(
            len(full_wf) - (pad_l + pad_r),
            marker_positions=m_pos,
            marker_levels=MARKER_WF_LEVS,
            marker_width=marker_wid,
            n_pad_left=pad_l,
            n_pad_right=pad_r
        )

        # Apply channel offset: waveform shifts right; marker content stays at start (original behavior)
        full_wf = np.pad(full_wf, (ch_offset, 0), 'constant')
        ch_marker = np.pad(ch_marker, (0, ch_offset), 'constant')

        all_channel_data.append(full_wf)
        
        # Accumulate markers for the trigger channel
        if ch_name in awg_config.marked_channels:
            if combined_marker_data.size == 0:
                combined_marker_data = ch_marker
            else:
                # Ensure arrays match length before adding
                target_len = max(len(combined_marker_data), len(ch_marker))
                combined_marker_data = np.pad(combined_marker_data, (0, target_len - len(combined_marker_data)), 'constant')
                ch_marker_padded = np.pad(ch_marker, (0, target_len - len(ch_marker)), 'constant')
                combined_marker_data = np.logical_or(combined_marker_data, ch_marker_padded).astype(float)

    # 4. Final Alignment & Hardware Write
    aligned_wfs, final_marker = align_data_length(all_channel_data, combined_marker_data)

    if plot and not optimised:
        plt.plot(final_marker)
        plt.title('Marker Data')
        plt.show(block=False)
        plt.pause(1)
        plt.close()

    if not dev_mode:
        assert awg is not None, "AWG instance should not be None in non-dev mode."
        # Configure markers and clear waveform memory first (same order as original)
        write_markers(final_marker, awg, awg_config.waveform_output_channels, marker_wid)
        awg.configure_arb_wave_trace_mode(WX218x_TraceMode.SINGLE)

        # Write all waveforms and configure triggers with outputs disabled
        for ch_name, data in zip(awg_config.waveform_output_channels, aligned_wfs):
            awg.configure_operation_mode(ch_name, WX218x_OperationMode.TRIGGER)
            awg.configure_trigger_source(ch_name, WX218x_TriggerMode.EXTERNAL)
            awg.configure_trigger_level(ch_name, 1.6)
            awg.configure_trigger_slope(ch_name, WX218x_TriggerSlope.POSITIVE)
            awg.configure_burst_count(ch_name, awg_config.burst_count)
            awg.set_active_channel(ch_name)
            if ch_name in VALID_CHANNELS:
                awg.create_arbitrary_waveform_custom(data.tolist())
            awg.configure_arb_gain(ch_name, 2.0)

        # Enable outputs only after all programming is complete, then arm
        for ch_name in awg_config.waveform_output_channels:
            awg.enable_channel(ch_name)
        awg.initiate_generation()
        if not optimised:
            print("AWG armed and waiting for trigger.")

    return awg, len(aligned_wfs[0])/awg_config.sample_rate