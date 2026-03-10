"""
This file contains the configuration objects that are loaded by the experiment objects in
the experimental_runner.py file. The configuration objects should be loaded by reading from
a configuration file (see Config.py) and then they can be passed to the experiment object
which will run the experiment with the specified configuration.

@author: Matt King, Jan Ole Ernst
created: 2025-05-30

"""

from __future__ import annotations

import csv
import logging
import re
import shutil
import warnings
from copy import deepcopy
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any, cast

import numpy as np

from classes.daq_sequence import DaqSequence
from classes.rabi_voltage_converter import RabiFreqVoltageConverter

logger = logging.getLogger(__name__)


def make_property(attr_name):
    return property(
        fget=lambda self: getattr(self, attr_name),
        fset=lambda self, value: setattr(self, attr_name, value),
        fdel=lambda self: delattr(self, attr_name),
    )


def sanitize_filename(name: str) -> str:
    # Remove extension
    name = Path(name).stem
    # Remove all non-alphanumeric or underscore characters
    return re.sub(r"[^A-Za-z0-9_]+", "_", name)


class Waveform:
    """Represents a single waveform envelope loaded from a CSV file.

    Parameters
    ----------
    fname : str
        Path to a CSV file containing the waveform envelope.  The file may be
        formatted as either:
        * **Single row, many columns** - one row of comma-separated float values.
        * **Single column, many rows** - one float value per line.
        Ambiguous files (multiple rows *and* multiple columns) are rejected.
    modulated : bool | None, optional
        Whether sinusoidal modulation should be applied to the envelope when
        :meth:`get` is called.  If ``None`` (the default), inferred automatically:
        ``True`` when ``mod_frequency`` is non-zero, ``False`` otherwise.
        Pass an explicit ``True`` or ``False`` to override.
    mod_frequency : float, optional
        The carrier / modulation frequency in Hz.  Only used when
        ``modulated`` is ``True``.  Defaults to ``0.0``.
    phases : list[tuple[float, int]] | None, optional
        Optional list of ``(phase_radians, sample_index)`` tuples that introduce
        mid-waveform phase jumps during modulation.  Defaults to ``[]`` (no phase
        jumps).  This parameter is rarely needed; most waveforms should omit it.
    """

    def __init__(
        self,
        fname: str | Path,
        modulated: bool | None = None,
        mod_frequency: float = 0.0,
        phases: list[tuple[float, int]] | None = None,
    ):
        if isinstance(fname, str):
            fname = Path(fname)
        self.__fname: Path = fname
        self.__mod_frequency = mod_frequency
        self.__phases = sorted(phases, key=lambda x: x[1]) if phases else []

        # Infer modulated flag when not explicitly provided
        if modulated is None:
            self.__modulated = mod_frequency != 0.0
            print(
                f"WARNING: Modulated flag not provided for waveform '{fname}'; inferred as {self.__modulated} based on mod_frequency."
            )
        else:
            self.__modulated = modulated

        if self.__modulated and self.__mod_frequency == 0.0:
            raise ValueError(
                "Waveform is marked as modulated but mod_frequency is 0.  "
                "Either set modulated=False or provide a non-zero mod_frequency."
            )

        self.data = self.__load_data()

    def __load_data(self) -> list[float]:
        """Load waveform data from a CSV file.

        Supported layouts:
        * **Single-row CSV** - one row with many comma-separated float values.
        * **Single-column CSV** - many rows, each containing a single float value.

        If the file contains multiple rows *and* multiple columns the format is
        ambiguous and a ``ValueError`` is raised.
        """
        with self.__fname.open() as csvfile:
            reader = csv.reader(csvfile, delimiter=",")
            rows: list[list[str]] = [row for row in reader if row]  # skip blank lines

        if not rows:
            raise ValueError(f"Waveform file {self.__fname} is empty or invalid.")

        n_rows = len(rows)
        max_cols = max(len(r) for r in rows)

        # Detect and validate CSV layout
        if n_rows == 1 and max_cols > 1:
            # Single-row, many-columns
            data = list(map(float, rows[0]))
            logger.info("Loaded single-row CSV (%d samples): %s", len(data), self.__fname)
        elif max_cols == 1 and n_rows > 1:
            # Single-column, many-rows
            data = [float(r[0]) for r in rows]
            logger.info("Loaded single-column CSV (%d samples): %s", len(data), self.__fname)
        elif n_rows == 1 and max_cols == 1:
            # Single value
            data = [float(rows[0][0])]
            logger.info("Loaded single-value CSV (1 sample): %s", self.__fname)
        else:
            raise ValueError(
                f"Ambiguous CSV format in {self.__fname}: the file has {n_rows} rows "
                f"and up to {max_cols} columns.  Waveform CSV files must be either a "
                f"single row of comma-separated values OR a single column with one "
                f"value per row."
            )

        if len(data) == 0:
            raise ValueError(f"Waveform file {self.__fname} is empty or invalid.")

        return data

    def get(self, sample_rate: float | None = None) -> list[float]:
        """Return the waveform data, with sinusoidal modulation applied if enabled.

        Parameters
        ----------
        sample_rate : float or None
            The AWG sample rate in samples per second.  Required when
            ``self.modulated`` is ``True`` (needed to compute the modulation
            time-step).  May be omitted for unmodulated waveforms.

        Returns
        -------
        list[float]
            A copy of the envelope data, optionally multiplied by a sine
            carrier at ``self.mod_frequency``.
        """
        if not self.__modulated:
            if sample_rate is not None:
                logger.warning(
                    "Sample rate provided to get() but modulation is disabled for this waveform.  Sample rate will be ignored."
                )
            return list(self.data)

        if sample_rate is None:
            raise ValueError(
                "sample_rate is required for modulated waveforms.  "
                "Either pass a sample_rate or set modulated=False."
            )

        t_step = 2 * np.pi / sample_rate
        phi = 0.0
        phases = list(self.__phases)  # work on a copy
        next_phi, next_i_flip = (None, None) if not phases else phases.pop(0)

        mod_data = list(self.data)
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
        marker_positions=None,
        marker_levels=(0, 1),
        marker_width=50,
        n_pad_right=0,
        n_pad_left=0,
    ) -> list[int]:
        """
        Returns a marker waveform.

        Pads with zeros on both sides, and marks selected positions with high levels.
        """
        if marker_positions is None:
            marker_positions = []
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
        return len(self.data) / sample_rate

    def set_mod_frequency(self, value: float):
        """Sets the modulation frequency."""
        self.__mod_frequency = value

    # --- Properties ---

    @property
    def fname(self) -> Path:
        return self.__fname

    @fname.setter
    def fname(self, value: str | Path):
        if isinstance(value, str):
            value = Path(value)
        self.__fname = value
        self.data = self.__load_data()

    @property
    def modulated(self) -> bool:
        """Whether sinusoidal modulation is applied when :meth:`get` is called."""
        return self.__modulated

    @modulated.setter
    def modulated(self, value: bool):
        self.__modulated = value

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
        self.__phases = sorted(value, key=lambda x: x[1]) if value else []


class AwgConfiguration:
    """
    Configuration for an Arbitrary Waveform Generator (AWG), including sample rate,
    output channels, timing lags, marker widths, and calibration locations.
    It also includes the waveform sequence and associated waveforms that the AWG will
    play.

    Can be read from a filepath using the AwgConfigReader class in config_readers.py.

    Structure of the AWG configuration file:
    waveform_sequence: A list of lists. Each inner list corresponds to a channel and
        contains the indices of the waveforms to play on that channel.
    waveforms: A dictionary mapping waveform indices to Waveform objects
    sample_rate: Sample rate for the AWG output in samples per second.
    burst_count: Number of times to repeat the waveform sequence in a single trigger.
    waveform_output_channels: Channels on the AWG that will be used for outputting waveforms.
    waveform_output_channel_lags: Timing lags for each output channel to synchronize them.
    marker_width_samps: Width of the marker pulse in samples.

    marked channels: DEPRECATED
    waveform stitch delays: DEPRECATED
    interleave waveforms: DEPRECATED

    waveforms:
    A list of waveform configurations, each containing:
        filename (required): Path to the CSV file containing the waveform envelope.
            The CSV may be either a single row of comma-separated values or a single
            column with one value per row.
        modulated (optional): Boolean indicating whether sinusoidal modulation should
            be applied.  If omitted, inferred as True when a non-zero modulation
            frequency is present, False otherwise.
        modulation frequency (optional): The carrier frequency in Hz for the waveform.
            Defaults to 0.0 if omitted.
        phases (optional): Mid-waveform phase-jump specification.  Rarely needed;
            defaults to empty.

    """

    def __init__(
        self,
        waveform_sequence: list[list[int]],
        waveforms: dict[int, Waveform],
        sample_rate: float,
        burst_count: int,
        waveform_output_channels: tuple[int, ...],
        marker_width_samps: int | None,
        waveform_output_channel_lags: tuple[float, ...] | None = None,
        waveform_stitch_delays: tuple[tuple[Any, ...], ...] | None = None,
        interleave_waveforms: bool | None = None,
        marked_channels: tuple[int, ...] | None = None,
    ):

        self._waveform_sequence = waveform_sequence
        self.waveforms = waveforms

        self._sample_rate = sample_rate
        self._burst_count = burst_count
        self._waveform_output_channels = waveform_output_channels

        if waveform_output_channel_lags is None:
            waveform_output_channel_lags = tuple(0.0 for _ in waveform_output_channels)
        else:
            self.waveform_output_channel_lags = waveform_output_channel_lags

        if marker_width_samps is None or self._verify_marker_width(marker_width_samps):
            self.marker_width_samps = marker_width_samps
        else:
            raise ValueError(
                f"Marker width in samples must be even and greater than zero, got {marker_width_samps}"
            )

        if waveform_stitch_delays is not None:
            warnings.warn(
                "waveform_stitch_delays is deprecated and will be ignored.",
                category=DeprecationWarning,
                stacklevel=1,
            )
        if interleave_waveforms is not None:
            warnings.warn(
                "interleave_waveforms is deprecated and will be ignored.",
                category=DeprecationWarning,
                stacklevel=1,
            )
        if marked_channels is not None:
            warnings.warn(
                "marked_channels is deprecated and will be ignored.",
                category=DeprecationWarning,
                stacklevel=1,
            )

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

    @staticmethod
    def _verify_marker_width(marker_width_samps: int) -> bool:
        """Ensures the marker width in samples is valid (even and greater than zero)."""
        return marker_width_samps > 0 and marker_width_samps % 2 == 0

    def get_total_time(self) -> float:
        """Calculates the total time of all waveforms in the sequence on the longest channel."""
        channel_times = np.zeros(len(self.waveform_output_channels))
        for i, channel in enumerate(self.waveform_output_channels):
            channel_waveforms = [self.waveforms[idx] for idx in self.waveform_sequence[channel]]
            channel_time = sum(wf.get_t_length(self.sample_rate) for wf in channel_waveforms)
            channel_times[i] = channel_time
        return max(channel_times) if channel_times else 0.0


class ScopeConfiguration:
    """
    Configuration for an oscilloscope used in data acquisition.

    Can be read from a standalone ``.ini`` file using ``ScopeConfigReader`` in
    ``config_readers.py``.

    Attributes
    ----------
    trigger_channel : int
        The oscilloscope channel used as the trigger source.
    trigger_level : float
        The trigger level in volts.
    sample_rate : float
        The sample rate in samples per second.
    time_range : tuple[float, float]
        The time range for data capture as ``(start, end)`` in seconds.
    data_channels : dict[int, dict]
        A mapping from channel number to a dict with keys ``"range"``
        (tuple of floats), ``"impedance"`` (str), and ``"coupling"`` (str).
    """

    def __init__(
        self,
        trigger_channel: int,
        trigger_level: float,
        sample_rate: float,
        time_range: tuple[float, float],
        data_channels: dict[int, dict],
    ):
        self.trigger_channel = trigger_channel
        self.trigger_level = trigger_level
        self.sample_rate = sample_rate
        self.time_range = time_range
        self.data_channels = data_channels

    def __repr__(self) -> str:
        return (
            f"ScopeConfiguration(trigger_channel={self.trigger_channel}, "
            f"trigger_level={self.trigger_level}, sample_rate={self.sample_rate}, "
            f"time_range={self.time_range}, data_channels={self.data_channels})"
        )


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


class MotFluoresceConfiguration(GenericConfiguration):
    """
    Configuration for a MOT fluorescence experiment. More details can be found in the MotFluoresceExperiment class.

    The data used to configure the experiment should be loaded from a configuration file with (currently) the
    "ExperimentConfigReader" class and the get_mot_fluoresce_config method. This class must be passed to the
    MotFluoresceExperiment class to run the experiment.

    inputs:
     - save_location: The location to save the data collected in the experiment
     - mot_reload: The time in milliseconds to wait for the MOT to reload
     - iterations: The number of times to repeat the experiment
     - scope_config: ScopeConfiguration object (or None if scope is not used)
     - awg_config: AwgConfiguration object (or None if AWG is not used)
     - awg_config_path: Path to the AWG config file (for reference)
     - cam_dict: Dictionary containing camera configuration parameters (if camera is used)
     - sequence_config_path: Path to the sequence config file (if applicable)
    """

    def __init__(
        self,
        save_location,
        mot_reload,
        iterations,
        scope_config: ScopeConfiguration | None = None,
        awg_config: AwgConfiguration | None = None,
        awg_config_path: str | None = None,
        cam_dict: dict | None = None,
        sequence_config_path: str | None = None,
        background_mode: bool = False,
        background_iterations: int | None = None,
        repump_channel: int | None = None,
    ):
        super().__init__(save_location, mot_reload, iterations)

        self.scope_config = scope_config
        self.awg_config = awg_config
        self.awg_config_path = awg_config_path
        self.sequence_config_path = sequence_config_path
        self.background_mode = background_mode
        self.background_iterations = background_iterations

        if repump_channel is not None:
            self.repump_channel = repump_channel
        else:
            self.repump_channel = 20  # default channel for MOT repumping

        self.use_scope = scope_config is not None
        self.use_awg = awg_config is not None
        self.use_cam = cam_dict is not None

        if self.use_cam:
            cam_dict = cast(dict, cam_dict)
            self.cam_exposure = cam_dict["cam_exposure"]
            self.cam_gain = cam_dict["cam_gain"]
            self.camera_trigger_channel = cam_dict["camera_trig_ch"]
            self.camera_trigger_level = cam_dict["camera_trig_levs"]
            self.camera_pulse_width = cam_dict["camera_pulse_width"]
            self.save_images = cam_dict["save_images"]
        else:
            print("No camera will be used.")

        if not self.use_scope:
            print("No scope will be used.")

        if not self.use_awg:
            print("No AWG will be used.")

    # ------------------------------------------------------------------
    # Backward-compatible property aliases for scope settings.
    # Consumers (e.g. MotFluoresceExperiment) that read
    # ``config.scope_trigger_channel`` etc. continue to work.
    # ------------------------------------------------------------------

    @property
    def scope_trigger_channel(self) -> int:
        return cast(ScopeConfiguration, self.scope_config).trigger_channel

    @property
    def scope_trigger_level(self) -> float:
        return cast(ScopeConfiguration, self.scope_config).trigger_level

    @property
    def scope_sample_rate(self) -> float:
        return cast(ScopeConfiguration, self.scope_config).sample_rate

    @property
    def scope_time_range(self) -> tuple[float, float]:
        return cast(ScopeConfiguration, self.scope_config).time_range

    @property
    def scope_data_channels(self) -> dict[int, dict]:
        return cast(ScopeConfiguration, self.scope_config).data_channels


class MotFluoresceConfigurationSweep:
    def __init__(
        self,
        base_config: MotFluoresceConfiguration,
        base_sequence: DaqSequence,
        sweep_type: str,
        num_shots: int,
        sweep_params: dict[Any, Any],
    ):

        self.base_config = base_config
        self.base_sequence = base_sequence
        self.sweep_type = sweep_type
        self.sweep_params = sweep_params
        # print(self.sweep_params)
        self.num_shots = num_shots

        now = datetime.now()
        self.current_date = now.strftime("%Y-%m-%d")
        self.current_time = now.strftime("%H-%M-%S")
        print(f"[DEBUG] date: {self.current_date}")
        print(f"[DEBUG] time: {self.current_time}")

        self.configs: list[MotFluoresceConfiguration] = []
        self.sequences: list[DaqSequence] = []
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
            raise ValueError("Sweep type not supported")

        assert len(self.configs) == len(self.sequences), (
            "configs and sequences must have the same length"
        )

    @classmethod
    def from_config_reader(
        cls,
        experiment_config: MotFluoresceConfiguration,
        sequence: DaqSequence,
        sweep_type: str,
        num_shots: int,
        sweep_params: dict[Any, Any],
    ) -> MotFluoresceConfigurationSweep:
        """Alternative constructor that accepts pre-built typed config objects.

        This is the preferred way to create a sweep config when using the new
        self-contained sweep config file format.  The ``ExperimentConfigReader``
        builds all objects and passes them here.
        """
        return cls(
            base_config=experiment_config,
            base_sequence=sequence,
            sweep_type=sweep_type,
            num_shots=num_shots,
            sweep_params=sweep_params,
        )

    def __iter__(self):
        """
        When iterating over the object it returns a tuple containing a MOTFluoresceConfiguration
        object and the associated Sequence object. These can then be used to run a single shot
        of the sweep.
        """
        return iter(zip(self.configs, self.sequences, strict=True))

    def __len__(self):
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
        temp_root = Path("temp")
        if temp_root.exists():
            shutil.rmtree(temp_root)
        temp_root.mkdir(exist_ok=True)

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

                        if not Path(pulse_path).exists():
                            Path(pulse_path).parent.mkdir(parents=True, exist_ok=True)
                            calib_path = (
                                Path(calibs[j]) / f"{freqs[j] / 1e6:.0f}MHz" / "rabi_data.csv"
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
                    base_config=cast(AwgConfiguration, new_config.awg_config),
                    waveform_csvs={idx: new_paths[idx] for idx in wave_idxs},
                    mod_freqs={idx: freqs[j] for j, idx in enumerate(wave_idxs)},
                )

                # Update the new config with modified sequence
                new_config.awg_config = modified_sequence_config

                new_config.save_location = str(
                    Path(self.base_config.save_location)
                    / self.current_date
                    / self.current_time
                    / sweep_title
                    / f"shot{shot:03d}"
                )

                if not Path(self.base_config.save_location).exists():
                    raise FileNotFoundError(
                        f"Base save location does not exist: {self.base_config.save_location}"
                    )
                # Ensure the directory exists
                save_dir = Path(new_config.save_location).parent
                save_dir.mkdir(parents=True, exist_ok=True)

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
                new_config.save_location = str(
                    Path(self.base_config.save_location)
                    / self.current_date
                    / self.current_time
                    / file_text.rstrip("_")
                    / f"shot{i}"
                )

                # Modifies the sequence
                freq_ch = 2  # These values shouldn't be hardcoded
                power_ch = 6
                new_sequence.update_channel(
                    freq_ch,
                    [
                        (0, freq),
                    ],
                    [
                        0,
                    ],
                )
                tv_pairs = list(new_sequence.get_tv_pairs(power_ch))
                print(f"The old tv pairs for the imaging channel are: {tv_pairs}")
                # HACK to change the correct power value and pulse length
                # img_start_tv = tv_pairs[2]  # This is a tuple representing a time voltage pair
                img_end_tv = tv_pairs[3]
                new_start_tv = (time, power)
                new_end_tv = (time + length, img_end_tv[1])
                tv_pairs[2] = new_start_tv
                tv_pairs[3] = new_end_tv
                print(f"The new tv pairs for the imaging channel are: {tv_pairs}")
                new_vint_styles = new_sequence.get_v_interval_styles(power_ch)
                new_sequence.update_channel(power_ch, tv_pairs, new_vint_styles)

                # Ensure directory exists
                if not Path(self.base_config.save_location).exists():
                    raise FileNotFoundError(
                        f"Base save location does not exist: {self.base_config.save_location}"
                    )
                save_dir = Path(new_config.save_location).parent
                save_dir.mkdir(parents=True, exist_ok=True)

                # Append sequence and config files to the list
                self.configs.append(new_config)
                self.sequences.append(new_sequence)

    @staticmethod
    def modify_awg_sequence_config(
        *, base_config: AwgConfiguration, waveform_csvs: dict[int, str], mod_freqs: dict[int, float]
    ) -> AwgConfiguration:
        new_config = deepcopy(base_config)

        for idx, wf in new_config.waveforms.items():
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
        self.waveforms: dict[int, Waveform] = waveforms
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
    SingleExperimentConfig defines the configuration for a single automated experiment run.
    Previously called AutomatedExperimentConfiguration.

    This includes:
    - Static DAQ channel values
    - The filename and contents of the experiment sequence
    - The number of times to repeat the experiment
    - The MOT (Magneto-Optical Trap) reload time
    - Frequencies used for modulation during the experiment

    Intended to be used as part of a larger experiment session, or independently for individual runs.
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
