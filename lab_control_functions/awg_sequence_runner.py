"""AWG sequence runner — standalone script for configuring and running
the AWG from a config file using AWGManager.

Reads an AWG + photon-production config file, builds the necessary
configuration objects, and uploads waveforms via AWGManager.
"""

from __future__ import annotations

import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from classes.config_readers import AwgConfigReader, ConfigReader, DaqReader
from classes.experimental_configs import (
    AwgConfiguration,
    PhotonProductionConfiguration,
)
from instruments.WX218x.awg_manager import AWGManager

"""AWG control functions — high-level helpers for configuring and running
the Tabor WX218x AWG.

Refactored to use AWGManager (PyVISA/SCPI) instead of the deprecated
DLL-based WX218x_awg driver.
"""


# Constants for marker configuration
MARKER_LOW = 0.0
MARKER_HIGH = 1.2
MARKER_WF_LOW = 0.0
MARKER_WF_HIGH = 1
MARKER_WIDTH_FACTOR = 10**-6
ABSOLUTE_OFFSET_FACTOR = 10**-6
DEFAULT_MARKER_OFFSET = 500

MARKER_WF_LEVS = (MARKER_WF_LOW, MARKER_WF_HIGH)
MARKER_LEVS = (MARKER_LOW, MARKER_HIGH)


def connect_awg() -> AWGManager:
    """Connect to the AWG via AWGManager (PyVISA/SCPI).

    Returns
    -------
    AWGManager
        A connected AWGManager instance.
    """
    print("Connecting to AWG...")
    awg = AWGManager()
    print("...connected")
    return awg


def plot_marker_data(marker_data):
    """Plot marker data for visualization."""
    plt.plot(marker_data)
    plt.title("Marker Data")
    plt.show()


def get_waveform_calib_fnc(calib_fname: str, max_eff: float = 0.9):
    """Generate a calibration function from a file containing waveform calibration data.

    Parameters
    ----------
    calib_fname : str
        Path to the calibration file (two-column, header row).
    max_eff : float
        Maximum efficiency value; rows above this are removed.

    Returns
    -------
    callable
        Interpolation function mapping efficiency values to calibration voltages.
    """
    calib_data = np.genfromtxt(calib_fname, skip_header=1)
    calib_data[:, 1] /= 100.0
    calib_data = calib_data[(calib_data[:, 1] <= max_eff)]
    calib_data[:, 1] /= max(calib_data[:, 1])

    def interp_fct(x):
        return np.interp(np.abs(x), calib_data[:, 1], calib_data[:, 0])

    return interp_fct


def run_awg(
    awg_config: AwgConfiguration,
    photon_config: PhotonProductionConfiguration | None = None,
) -> tuple[AWGManager, float]:
    """Configure the AWG for an experiment using :class:`AWGManager`.

    All hardware communication (connection, reset, waveform processing,
    upload, trigger configuration, marker setup and arming) is delegated
    to :meth:`AWGManager.upload_and_arm`.

    Parameters
    ----------
    awg_config : AwgConfiguration
        AWG settings including sample rate, burst count, output channels,
        marker width, waveform sequence and waveforms.
    photon_config : PhotonProductionConfiguration or None
        Legacy parameter kept for backward compatibility.  If provided and
        *awg_config* does not already have waveforms / sequence set, they
        are copied from *photon_config*.

    Returns
    -------
    tuple[AWGManager, float]
        The connected :class:`AWGManager` instance and the total waveform
        duration in seconds.
    """
    # Legacy support: copy waveforms/sequence from photon_config if needed
    if photon_config is not None:
        if awg_config.waveforms is None or len(awg_config.waveforms) == 0:
            awg_config.waveforms = photon_config.waveforms
        if awg_config.waveform_sequence is None or len(awg_config.waveform_sequence) == 0:
            awg_config.waveform_sequence = photon_config.waveform_sequence

    awg = connect_awg()
    awg.upload_and_arm(awg_config)

    # Calculate waveform duration from the processed data
    max_samples = 0
    for ch_seq in awg_config.waveform_sequence:
        ch_samples = sum(awg_config.waveforms[i].get_n_samples() for i in ch_seq)
        max_samples = max(max_samples, ch_samples)

    duration = max_samples / awg_config.sample_rate
    print(f"AWG configuration complete. Waveform duration: {duration:.6f} s")
    return awg, duration


def disconnect_awg(awg: AWGManager) -> None:
    """Cleanly shut down the AWG connection.

    Parameters
    ----------
    awg : AWGManager
        The AWGManager instance to disconnect.
    """
    awg.abort()
    awg.close()
    print("AWG disconnected.")


if __name__ == "__main__":
    path_to_config = r"configs\photon production\newPhotonProductionConfigJan"

    awg_config: AwgConfiguration = AwgConfigReader(path_to_config).get_awg_config()

    # Configure the AWG (connect, upload, arm)
    awg, duration = run_awg(awg_config)
    print(f"AWG armed. Waveform duration: {duration:.6f} s")

    # Opens a new config file as a "config reader" object.
    config_reader = ConfigReader(Path.cwd() / "configs" / "rootConfig.ini")
    for _i in range(1, 1000):
        daq_config_fname = config_reader.get_daq_config_fname()
        daq_controller = DaqReader(daq_config_fname).load_daq_controller()

        # Manual DAQ channel control
        daq_controller.continuousOutput = True
        daq_controller.update_channel_value(22, 2.6)
        daq_controller.update_channel_value(14, 2.485)
        daq_controller.update_channel_value(8, 0.0048)
        daq_controller.release_all()
        time.sleep(1)
