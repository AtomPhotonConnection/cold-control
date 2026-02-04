from time import sleep
import os
from typing import Any, Dict, List, Tuple
import numpy as np
import glob
import re
import matplotlib.pyplot as plt
import ctypes

from classes.ExperimentalConfigs import AWGSequenceConfiguration, AwgConfiguration, Waveform
from instruments.WX218x.WX218x_awg import WX218x_awg, Channel
from instruments.WX218x.WX218x_DLL import (
    WX218x_OutputMode, WX218x_OperationMode, WX218x_TriggerMode, WX218x_TriggerSlope, WX218x_TraceMode
)


# Constants for marker configuration

#marker_levs, marker_waveform_levs = (0,1.2), (0,1)
MARKER_LOW = 0.0
MARKER_HIGH = 1.2
MARKER_WF_LOW = 0.0
MARKER_WF_HIGH = 1
MARKER_WIDTH_FACTOR = 10**-6
ABSOLUTE_OFFSET_FACTOR = 10**-6
# Increasing DEFAULT_MARKER_OFFSET makes the marker pulses happen later.
DEFAULT_MARKER_OFFSET = 50  # TO DO: MAKE A LIST TO VARY MARKER DELAYS INDEPENDENTLY   si surt 0 en marker channel es aixoooo


MARKER_WF_LEVS = (MARKER_WF_LOW, MARKER_WF_HIGH)
MARKER_LEVS = (MARKER_LOW, MARKER_HIGH)

def connect_awg():
    """Connect to the AWG and clear previous configurations."""
    print("Connecting to AWG...")
    awg = WX218x_awg()
    print(f"Attempting to open AWG: {awg}")

    awg.open(reset=False)
    awg.clear_arbitrary_sequence()
    awg.clear_arbitrary_waveform()
    print("...connected")
    return awg


def configure_awg_general(awg:WX218x_awg, sample_rate, burst_count):
    """Configure general AWG settings like sample rate and output mode."""
    awg.configure_sample_rate(sample_rate)
    awg.configure_output_mode(WX218x_OutputMode.ARBITRARY)
    awg.configure_couple_enabled(True)
    #awg.configure_burst_count(Channel.CHANNEL_1, burst_count)  # Example for one channel


def configure_trigger(awg:WX218x_awg, awg_chs:List[int], burst_count):
    """Configure trigger settings for specific channels."""
    for ch in awg_chs:
        print(f"Configuring trigger options for {ch}")
        awg.configure_burst_count(ch, burst_count)
        awg.configure_operation_mode(ch, WX218x_OperationMode.TRIGGER)
        awg.configure_trigger_source(ch, WX218x_TriggerMode.EXTERNAL)
        awg.configure_trigger_level(ch, 1.6)
        awg.configure_trigger_slope(ch, WX218x_TriggerSlope.POSITIVE)



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

    if optimised == False:
        print("\n DEBUG: Channel offsets:")
        for i, offset in enumerate(absolute_offsets):
            print(f"  Channel {i+1}: abs_offset = {offset}, rel_offset = {max(absolute_offsets) - offset}")
        
    return absolute_offsets


def plot_marker_data(marker_data):
    """Plot marker data for visualization."""
    plt.plot(marker_data)
    plt.title("Marker Data")
    plt.show(block=False)
    plt.pause(1)
    plt.close()


def get_waveform_calib_fnc(calib_fname, max_eff=0.9):
    """
    Generates a calibration function from a file containing waveform calibration data.
    Inputs:
        - calib_fname (str): name of the file from which to read calibration data. Has two columns.
        - max_eff (float): maximum efficiency value. Values above this are removed from the data.
    Returns:
        - interp_fct (function): a function that takes in a list of points, x, and returns the
        interpolated values of the calibration data at each of the points.
    """
    calib_data = np.genfromtxt(calib_fname,skip_header=1)
    calib_data[:,1] /= 100. # convert % as saved to decimal efficiencies
    calib_data = calib_data[(calib_data[:,1]<=max_eff)] # remove all elements with greater than the maximum efficiency
    calib_data[:,1] /= max(calib_data[:,1]) # rescale effiencies

    interp_fct = lambda x: np.interp(np.abs(x), calib_data[:,1], calib_data[:,0])

    return interp_fct


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




def expand_waveform_sequence(waveforms:List[Waveform], waveform_sequence:List[List[int]]):
    """
    Translates a sequence of waveform IDs into their actual waveform objects.
    """
    # This list comprehension replaces the IDs in waveform_sequence 
    # with the actual objects from the 'waveforms' dictionary.

    #NOTE: This should be changed to use waveofrms as a Dict[int, Waveform] later

    return [[waveforms[i] for i in ch_waveforms] for ch_waveforms in waveform_sequence]



def calculate_stitch_delays(stitch_delays, waveforms:List[Waveform], optimised = False):
    """
    Calculates delays required to stitch waveforms.
    Returns a list of calculated delays.
    """
    calculated_delays = []

    # Optional: Debug print
    if optimised == False:
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


def write_markers(marker_data, awg:WX218x_awg, awg_chs, marker_width):
    #finds start of marker pulse if it has been padded
    marker_starts = np.where(np.diff(marker_data, prepend=0) > 0)[0]#np.where((marker_data[:-1] == 0) & (marker_data[1:] > 0))[0]
    print('Marker_starts:', marker_starts)
    
    if len(marker_starts) > 1:
        print('ERROR: There are more markers required than can be set currently using the marker channels!')
        marker_starts = marker_starts[:1]  # Only use the first marker for now

    # print('Writing markers to marker channels at {0}'.format(marker_starts))
    if len(marker_starts) == 1:
        awg.configure_marker(awg_chs[0], 
                                    index = 1, 
                                    position = marker_starts[0] - marker_width/4,
                                    levels = MARKER_LEVS,
                                    width = marker_width/2)
    else:
        print("No markers defined, not using a marker")
    #awg.configure_marker(awg_chs[1], # changed to channel 2 to investigate pulses
    #                            index = 2, 
    #                            position = marker_starts[1] - marker_width/4,
    #                            levels = MARKER_LEVS,
    #                            width = marker_width/2)

    awg.clear_arbitrary_sequence()
    awg.clear_arbitrary_waveform()



def write_channels(awg_chs:List[Any], _wf_data:List[np.ndarray], _awg:WX218x_awg, show_plots=False):
    '''Configure each channel for its output data.'''
    for channel, data in zip(awg_chs, _wf_data):
        # Roll channel data to account for relative offsets (e.g. AOM lags)
        # print(data)
        if show_plots:
            plt.plot(data)
            plt.title('Channel {0} data'.format(channel))
            plt.show(block=False)
            plt.pause(1)
            plt.close()


        # print('Writing {0} points to {1}'.format(len(data),channel))
        _awg.set_active_channel(channel)
        if channel in [Channel.CHANNEL_1, Channel.CHANNEL_2, Channel.CHANNEL_3, Channel.CHANNEL_4]:
            _awg.create_arbitrary_waveform_custom(data.tolist())

            
    for channel in awg_chs:
        _awg.enable_channel(channel)
        _awg.configure_arb_gain(channel, 2)


def run_awg(awg_config: AwgConfiguration, marked_wfs = [1], dev_mode:bool = False, 
            optimised:bool = False, plot:bool = False):
    """
    Main function to configure the AWG for the experiment.
    Input args:
    awg_config (AwgConfiguration): Specifies the settings of the awg. For details see the class definition.
    marked_wfs (list): IMPORTANT THIS SETS the indices of the waveforms on the marked channel
      that are actually marked for photon dectection (i.e. the VST pulses)
    
    """
    if not dev_mode:
        awg = connect_awg()

        # General AWG settings
        configure_awg_general(awg, awg_config.sample_rate, awg_config.burst_count)
        configure_trigger(awg, awg_config.waveform_output_channels, awg_config.burst_count)



    

    # Calculate channel offsets
    abs_offsets = calculate_offsets(awg_config.waveform_output_channel_lags,\
                                                  awg_config.sample_rate)
    #rel_offsets = max(abs_offsets) - abs_offsets

    # Process waveforms and markers
    marker_wid  = int(awg_config.marker_width*10**-6 * awg_config.sample_rate)

    

    # Markers (if you actually need them)
    seq_marker_data = np.array([])
    wf_list = expand_waveform_sequence(awg_config.waveforms, awg_config.waveform_sequence)
    
    if optimised == False:
        print(wf_list)
     
    if awg_config.interleave_waveforms:  
        wf_stitched_delays = calculate_stitch_delays(awg_config.waveform_stitch_delays,\
                                                      awg_config.waveforms, optimised=optimised)
    else:
        wf_stitched_delays=[0]*len(awg_config.waveform_output_channels)


    wf_data = []
    # main loop to do everything
    for channel, waveforms, delay, channel_abs_offset in \
        zip(awg_config.waveform_output_channels, wf_list, wf_stitched_delays, abs_offsets):
        """
        Loops through each channel, processing the waveform and marker data to be sent to 
        the awg for each channel.
        """ 

        if not optimised: print('Writing onto channel:', channel)


        waveform_lengths=[w.get_n_samples() for w in waveforms]
        total_sequence_len = sum(waveform_lengths)

        current_channel_wf_data = []
        marker_data = []


        pad_left = abs(delay) if delay < 0 else 0
        pad_right = abs(delay) if delay > 0 else 0

        if len(waveforms) == 1:
            waveform = waveforms[0]

            raw_wf = np.array(waveform.get(sample_rate=awg_config.sample_rate))
            current_channel_wf_data = np.pad(raw_wf, (pad_left, pad_right), 'constant')

            marker_pos = []
            seg_length = waveform.get_n_samples() + abs(delay) + abs(channel_abs_offset)

            if channel_abs_offset <= seg_length:
                marker_pos.append(channel_abs_offset + DEFAULT_MARKER_OFFSET)

            marker_data = waveform.get_marker_data(\
                    marker_positions=marker_pos,
                    marker_levels=MARKER_WF_LEVS,
                    marker_width=marker_wid,
                    n_pad_left=pad_left,
                    n_pad_right=pad_right)


        else:# multiple waveforms in the sequence
            wf_chunks = []# storage for waveform chunks
            multi_marker_pos = []
            for ind, waveform in enumerate(waveforms):
                waveform: Waveform
                seg_pad_l = pad_left if ind == 0 else 0
                seg_pad_r = pad_right if ind == len(waveforms)-1 else 0
                
                raw_wf = np.array(waveform.get(sample_rate=awg_config.sample_rate))
                if seg_pad_l > 0 or seg_pad_r > 0:
                    chunk = np.pad(raw_wf, (seg_pad_l, seg_pad_r), 'constant')
                else:
                    chunk = raw_wf
                    
                wf_chunks.append(chunk)

                
                if ind in marked_wfs:
                    base_pos = channel_abs_offset + DEFAULT_MARKER_OFFSET
                    offset = 0 if ind == 0 else sum(waveform_lengths[:ind])
                    pos = base_pos + offset
                    if delay < 0:
                        pos += abs(delay)
                    multi_marker_pos.append(pos)

            current_channel_wf_data = np.concatenate(wf_chunks)
            marker_data = get_multiwaveform_marker_data(
                total_sequence_len,
                marker_positions=multi_marker_pos,
                marker_levels=MARKER_WF_LEVS,
                marker_width=marker_wid,
                n_pad_left=pad_left,
                n_pad_right=pad_right
            )

                
        # Channel offset, pad the waveform and marker data accordingly
        pad_offset = abs(int(channel_abs_offset))
        current_channel_wf_data = np.pad(current_channel_wf_data, (pad_offset, 0), 'constant')
        marker_data = np.pad(marker_data, (0, pad_offset), 'constant')# Should the padding be on the left?

            
        wf_data.append(current_channel_wf_data)
                
        
        # Combine the marker data for each marked channel.
        print('Marked Channels:', awg_config.marked_channels)
        if channel in awg_config.marked_channels:
            if len(seq_marker_data) == 0:
                print('seq_marker_data is empty')
                seq_marker_data = np.array(marker_data)
            else:
                new_data = np.array(marker_data)
                current_len = len(seq_marker_data)
                new_len = len(new_data)

                if new_len > current_len:
                    seq_marker_data = np.pad(seq_marker_data, (0, new_len - current_len), 'constant')
                elif current_len > new_len:
                    new_data = np.pad(new_data, (0, current_len - new_len), 'constant')

                seq_marker_data += new_data

    
    # End of loop
    print(f"Waveforms written to {len(wf_data)} channels")

    # Ensure data length alignment
    wf_data, seq_marker_data = align_data_length(wf_data, seq_marker_data)  

    # Plot marker data
    if plot and not optimised: plot_marker_data(marker_data)

    if not dev_mode:
        # Add markers to channels
        write_markers(seq_marker_data, awg, awg_config.waveform_output_channels, marker_wid)  

        awg.configure_arb_wave_trace_mode(WX218x_TraceMode.SINGLE)


        # Configure channels and write data
        write_channels(awg_config.waveform_output_channels, wf_data, awg, show_plots=plot) 


    print("AWG configuration complete.")

    return awg, len(wf_data[0])/awg_config.sample_rate

