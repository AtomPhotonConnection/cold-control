"""
This file contains the configuration objects that are loaded by the experiment objects in
the ExperimentalRunner.py file. The configuration objects should be loaded by reading from
a configuration file (see Config.py) and then they can be passed to the experiment object
which will run the experiment with the specified configuration.

@author: Matt King, Jan Ole Ernst
created: 2025-05-30

"""

from __future__ import annotations

import csv
import os
import re
import shutil
from copy import deepcopy
from datetime import datetime
from itertools import product
from typing import Any, Optional

import numpy as np

from classes.rabi_voltage_converter import RabiFreqVoltageConverter
from classes.Sequence import Sequence


def toBool(string):
    GLOB_TRUE_BOOL_STRINGS = ["true", "t", "yes", "y"]
    return string.lower() in GLOB_TRUE_BOOL_STRINGS


def make_property(attr_name):
    return property(
        fget=lambda self: getattr(self, attr_name),
        fset=lambda self, value: setattr(self, attr_name, value),
        fdel=lambda self: delattr(self, attr_name),
    )


def sanitize_filename(name: str) -> str:
    # Remove extension
    name = os.path.splitext(name)[0]
    # Remove all non-alphanumeric or underscore characters
    return re.sub(r"[^A-Za-z0-9_]+", "_", name)


class ExperimentSessionConfig:
    """
    ExperimentSessionConfig manages high-level configuration for an automated experimental session.
    Previously called ExperimentalAutomationConfiguration.

    This includes:
    - The location where experiment data and summaries should be saved
    - A list of individual experiment configurations to run
    - Parameters controlling how frequently DAQ channels are updated

    Intended to coordinate and control the behavior of a full session involving multiple experiments.
    """

    def __init__(
        self,
        save_location,
        summary_fname,
        automated_experiment_configurations,
        daq_channel_update_steps,
        daq_channel_update_delay,
    ):

        self._save_location = save_location
        self._summary_fname = summary_fname
        self._automated_experiment_configurations = automated_experiment_configurations
        self._daq_channel_update_steps = daq_channel_update_steps
        self._daq_channel_update_delay = daq_channel_update_delay

    summary_fname = make_property("_summary_fname")
    save_location = make_property("_save_location")
    automated_experiment_configurations = make_property("_automated_experiment_configurations")
    daq_channel_update_steps = make_property("_daq_channel_update_steps")
    daq_channel_update_delay = make_property("_daq_channel_update_delay")


class GenericConfiguration:
    """
    GenericConfiguration is a placeholder for any configuration that doesn't fit into the other categories.
    This class is not intended to be used directly but serves as a base for other configuration classes.
    """

    def __init__(
        self,
        save_location,
        mot_reload,
        iterations,
    ):

        self._save_location = save_location
        self._mot_reload = mot_reload  # in milliseconds
        self._iterations = iterations

    save_location = make_property("_save_location")
    mot_reload = make_property("_mot_reload")
    iterations = make_property("_iterations")

    def set_mot_reload(self, value):
        """Sets the value of the MOT reload time in milliseconds."""
        self._mot_reload = value

    def set_iterations(self, value):
        self._iterations = value


class ScopeConfiguration:
    """
    Configuration for an oscilloscope used in experiments.

    Defines:
    - Trigger channel and level
    - Sample rate
    - Time range (start, stop) for acquisition
    - Data channels with their voltage ranges, impedances, and couplings
    """

    def __init__(
        self,
        trigger_channel: int,
        trigger_level: float,
        sample_rate: float,
        time_range: Tuple[float, float],
        data_channels: Dict[int, Dict[str, Any]],
    ):
        """
        Args:
            trigger_channel: Oscilloscope trigger channel number
            trigger_level: Trigger threshold voltage
            sample_rate: Sampling rate in Hz
            time_range: Tuple of (start_time, stop_time) in seconds
            data_channels: Dict mapping channel number to config dict with 'range', 'impedance', 'coupling'
        """
        self._trigger_channel = trigger_channel
        self._trigger_level = trigger_level
        self._sample_rate = sample_rate
        self._time_range = time_range
        self._data_channels = data_channels

    trigger_channel = make_property("_trigger_channel")
    trigger_level = make_property("_trigger_level")
    sample_rate = make_property("_sample_rate")
    time_range = make_property("_time_range")
    data_channels = make_property("_data_channels")


class SweepConfiguration:
    """
    Configuration for parameter sweeps in MOT fluorescence experiments.

    Supports two sweep types:
    - "awg_sequence": sweeps over AWG waveform parameters (Rabi frequencies, modulation frequencies)
    - "mot_imaging": sweeps over imaging parameters (beam powers, frequencies, pulse lengths/times)
    """

    def __init__(self, sweep_type: str, num_shots: int, sweep_parameters: Dict[str, Any]):
        """
        Args:
            sweep_type: Either "awg_sequence" or "mot_imaging"
            num_shots: Number of repetitions per sweep point
            sweep_parameters: Dict with sweep-type-specific parameters
        """
        self._sweep_type = sweep_type
        self._num_shots = num_shots
        self._sweep_parameters = sweep_parameters

    sweep_type = make_property("_sweep_type")
    num_shots = make_property("_num_shots")
    sweep_parameters = make_property("_sweep_parameters")


class MotFluoresceConfiguration(GenericConfiguration):
    """
    Configuration for a MOT fluorescence experiment.

    Loads configuration from an experiment config file and manages sub-configurations
    for camera, scope, AWG, and optional sweep parameters.

    The data used to configure the experiment should be loaded from a configuration file
    using the "ExperimentConfigReader" class and the get_mot_fluoresce_configuration method.
    This class must be passed to the MotFluoresceExperiment class to run the experiment.

    Attributes:
        - save_location: Directory where experiment data is saved
        - mot_reload: Time in milliseconds to wait for MOT to reload
        - iterations: Number of experiment repetitions
        - use_cam: Whether to use camera for imaging
        - use_scope: Whether to use oscilloscope for data acquisition
        - use_awg: Whether to use AWG
        - sequence: Sequence object defining DAQ timing and channels
        - cam_config: CameraConfiguration object (if use_cam is True)
        - scope_config: ScopeConfiguration object (if use_scope is True)
        - awg_config: AwgConfiguration object (if use_awg is True)
        - sweep_config: SweepConfiguration object (if sweep is enabled)
    """

    def __init__(
        self,
        save_location: str,
        mot_reload: float,
        iterations: int,
        use_cam: bool,
        use_scope: bool,
        use_awg: bool,
        sequence: Sequence | None = None,
        cam_config: "CameraConfiguration" | None = None,
        scope_config: ScopeConfiguration | None = None,
        awg_config: AwgConfiguration | None = None,
        sweep_config: SweepConfiguration | None = None,
    ):
        """
        Initialize MOT fluorescence configuration with optional sub-configurations.

        Args:
            save_location: Directory for data storage
            mot_reload: MOT reload time in ms
            iterations: Number of experimental repetitions
            use_cam: Enable camera
            use_scope: Enable oscilloscope
            use_awg: Enable AWG
            sequence: Sequence object for DAQ timing and channel configuration
            cam_config: Camera configuration (required if use_cam=True)
            scope_config: Scope configuration (required if use_scope=True)
            awg_config: AWG configuration (required if use_awg=True)
            sweep_config: Sweep configuration (optional)
        """
        super().__init__(save_location, mot_reload, iterations)

        self.use_cam = use_cam
        self.use_scope = use_scope
        self.use_awg = use_awg
        self.sequence = sequence

        # Validate camera configuration
        if use_cam:
            if cam_config is None:
                raise ValueError("cam_config must be provided if use_cam is True")
            self.cam_config = cam_config
        else:
            self.cam_config = None
            print("No camera will be used.")

        # Validate scope configuration
        if use_scope:
            if scope_config is None:
                raise ValueError("scope_config must be provided if use_scope is True")
            self.scope_config = scope_config
        else:
            self.scope_config = None

        # Validate AWG configuration
        if use_awg:
            if awg_config is None:
                raise ValueError("awg_config must be provided if use_awg is True")
            self.awg_config = awg_config
        else:
            self.awg_config = None
            print("No AWG will be used.")

        # Optional sweep configuration
        self.sweep_config = sweep_config

    @property
    def scope_trigger_channel(self):
        """Backward compatibility: retrieve scope trigger channel from config."""
        if self.scope_config is None:
            raise AttributeError("Scope not configured for this experiment")
        return self.scope_config.trigger_channel

    @property
    def scope_trigger_level(self):
        """Backward compatibility: retrieve scope trigger level from config."""
        if self.scope_config is None:
            raise AttributeError("Scope not configured for this experiment")
        return self.scope_config.trigger_level

    @property
    def scope_sample_rate(self):
        """Backward compatibility: retrieve scope sample rate from config."""
        if self.scope_config is None:
            raise AttributeError("Scope not configured for this experiment")
        return self.scope_config.sample_rate

    @property
    def scope_time_range(self):
        """Backward compatibility: retrieve scope time range from config."""
        if self.scope_config is None:
            raise AttributeError("Scope not configured for this experiment")
        return self.scope_config.time_range

    @property
    def scope_data_channels(self):
        """Backward compatibility: retrieve scope data channels from config."""
        if self.scope_config is None:
            raise AttributeError("Scope not configured for this experiment")
        return self.scope_config.data_channels


class CameraConfiguration:
    """
    Configuration for a camera used in MOT fluorescence experiments.

    Defines:
    - Camera exposure and gain settings
    - Trigger channel and pulse width
    - Whether to save images
    """

    def __init__(
        self,
        cam_exposure: int,
        cam_gain: int,
        camera_trigger_channel: int,
        camera_trigger_level: float,
        camera_pulse_width: float,
        save_images: bool = True,
    ):
        """
        Args:
            cam_exposure: Camera exposure setting
            cam_gain: Camera gain setting
            camera_trigger_channel: DAQ channel for camera trigger
            camera_trigger_level: Trigger voltage level
            camera_pulse_width: Trigger pulse width in microseconds
            save_images: Whether to save acquired images
        """
        self._cam_exposure = cam_exposure
        self._cam_gain = cam_gain
        self._camera_trigger_channel = camera_trigger_channel
        self._camera_trigger_level = camera_trigger_level
        self._camera_pulse_width = camera_pulse_width
        self._save_images = save_images

    cam_exposure = make_property("_cam_exposure")
    cam_gain = make_property("_cam_gain")
    camera_trigger_channel = make_property("_camera_trigger_channel")
    camera_trigger_level = make_property("_camera_trigger_level")
    camera_pulse_width = make_property("_camera_pulse_width")
    save_images = make_property("_save_images")


class MotFluoresceConfigurationSweep:
    """
    Manages sweep configurations for MOT fluorescence experiments.

    Given a base configuration, sweep type, and sweep parameters, generates
    multiple experiment configurations (one per sweep point) with corresponding
    sequence modifications.

    Supports two sweep types:
    - "awg_sequence": modifies AWG waveforms and frequencies
    - "mot_imaging": modifies imaging parameters (beam power, frequency, pulse timing)
    """

    def __init__(
        self,
        base_config: "MotFluoresceConfiguration",
        base_sequence: Sequence,
        sweep_type: str,
        num_shots: int,
        sweep_params: Dict[Any, Any],
    ):
        """
        Initialize sweep configuration.

        Args:
            base_config: Base MOT fluorescence configuration
            base_sequence: Base sequence to be modified for each sweep point
            sweep_type: Either "awg_sequence" or "mot_imaging"
            num_shots: Number of repetitions per sweep point
            sweep_params: Dictionary with sweep-type-specific parameters
        """
        self.base_config = base_config
        self.base_sequence = base_sequence
        self.sweep_type = sweep_type
        self.sweep_params = sweep_params
        self.num_shots = num_shots

        now = datetime.now()
        self.current_date = now.strftime("%Y-%m-%d")
        self.current_time = now.strftime("%H-%M-%S")
        print(f"[DEBUG] Sweep date: {self.current_date}, time: {self.current_time}")

        self.configs: List[MotFluoresceConfiguration] = []
        self.sequences: List[Sequence] = []
        print("Creating all MOT fluorescence configurations for the sweep...")

        if sweep_type == "awg_sequence":
            wave_idxs = self.sweep_params["waveform_indices"]
            rabi_freqs = self.sweep_params["rabi_frequencies"]
            mod_freqs = self.sweep_params["modulation_frequencies"]
            waveforms_paths = self.sweep_params["waveforms"]
            calib_paths = self.sweep_params["calibration_paths"]
            all_sweeps = self.sweep_params["sweeps"]
            self.__configure_awg_sweep(
                wave_idxs, rabi_freqs, mod_freqs, waveforms_paths, calib_paths, all_sweeps
            )

        elif sweep_type == "mot_imaging":
            # all these parameters need to be extracted from the config file
            _beam_powers: list[float] = self.sweep_params["beam_powers"]
            _beam_frequencies: list[float] = self.sweep_params["beam_frequencies"]
            _pulse_lengths: list[int] = self.sweep_params["pulse_lengths"]
            _pulse_times: list[int] = self.sweep_params["pulse_times"]
            self.__configure_imaging_sweep(
                _beam_powers, _beam_frequencies, _pulse_lengths, _pulse_times
            )

        else:
            raise ValueError(
                f"Sweep type '{sweep_type}' not supported. Use 'awg_sequence' or 'mot_imaging'."
            )

        assert len(self.configs) == len(self.sequences), (
            "configs and sequences must have the same length"
        )

    def __iter__(self):
        """
        When iterating over the object it returns a tuple containing a MotFluoresceConfiguration
        object and the associated Sequence object. These can then be used to run a single shot
        of the sweep.
        """
        return iter(zip(self.configs, self.sequences))

    def __len__(self):
        """Return the number of sweep configurations."""
        return len(self.configs)

    def __configure_awg_sweep(
        self, wave_idxs, rabi_freqs, mod_freqs, waveforms_paths, calib_paths, all_sweeps
    ):
        """
        Creates the list of MOTFluoresceConfiguration objects and Sequence objects for each
        of the different experiments to be run by the sweep. This function changes the
        MOTFluoresceConfiguration objects so that the AWG configs are different, allowing
        for experiments with different pulse shapes.
        """

        # Delete the temp folder and its contents if it exists, then recreate it
        temp_root = "temp"
        if os.path.exists(temp_root):
            shutil.rmtree(temp_root)
        os.makedirs(temp_root, exist_ok=True)

        for shot in range(self.num_shots):
            for sweep_dict in all_sweeps:
                sweep_title = sweep_dict["title"]
                rabis = sweep_dict.get("rabi_frequencies", rabi_freqs)
                freqs = sweep_dict.get("modulation_frequencies", mod_freqs)
                waves = sweep_dict.get("waveforms", waveforms_paths)
                calibs = sweep_dict.get("calibration_paths", calib_paths)

                new_paths = {}
                for j, idx in enumerate(wave_idxs):
                    if waves[j] == "":
                        # This means the pulse shouldn't be changed
                        new_paths[idx] = waves[j]  # No rescaling needed
                    else:
                        pulse_path = f"temp/{sweep_title}/{idx}.csv"

                        if not os.path.exists(pulse_path):
                            os.makedirs(os.path.dirname(pulse_path), exist_ok=True)
                            calib_path = os.path.join(
                                calibs[j], f"{freqs[j] / 1e6:.0f}MHz\\rabi_data.csv"
                            )
                            rabi_converter = RabiFreqVoltageConverter(calib_path)

                            rabi_converter.rescale_csv(
                                rabis[j] * 2 * np.pi, waves[j], pulse_path, normalised=False
                            )

                        new_paths[idx] = pulse_path

                # Clone and modify base configuration
                new_config = deepcopy(self.base_config)
                new_sequence = deepcopy(self.base_sequence)

                # Modify waveform and frequency settings
                modified_sequence_config = self.modify_awg_sequence_config(
                    base_config=new_config.awg_config,
                    waveform_csvs={idx: new_paths[idx] for idx in wave_idxs},
                    mod_freqs={idx: freqs[j] for j, idx in enumerate(wave_idxs)},
                )

                # Update the new config with modified sequence
                new_config.awg_config = modified_sequence_config

                new_config.save_location = os.path.join(
                    self.base_config.save_location,
                    self.current_date,
                    self.current_time,
                    sweep_title,
                    f"shot{shot:03d}",
                )

                if not os.path.exists(self.base_config.save_location):
                    raise FileNotFoundError(
                        f"Base save location does not exist: {self.base_config.save_location}"
                    )
                # Ensure the directory exists
                save_dir = os.path.dirname(new_config.save_location)
                os.makedirs(save_dir, exist_ok=True)

                self.configs.append(new_config)
                self.sequences.append(new_sequence)

    def __configure_imaging_sweep(self, beam_powers, beam_frequencies, pulse_lengths, pulse_times):
        to_sweep = []
        if len(beam_powers) > 1:
            to_sweep.append("beam_powers")
        if len(beam_frequencies) > 1:
            to_sweep.append("beam_frequencies")
        if len(pulse_lengths) > 1:
            to_sweep.append("pulse_lengths")
        if len(pulse_times) > 1:
            to_sweep.append("pulse_times")
        print(f"Sweeping over the following parameters: {to_sweep}")

        for i in range(self.num_shots):
            for power, freq, length, time in product(
                beam_powers, beam_frequencies, pulse_lengths, pulse_times
            ):
                # Clone and modify the base sequence and config
                new_config = deepcopy(self.base_config)
                new_sequence = deepcopy(self.base_sequence)

                # Create unique filename suffix based on swept parameters
                file_text = ""
                for param in to_sweep:
                    if param == "beam_powers":
                        file_text += f"power{power:.2f}V_"
                    elif param == "beam_frequencies":
                        file_text += f"freq{freq:.2f}V_"
                    elif param == "pulse_lengths":
                        file_text += f"length{length}us_"
                    elif param == "pulse_times":
                        file_text += f"time{time}us_"

                # Modify save location to easily manage data
                new_config.save_location = os.path.join(
                    self.base_config.save_location,
                    self.current_date,
                    self.current_time,
                    file_text.rstrip("_"),
                    f"shot{i}",
                )

                # Modifies the sequence
                freq_ch = 2  # These values shouldn't be hardcoded
                power_ch = 6
                new_sequence.updateChannel(
                    freq_ch,
                    [
                        (0, freq),
                    ],
                    [
                        0,
                    ],
                )
                tv_pairs = list(new_sequence.get_tV_pairs(power_ch))
                print(f"The old tv pairs for the imaging channel are: {tv_pairs}")
                # HACK to change the correct power value and pulse length
                img_start_tv = tv_pairs[2]  # This is a tuple representing a time voltage pair
                img_end_tv = tv_pairs[3]
                new_start_tv = (time, power)
                new_end_tv = (time + length, img_end_tv[1])
                tv_pairs[2] = new_start_tv
                tv_pairs[3] = new_end_tv
                print(f"The new tv pairs for the imaging channel are: {tv_pairs}")
                new_vint_styles = new_sequence.get_V_intervalStyles(power_ch)
                new_sequence.updateChannel(power_ch, tv_pairs, new_vint_styles)

                # Ensure directory exists
                if not os.path.exists(self.base_config.save_location):
                    raise FileNotFoundError(
                        f"Base save location does not exist: {self.base_config.save_location}"
                    )
                save_dir = os.path.dirname(new_config.save_location)
                os.makedirs(save_dir, exist_ok=True)

                # Append sequence and config files to the list
                self.configs.append(new_config)
                self.sequences.append(new_sequence)

    @staticmethod
    def modify_awg_sequence_config(
        *, base_config: AwgConfiguration, waveform_csvs: dict[int, str], mod_freqs: dict[int, float]
    ) -> AwgConfiguration:
        new_config = deepcopy(base_config)

        for idx, wf in enumerate(new_config.waveforms):
            if idx in waveform_csvs:
                wf.fname = waveform_csvs[idx]
            if idx in mod_freqs:
                wf.mod_frequency = mod_freqs[idx]

        return new_config

    # this can be used as follows:
    # base_config = MotFluoresceConfiguration(...)

    # waveform_csvs_ch1 = ['waveform1.csv', 'waveform2.csv']
    # waveform_csvs_ch2 = ['waveform3.csv', 'waveform4.csv']

    # mod_freqs_ch1 = [1e6, 2e6]
    # mod_freqs_ch2 = [3e6, 4e6]
    # sweep = MotFluoresceConfigurationSweep(base_config, waveform_csvs_ch1, waveform_csvs_ch2, mod_freqs_ch1, mod_freqs_ch2)
    # for config in sweep:


class AWGSequenceConfiguration:
    """
    [DEPRECATED] Use AwgConfiguration instead.

    This class is kept for backward compatibility but should not be used for new code.
    """

    def __init__(
        self,
        waveform_sequence,
        waveforms,
        interleave_waveforms,
        waveform_stitch_delays,
        awg_configuration,
    ):
        print("Warning: AWGSequenceConfiguration is deprecated. Use AwgConfiguration instead.")
        self._waveform_sequence = waveform_sequence
        self.waveforms: list[Waveform] = waveforms
        self.interleave_waveforms: bool = interleave_waveforms
        self.waveform_stitch_delays = waveform_stitch_delays
        self._awg_configuration: AwgConfiguration = awg_configuration

    @property
    def waveform_sequence(self):
        return self._waveform_sequence

    @waveform_sequence.setter
    def waveform_sequence(self, value):
        print("Setting waveform sequence to", value, [type(x) for x in value])
        self._waveform_sequence = value

    @waveform_sequence.deleter
    def waveform_sequence(self):
        del self._waveform_sequence

    awg_configuration = make_property("_awg_configuration")


class PhotonProductionConfiguration(GenericConfiguration):
    """
    PhotonProductionConfiguration stores all configuration parameters
    required for a photon production experiment.

    This includes:
    - Save location and MOT reload time
    - Number of iterations
    - A waveform sequence and its associated waveforms
    - Interleaving and stitching behavior for waveforms
    - Configuration objects for the AWG and TDC systems
    """

    def __init__(
        self,
        save_location,
        mot_reload,
        iterations,
        waveform_sequence,
        waveforms,
        interleave_waveforms,
        waveform_stitch_delays,
        awg_configuration,
        tdc_configuration,
    ):

        super().__init__(save_location, mot_reload, iterations)

        self._waveform_sequence = waveform_sequence
        self.waveforms: list[Waveform] = waveforms
        self.interleave_waveforms: bool = interleave_waveforms
        self.waveform_stitch_delays = waveform_stitch_delays

        self._awg_configuration: AwgConfiguration = awg_configuration
        self._tdc_configuration: TdcConfiguration = tdc_configuration

    # --- waveform_sequence ---
    @property
    def waveform_sequence(self):
        return self._waveform_sequence

    @waveform_sequence.setter
    def waveform_sequence(self, value):
        print("Setting waveform sequence to", value, [type(x) for x in value])
        self._waveform_sequence = value

    @waveform_sequence.deleter
    def waveform_sequence(self):
        del self._waveform_sequence

    awg_configuration = make_property("_awg_configuration")
    tdc_configuration = make_property("_tdc_configuration")


class AbsorbtionImagingConfiguration(GenericConfiguration):
    """
    This object stores and presents for editing the settings for absorbtion imaging experiments.

        scan_abs_img_freq - TODO
        abs_img_freq_ch - TODO
        abs_img_freqs - TODO
        camera_trig_ch, imag_power_ch - The DAQ channels that trigger the camera and control the imaging light power.
        camera_pulse_width, imag_pulse_width - How long to make the trigger pulse and absorbtion imaging flash in microseconds.
        t_imgs - The times at which to take images (in microseconds where 0 is the beginning of the sequence).
        mot_reload_time - The MOT reload time in ms
        bkg_off_channels - A list of channels (specified by channel number) to turn off during background pictures.
        n_backgrounds - The number of background images to take for each absorbtion image.
        cam_gain - The gain setting for the camera when taking the picture.
        cam_exposure - How long the camera exposure should be.  Passes as an integer x which corresponds to an exposure time of 1/x seconds.
        save_location - The folder to save images to as 'save_location/{date}/{time}/'
        save_raw_images - Boolean determining whether the raw images (i.e. processed absorbtion images and all background contributing to
                          the background average) are saved.
        save_processed_images - Boolean determining whether the processed images (i.e. absorbtion images after background subtraction and
                                average backgrounds) are automatically saved.
        review_processed_images - Boolean determining whether the Absorbtion_imaging_review_UI is launched after the images are processed
                                  to allow the user to review the images, add notes and decide whether to save or not. Note that since the
                                  user is given the chance to review the processed images, the option to automatically save them is disabled
                                  when review_processed_images=True.
    """

    def __init__(
        self,
        scan_abs_img_freq,
        abs_img_freq_ch,
        abs_img_freqs,
        camera_trig_ch,
        imag_power_ch,
        camera_trig_levs,
        imag_power_levs,
        camera_pulse_width,
        imag_pulse_width,
        t_imgs,
        mot_reload,
        n_backgrounds,
        bkg_off_channels,
        cam_gain,
        cam_exposure,
        cam_gain_lims,
        cam_exposure_lims,
        save_location,
        save_raw_images,
        save_processed_images,
        review_processed_images,
        iterations=1,
    ):
        super().__init__(save_location, mot_reload, iterations)

        self.scan_abs_img_freq = scan_abs_img_freq
        self.abs_img_freq_ch = abs_img_freq_ch
        self.abs_img_freqs = abs_img_freqs
        self.camera_trig_ch = camera_trig_ch
        self.imag_power_ch = imag_power_ch
        self.camera_trig_levs = camera_trig_levs
        self.imag_power_levs = imag_power_levs
        self.camera_pulse_width = camera_pulse_width
        self.imag_pulse_width = imag_pulse_width
        self.t_imgs = t_imgs
        self.mot_reload_time = mot_reload
        self.n_backgrounds = n_backgrounds
        self.bkg_off_channels = bkg_off_channels
        self.cam_gain = cam_gain
        self.cam_exposure = cam_exposure
        self.cam_gain_lims = cam_gain_lims
        self.cam_exposure_lims = cam_exposure_lims
        self.save_location = save_location
        self.save_raw_images = save_raw_images
        self.save_processed_images = save_processed_images
        self.review_processed_images = review_processed_images


class SingleExperimentConfig(GenericConfiguration):
    """
    [DEPRECATED] Use MotFluoresceConfiguration instead.

    Kept for backward compatibility but should not be used for new code.
    """

    def __init__(
        self,
        daq_channel_static_values,
        sequence_fname,
        sequence,
        iterations,
        mot_reload,
        modulation_frequencies,
        save_location=None,
    ):

        self._daq_channel_static_values = daq_channel_static_values
        self._sequence_fname = sequence_fname
        self._sequence = sequence
        self._modulation_frequencies = modulation_frequencies
        super().__init__(save_location, mot_reload, iterations)

    daq_channel_static_values = make_property("_daq_channel_static_values")
    sequence_fname = make_property("_sequence_fname")
    iterations = make_property("_iterations")
    mot_reload_time = make_property("_mot_reload_time")
    sequence = make_property("_sequence")
    modulation_frequencies = make_property("_modulation_frequencies")


class Waveform:
    def __init__(self, fname: str, mod_frequency: float, phases: list[tuple[float, int]]):
        self.__fname = fname
        self.__mod_frequency = mod_frequency
        self.__phases = sorted(phases, key=lambda x: x[1])  # Sort by index
        self.data = self.__load_data()

    def __load_data(self) -> list[float]:
        """Loads waveform data from a CSV file."""
        with open(self.__fname) as csvfile:
            print("Loading waveform:", self.__fname)
            reader = csv.reader(csvfile, delimiter=",")
            data = []
            for row in reader:
                if len(row) > 1:
                    data += list(map(float, row))
                else:
                    data.append(float(row[0]))

        if len(data) == 0:
            raise ValueError(f"Waveform file {self.__fname} is empty or invalid.")

        return data

    def get(
        self,
        sample_rate: float,
        calibration_function=lambda level: level,
        constant_voltage=False,
        double_pass=False,
    ) -> list[float]:
        """
        Returns the modulated waveform data.

        - Applies the calibration function.
        - If constant_voltage is False, applies sinusoidal modulation.
        """
        mod_data = [calibration_function(x) for x in self.data]
        if constant_voltage or float(self.__mod_frequency) == 0.0:
            return mod_data

        t_step = 2 * np.pi / sample_rate
        phi = 0.0
        # Divided phases by two for double passed AOM.
        phases = [(x[0] / 2 if double_pass else x[0], x[1]) for x in self.__phases]
        next_phi, next_i_flip = (None, None) if not phases else phases.pop(0)

        for i in range(len(mod_data)):
            if i == next_i_flip:
                phi = next_phi
                next_phi, next_i_flip = (None, None) if not phases else phases.pop(0)
            if phi is None:
                raise ValueError("Phase not set before modulation.")
            mod_data[i] *= np.sin(i * t_step * self.__mod_frequency + phi)

        return mod_data

    def get_marker_data(
        self,
        marker_positions=[],
        marker_levels=(0, 1),
        marker_width=50,
        n_pad_right=0,
        n_pad_left=0,
    ) -> list[int]:
        """
        Returns a marker waveform.

        Pads with zeros on both sides, and marks selected positions with high levels.
        """
        data = np.array([marker_levels[0]] * (n_pad_left + len(self.data) + n_pad_right))
        for pos in marker_positions:
            pos = int(pos)
            data[pos : pos + int(marker_width)] = marker_levels[1]

        # Fix for high-start issue
        if data[0] == 1:
            data[0] = 0

        return data.tolist()

    def get_profile(self) -> list[float]:
        """Returns the raw waveform data."""
        return self.data

    def get_n_samples(self) -> int:
        """Returns the number of samples in the waveform."""
        return len(self.data)

    def get_t_length(self, sample_rate: float) -> float:
        """Returns the duration of the waveform at a given sample rate."""
        return len(self.data) * sample_rate

    def set_mod_frequency(self, value: float):
        """Sets the modulation frequency."""
        self.__mod_frequency = value

    # --- Properties ---

    @property
    def fname(self) -> str:
        return self.__fname

    @fname.setter
    def fname(self, value: str):
        self.__fname = value
        self.data = self.__load_data()

    @property
    def mod_frequency(self) -> float:
        return self.__mod_frequency

    @mod_frequency.setter
    def mod_frequency(self, value: float):
        self.__mod_frequency = value

    @property
    def phases(self) -> list[tuple[float, int]]:
        return self.__phases

    @phases.setter
    def phases(self, value: list[tuple[float, int]]):
        self.__phases = sorted(value, key=lambda x: x[1])


class AwgConfiguration:
    """
    Configuration for an Arbitrary Waveform Generator (AWG), including sample rate,
    output channels, timing lags, marker widths, and calibration locations.
    It also includes the waveform sequence and associated waveforms that the AWG will
    play.

    Structure of the AWG configuration file:
    waveform sequence: A list of lists. Each inner list corresponds to a channel and
        contains the indices of the waveforms to play on that channel.
    waveform stitch delays: DEPRECATED
    interleave waveforms: DEPRECATED
    sample rate: Sample rate for the AWG output in samples per second.
    burst count: Number of times to repeat the waveform sequence in a single trigger.
    waveform output channels: Channels on the AWG that will be used for outputting waveforms.
    waveform output channel lags: Timing lags for each output channel to synchronize them.
    marked channels: DEPRECATED
    marker width: Width of the marker pulse in us. TODO switch to samples.

    waveforms:
    A list of waveform configurations, including: TODO make a dictionary instead of a list to avoid confusion about which waveform is which.
        modulation frequency: The "carrier" frequency for the waveform
        phases: DEPRECATED
        filename: The path to the CSV file containing the waveform data. The CSV should
            contain a single row of voltage values, one per column.

    """

    def __init__(
        self,
        waveform_sequence: list[list[int]],
        waveforms: list[Waveform],
        sample_rate: float,
        burst_count: int,
        waveform_output_channels: list[int],
        waveform_output_channel_lags: list[float],
        marker_width: int,
        waveform_stitch_delays: Optional[list[list[Any]]] = None,
        interleave_waveforms: Optional[bool] = None,
        marked_channels: Optional[list[int]] = None,
    ):

        self._waveform_sequence = waveform_sequence
        self.waveforms = waveforms
        self.interleave_waveforms = interleave_waveforms
        self.waveform_stitch_delays = waveform_stitch_delays

        self._sample_rate = sample_rate
        self._burst_count = burst_count
        self._waveform_output_channels = waveform_output_channels

        self.waveform_output_channel_lags = waveform_output_channel_lags
        self.marked_channels = marked_channels
        self.marker_width = marker_width

    sample_rate: property = make_property("_sample_rate")
    burst_count: property = make_property("_burst_count")
    waveform_output_channels: property = make_property("_waveform_output_channels")

    def set_burst_count(self, value: int):
        self._burst_count = value

    def set_sample_rate(self, value: float):
        self._sample_rate = value

    @property
    def waveform_sequence(self):
        return self._waveform_sequence

    @waveform_sequence.setter
    def waveform_sequence(self, value):
        print("Setting waveform sequence to", value, [type(x) for x in value])
        self._waveform_sequence = value

    @waveform_sequence.deleter
    def waveform_sequence(self):
        del self._waveform_sequence


class TdcConfiguration:
    """
    Configuration for a Time-to-Digital Converter (TDC), including the channels used for
    counting events, the marker channel for synchronization, and the timestamp buffer size.
    """

    def __init__(
        self, counter_channels: list[int], marker_channel: int, timestamp_buffer_size: int
    ):
        self._counter_channels = counter_channels
        self._marker_channel = marker_channel
        self._timestamp_buffer_size = timestamp_buffer_size

    counter_channels = make_property("_counter_channels")
    marker_channel = make_property("_marker_channel")
    timestamp_buffer_size = make_property("_timestamp_buffer_size")

    def set_counter_channels(self, value: list[int]):
        self._counter_channels = value

    def set_marker_channel(self, value: int):
        self._marker_channel = value
