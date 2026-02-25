"""
AWG Control Functions for PSH (Pulse Shaping Experiment)

This module provides a clean interface to configure and control the WX218x AWG
using an AwgConfiguration object. It replaces the legacy awg_control_functions_psh.py
with improved error handling, clearer logic, and better separation of concerns.

@author: GitHub Copilot
@date: 2025-12-01
"""

from time import sleep
from typing import Any, Optional

import numpy as np
from instruments.WX218x.WX218x_awg import WX218x_awg
from instruments.WX218x.WX218x_DLL import (
    WX218x_OperationMode,
    WX218x_OutputMode,
    WX218x_TriggerMode,
    WX218x_TriggerSlope,
)

from classes.experimental_configs import AwgConfiguration, Waveform

# ============================================================================
# Constants for Marker Configuration
# ============================================================================

MARKER_LOW = 0.0
MARKER_HIGH = 1.2
MARKER_WF_LOW = 0.0
MARKER_WF_HIGH = 1.0

# Time conversion factor: microseconds to seconds
US_TO_S = 1e-6

# Marker configuration constants
MARKER_LEVS = (MARKER_LOW, MARKER_HIGH)
MARKER_WF_LEVS = (MARKER_WF_LOW, MARKER_WF_HIGH)


# ============================================================================
# AWG Connection and Initialization
# ============================================================================


def connect_awg(reset: bool = False) -> WX218x_awg:
    """
    Connect to the AWG and initialize it.

    Args:
        reset: Whether to reset the AWG on connection (default: False)

    Returns:
        WX218x_awg: Connected AWG object

    Raises:
        Exception: If AWG connection fails
    """
    print("Connecting to AWG...")
    try:
        awg = WX218x_awg()
        awg.open(reset=reset)
        awg.clear_arbitrary_sequence()
        awg.clear_arbitrary_waveform()
        print(f"Connected to AWG: {awg.name}")
        return awg
    except Exception as e:
        print(f"Failed to connect to AWG: {e}")
        raise


def disconnect_awg(awg: WX218x_awg) -> None:
    """
    Safely disconnect from the AWG.

    Args:
        awg: The WX218x_awg object to disconnect
    """
    try:
        awg.close()
        print("AWG disconnected")
    except Exception as e:
        print(f"Error during AWG disconnect: {e}")


# ============================================================================
# General AWG Configuration
# ============================================================================


def configure_awg_general(awg: WX218x_awg, awg_config: AwgConfiguration) -> None:
    """
    Configure general AWG settings (sample rate, output mode, coupling).

    Args:
        awg: The WX218x_awg object
        awg_config: AwgConfiguration object containing settings
    """
    print("\n" + "=" * 60)
    print("Configuring General AWG Settings")
    print("=" * 60)

    print(f"Sample rate: {awg_config.sample_rate / 1e6:.1f} MHz")
    awg.configure_sample_rate(awg_config.sample_rate)

    print("Output mode: ARBITRARY")
    awg.configure_output_mode(WX218x_OutputMode.ARBITRARY)

    print("Channel coupling: ENABLED")
    awg.configure_couple_enabled(True)

    print("General configuration complete")


def configure_triggers(awg: WX218x_awg, awg_config: AwgConfiguration) -> None:
    """
    Configure trigger settings for all output channels.

    Args:
        awg: The WX218x_awg object
        awg_config: AwgConfiguration object containing channel and trigger info
    """
    print("\n" + "=" * 60)
    print("Configuring Trigger Settings")
    print("=" * 60)

    channels = awg_config.waveform_output_channels
    burst_count = awg_config.burst_count

    print(f"Channels to configure: {channels}")
    print(f"Burst count: {burst_count}")

    # Configure triggers for even-indexed channels (typically the main channels)
    for i, channel in enumerate(channels):
        if i % 2 == 0:
            print(f"\n  Configuring {channel}...")
            awg.configure_burst_count(channel, burst_count)
            awg.configure_operation_mode(channel, WX218x_OperationMode.TRIGGER)
            sleep(0.1)  # Brief delay between commands
            awg.configure_trigger_source(channel, WX218x_TriggerMode.EXTERNAL)
            awg.configure_trigger_level(channel, 2.0)
            awg.configure_trigger_slope(channel, WX218x_TriggerSlope.POSITIVE)

    print("\n Trigger configuration complete")


# ============================================================================
# Channel Offset Calculation
# ============================================================================


def calculate_channel_offsets(
    channel_lags: list[float], sample_rate: float
) -> tuple[list[int], list[int]]:
    """
    Calculate absolute and relative channel offsets from timing lags.

    Channel lags represent timing delays (in microseconds) between channels.
    These are converted to AWG sample offsets for synchronization.

    Args:
        channel_lags: Timing lags for each channel in microseconds
        sample_rate: AWG sample rate in Hz

    Returns:
        tuple of (absolute_offsets, relative_offsets) in samples
    """
    # Convert time-based lags to sample-based offsets
    absolute_offsets = [int(np.rint(lag * US_TO_S * sample_rate)) for lag in channel_lags]

    # Relative offsets are computed such that the channel with max offset is 0
    max_offset = max(absolute_offsets) if absolute_offsets else 0
    relative_offsets = [max_offset - offset for offset in absolute_offsets]

    print("\n" + "=" * 60)
    print("Channel Offset Calculation")
    print("=" * 60)
    print(f"Channel lags (µs): {channel_lags}")
    print(f"Sample rate: {sample_rate / 1e6:.1f} MHz")
    print("\nChannel offsets (in AWG samples):")
    for i, (abs_off, rel_off) in enumerate(zip(absolute_offsets, relative_offsets)):
        print(f"  Ch{i + 1}: absolute={abs_off:6d}, relative={rel_off:6d}")

    return absolute_offsets, relative_offsets


# ============================================================================
# Waveform Processing
# ============================================================================


def get_waveform_data(
    waveform: Waveform,
    sample_rate: float,
    calibration_function=None,
    constant_voltage: bool = False,
    double_pass: bool = False,
) -> list[float]:
    """
    Get processed waveform data from a Waveform object.

    Args:
        waveform: Waveform object to process
        sample_rate: Sample rate in Hz (for modulation calculation)
        calibration_function: Optional function to apply calibration (default: identity)
        constant_voltage: If True, return constant voltage (no modulation)
        double_pass: If True, phases are divided by 2 for double-pass AOMs

    Returns:
        list of float values representing waveform samples
    """
    if calibration_function is None:
        calibration_function = lambda x: x

    return waveform.get(
        sample_rate=sample_rate,
        calibration_function=calibration_function,
        constant_voltage=constant_voltage,
        double_pass=double_pass,
    )


def stitch_waveforms_for_channel(
    channel_waveforms: list[Waveform],
    sample_rate: float,
    stitch_delays: list[Any],
    calibration_function=None,
    pad_length: int = 0,
) -> np.ndarray:
    """
    Concatenate and stitch multiple waveforms for a single channel with optional delays.

    Args:
        channel_waveforms: list of Waveform objects to stitch
        sample_rate: Sample rate in Hz
        stitch_delays: Stitch delay configuration (currently limited support)
        calibration_function: Optional calibration function
        pad_length: Padding to add at the end (in samples)

    Returns:
        Stitched waveform as numpy array
    """
    if calibration_function is None:
        calibration_function = lambda x: x

    stitched_data = []

    # NOTE: STILL NEED TO ADD STITCH DELAY HANDLING

    for wf in channel_waveforms:
        wf_data = get_waveform_data(wf, sample_rate, calibration_function, constant_voltage=False)
        print(f"  Waveform '{wf.fname}': {len(wf_data)} samples")
        stitched_data.extend(wf_data)

    # Add padding if requested
    if pad_length > 0:
        stitched_data.extend([0.0] * pad_length)

    return np.array(stitched_data)


def create_marker_waveform(
    waveform_length: int,
    marker_positions: list[int],
    marker_levels: tuple[float, float] = MARKER_LEVS,
    marker_width: int = 50,
    n_pad_left: int = 0,
    n_pad_right: int = 0,
) -> list[float]:
    """
    Create a marker waveform with specified pulse positions.

    Args:
        waveform_length: Length of the main waveform in samples
        marker_positions: list of sample indices where markers should start
        marker_levels: tuple of (low_level, high_level) for marker
        marker_width: Width of each marker pulse in samples
        n_pad_left: Number of samples to pad on the left
        n_pad_right: Number of samples to pad on the right

    Returns:
        list of marker values (0 or 1)
    """
    total_length = n_pad_left + waveform_length + n_pad_right
    data = np.full(total_length, marker_levels[0], dtype=float)

    for pos in marker_positions:
        pos_int = int(pos) + n_pad_left
        if 0 <= pos_int < total_length:
            end_pos = min(pos_int + int(marker_width), total_length)
            data[pos_int:end_pos] = marker_levels[1]

    # Fix for high-start issue: if first element is high, set it low
    if len(data) > 0 and data[0] == marker_levels[1]:
        data[0] = marker_levels[0]

    return data.tolist()


def find_marker_positions(marker_data: list[float]) -> list[int]:
    """
    Find positions where marker transitions from low to high.

    Args:
        marker_data: Marker waveform data

    Returns:
        list of indices where marker pulses begin
    """
    if len(marker_data) < 2:
        return []

    positions = []
    for i in range(1, len(marker_data)):
        # Detect transition from low (0) to high (1)
        if marker_data[i - 1] == 0 and marker_data[i] > 0:
            positions.append(i)

    return positions


# ============================================================================
# Data Alignment and Validation
# ============================================================================


def ensure_alignment(
    waveform_data: list[np.ndarray], marker_data: list[float], align_to: int = 16
) -> tuple[list[np.ndarray], list[float]]:
    """
    Ensure all waveforms and markers are aligned to a multiple of align_to samples.

    This is required by many AWG implementations (e.g., must be multiple of 16).

    Args:
        waveform_data: list of waveform arrays (one per channel)
        marker_data: Marker waveform array
        align_to: Alignment boundary (default: 16)

    Returns:
        tuple of (aligned_waveforms, aligned_markers)
    """
    # Find maximum length
    max_length = max([len(wf) for wf in waveform_data] + [len(marker_data)])

    # Pad to multiple of align_to
    if max_length % align_to != 0:
        max_length = max_length + (align_to - max_length % align_to)

    # Pad all waveforms to max length
    aligned_waveforms = []
    for wf in waveform_data:
        padded = np.pad(np.array(wf), (0, max_length - len(wf)), mode="constant")
        aligned_waveforms.append(padded)

    # Pad marker data
    aligned_marker = np.pad(
        np.array(marker_data), (0, max_length - len(marker_data)), mode="constant"
    )

    print("\n Data alignment:")
    print(f"  Max waveform length: {max_length} samples (aligned to {align_to})")
    for i, wf in enumerate(aligned_waveforms):
        print(f"  Channel {i + 1}: {len(wf)} samples")
    print(f"  Marker: {len(aligned_marker)} samples")

    return aligned_waveforms, aligned_marker.tolist()


# ============================================================================
# AWG Waveform Writing
# ============================================================================


def write_waveforms_to_awg(
    awg: WX218x_awg,
    channels: list[str],
    waveform_data: list[list[float]],
    relative_offsets: list[int],
) -> None:
    """
    Write waveforms to AWG channels with optional time-domain offsets.

    The offsets are applied by rolling the waveform arrays, which effectively
    shifts them in time on the AWG.

    Args:
        awg: The WX218x_awg object
        channels: list of channel names (e.g., ['channel1', 'channel2', ...])
        waveform_data: list of waveform arrays (one per channel)
        relative_offsets: Time offsets in samples for each channel
    """
    print("\n" + "=" * 60)
    print("Writing Waveforms to AWG")
    print("=" * 60)

    if len(channels) != len(waveform_data) or len(channels) != len(relative_offsets):
        raise ValueError(
            f"Channel count mismatch: {len(channels)} channels, "
            f"{len(waveform_data)} waveforms, {len(relative_offsets)} offsets"
        )

    for ch_idx, (channel, data, offset) in enumerate(
        zip(channels, waveform_data, relative_offsets)
    ):
        print(f"\n  Channel {ch_idx + 1}: {channel}")
        print(f"    Samples: {len(data)}")
        print(f"    Offset: {offset} samples")

        # Apply time-domain offset (circular shift)
        if offset != 0:
            data = np.roll(np.array(data), offset).tolist()

        # Set active channel and create waveform
        awg.set_active_channel(channel)
        waveform_handle = awg.create_arbitrary_waveform(data)

        print(f"    Waveform handle: {waveform_handle}")


def write_markers_to_awg(
    awg: WX218x_awg,
    marked_channels: list[str],
    marker_data: list[float],
    marker_width: float,
    sample_rate: float,
) -> None:
    """
    Configure and write marker outputs to specified channels.

    Markers are typically used to synchronize external instruments or TTL signals.

    Args:
        awg: The WX218x_awg object
        marked_channels: list of channels that should have markers
        marker_data: Marker waveform data
        marker_width: Width of marker pulses in microseconds

    Raises:
        ValueError: If more than 2 markers are requested (AWG limitation)
    """
    print("\n" + "=" * 60)
    print("Configuring Markers")
    print("=" * 60)

    # Find marker pulse positions
    marker_positions = find_marker_positions(marker_data)

    if not marker_positions:
        print("  ℹ No markers detected in marker waveform")
        return

    if len(marker_positions) > 2:
        print(
            f" {len(marker_positions)} marker positions requested, "
            f"but AWG only supports 2 markers. Using first 2."
        )
        marker_positions = marker_positions[:2]

    print(f"  Marker positions: {marker_positions}")
    print(f"  Marker width: {marker_width} µs")

    # Convert marker width from microseconds to AWG sample units
    marker_width_samples = int(marker_width * US_TO_S * sample_rate)

    # Assign markers to channels
    for marker_idx, (marker_pos, channel) in enumerate(
        zip(marker_positions, marked_channels[: len(marker_positions)])
    ):
        print(f"\n  Marker {marker_idx + 1}:")
        print(f"    Channel: {channel}")
        print(f"    Position: {marker_pos}")
        print(f"    Width: {marker_width_samples} samples")

        awg.configure_marker(
            channel,
            index=marker_idx + 1,
            position=marker_pos,
            levels=MARKER_LEVS,
            width=marker_width_samples,
        )


def enable_awg_outputs(awg: WX218x_awg, channels: list[str], gain: float = 2.0) -> None:
    """
    Enable output on all AWG channels and set gain.

    Args:
        awg: The WX218x_awg object
        channels: list of channel names to enable
        gain: Output gain/amplitude scaling (default: 2.0)
    """
    print("\n" + "=" * 60)
    print("Enabling AWG Outputs")
    print("=" * 60)

    for channel in channels:
        print(f"  {channel}: gain={gain}")
        awg.enable_channel(channel)
        awg.configure_arb_gain(channel, gain)

    print("All outputs enabled")


# ============================================================================
# Main Control Function
# ============================================================================


def run_awg(awg_config: AwgConfiguration, dev_mode: bool = False) -> Optional[WX218x_awg]:
    """
    Main function to configure and control the AWG for an experiment.

    This is the primary entry point for AWG control. It:
    1. Connects to the AWG (unless in development mode)
    2. Configures general settings (sample rate, output mode)
    3. Calculates and applies channel timing offsets
    4. Processes waveforms according to the configuration
    5. Writes waveforms and markers to the AWG
    6. Enables outputs

    Args:
        awg_config: AwgConfiguration object with all settings
        dev_mode: If True, skip hardware communication (for testing)

    Returns:
        WX218x_awg object if hardware mode, None if dev_mode
    """
    print("\n" + "#" * 60)
    print("# AWG Configuration and Control")
    print("#" * 60)

    awg = None

    try:
        # Connect to hardware (skip in development mode)
        if not dev_mode:
            awg = connect_awg(reset=False)
            configure_awg_general(awg, awg_config)
            configure_triggers(awg, awg_config)
        else:
            print("\n  Development mode: skipping hardware connection")

        # Calculate channel offsets
        abs_offsets, rel_offsets = calculate_channel_offsets(
            awg_config.waveform_output_channel_lags, awg_config.sample_rate
        )

        # Process waveforms
        print("\n" + "=" * 60)
        print("Processing Waveforms")
        print("=" * 60)

        # Build waveform data for each channel
        waveform_data = []
        for channel_waveforms in awg_config.waveform_sequence:
            print(f"Channel waveforms: {channel_waveforms}")
            channel_wfs = [awg_config.waveforms[i] for i in channel_waveforms]
            stitched = stitch_waveforms_for_channel(
                channel_wfs, awg_config.sample_rate, awg_config.waveform_stitch_delays
            )
            waveform_data.append(stitched)
            print(f"  Channel waveform: {len(stitched)} samples")

        # Create marker waveform
        marker_waveform = create_marker_waveform(
            waveform_length=len(waveform_data[0]) if waveform_data else 0,
            marker_positions=[],  # Can be customized as needed
            marker_levels=MARKER_LEVS,
            marker_width=int(awg_config.marker_width * US_TO_S * awg_config.sample_rate),
        )

        # Ensure data alignment
        waveform_data, marker_waveform = ensure_alignment(waveform_data, marker_waveform)

        # Write to AWG (skip in development mode)
        if not dev_mode and awg:
            print(waveform_data[0])
            np.savetxt(
                r"C:\Users\LabUser\Documents\cold-control\waveforms\pulse_shaping_exp\stirap\test_output_waveform.csv",
                waveform_data[0],
                delimiter=",",
            )
            write_waveforms_to_awg(
                awg,
                awg_config.waveform_output_channels,
                waveform_data,
                rel_offsets,
            )

            write_markers_to_awg(
                awg,
                awg_config.marked_channels,
                marker_waveform,
                awg_config.marker_width,
                awg_config.sample_rate,
            )

            enable_awg_outputs(awg, awg_config.waveform_output_channels)

            print("\nAWG configuration complete")
        else:
            print("\n  Development mode: skipping hardware writes")

        return awg

    except Exception as e:
        print(f"\n Error during AWG configuration: {e}")
        if awg:
            try:
                disconnect_awg(awg)
            except:
                pass
        raise
