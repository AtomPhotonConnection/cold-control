"""
Created on 22 Apr 2016

@author: Tom Barrett, Jan Ole Ernst
"""

from __future__ import annotations

import ast
import functools
import logging
import operator
import os
import re
import time
import warnings
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import numpy as np
from configobj import ConfigObj

logger = logging.getLogger(__name__)

from classes.daq import (  # noqa: E402
    INPUT_LINE,
    OUTPUT_LINE,
    Channel_P1A,
    Channel_P1B,
    Channel_P1C,
    Channel_P1CH,
    Channel_P1CL,
    DAQCard,
    DAQChannel,
    DAQController,
    DAQDio,
)
from classes.daq_sequence import DaqSequence  # noqa: E402
from classes.experimental_configs import (  # noqa: E402
    AbsorbtionImagingConfiguration,
    AwgConfiguration,
    ExperimentSessionConfig,
    MotFluoresceConfiguration,
    MotFluoresceConfigurationSweep,
    MotFluorescenceAlignmentConfiguration,
    PhotonProductionConfiguration,
    ScopeConfiguration,
    SingleExperimentConfig,
    TdcConfiguration,
    Waveform,
)

GLOB_TRUE_BOOL_STRINGS = ["true", "t", "yes", "y"]


def get_config_root() -> str:
    """Return the directory used as the base for resolving relative config paths.
    Uses environment variable COLD_CONTROL_CONFIG_ROOT if set, otherwise Path.cwd()."""
    return os.environ.get("COLD_CONTROL_CONFIG_ROOT", str(Path.cwd()))


def resolve_config_path(path: str, base: str | None = None) -> str:
    """Resolve a config path. If path is relative, join with base (default get_config_root())."""
    if path is None or path == "":
        return path
    path = str(path).strip()
    if base is None:
        base = get_config_root()
    if Path(path).is_absolute():
        return str(Path(path).resolve())
    return str((Path(base) / path).resolve())


def to_bool(string):
    return string.lower() in GLOB_TRUE_BOOL_STRINGS


def to_int_list(arg):
    if arg is None:
        return None
    else:
        return list(map(int, arg))


def to_float_tuple(arg):
    return tuple(to_float_list(arg))


def to_int_tuple(arg):
    return tuple(map(int, arg))


def to_float_list(arg):
    if isinstance(arg, str):
        warnings.warn(
            "to_float_list received a string input. This may lead to unexpected behavior.",
            stacklevel=2,
        )
        return [float(arg)]
    return list(map(float, arg))


class ConfigReader:
    def __init__(self, fname):
        self.fname = fname
        self.config = ConfigObj(fname)
        fpath = Path(fname)
        self._config_dir = str(fpath.resolve().parent)

    def _resolve(self, path):
        if path is None or path == "":
            return path
        return resolve_config_path(path.strip(), get_config_root())

    def get_sequence_fname(self):
        """Return the sequence filename from rootConfig.

        .. deprecated::
            The sequence path should now be specified in the experiment config
            file via the ``sequence_config`` key.  This method will be removed
            in a future release.
        """
        warnings.warn(
            "ConfigReader.get_sequence_fname() is deprecated; the sequence path "
            "should now come from the experiment config file via 'sequence_config'.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._resolve(self.config["sequence_filename"])

    def get_daq_config_fname(self):
        return self._resolve(self.config["daq_config_filename"])

    def get_absorbtion_imaging_config_fname(self):
        return self._resolve(self.config["absorbtion_images_config_filename"])

    def get_experiment_config_fname(self):
        """Preferred: returns experiment config path (experiment_config_filename with fallback to photon_production_config_filename)."""
        path = self.config.get("experiment_config_filename") or self.config.get(
            "photon_production_config_filename"
        )
        if path is None:
            raise KeyError(
                "Neither 'experiment_config_filename' nor 'photon_production_config_filename' found in root config."
            )
        if (
            "photon_production_config_filename" in self.config
            and "experiment_config_filename" not in self.config
        ):
            warnings.warn(
                "photon_production_config_filename is deprecated; use experiment_config_filename in root config.",
                DeprecationWarning,
                stacklevel=2,
            )
        return self._resolve(path)

    def get_photon_production_config_fname(self):
        """Returns experiment config path. Prefer get_experiment_config_fname(). Backward compatible: reads experiment_config_filename or photon_production_config_filename."""
        return self.get_experiment_config_fname()

    def is_development_mode(self):
        logger.debug("Config keys: %s", self.config.keys())
        return self.config.as_bool("development_mode")


class ConfigWriter:
    def __init__(self, fname):
        self.fname = fname
        self.config = ConfigObj(fname)

    def save(
        self,
        sequence_fname,
        daq_config_fname,
        absorbtion_imaging_config_fname,
        photon_production_config_fname,
    ):

        self.config["date"] = time.strftime("%d/%m/%y")
        self.config["time"] = time.strftime("%H:%M:%S")

        self.config["sequence_filename"] = sequence_fname
        self.config["daq_config_filename"] = daq_config_fname
        self.config["absorbtion_images_config_filename"] = absorbtion_imaging_config_fname
        self.config["photon_production_config_filename"] = photon_production_config_fname
        self.config["experiment_config_filename"] = photon_production_config_fname

        self.config.write()


class MyConfig:
    """
    Simple wrapper around ConfigObj to provide dictionary-like access and additional methods.
    """

    def __init__(self, fname: str):
        self._cfg = ConfigObj(fname)

    def __getitem__(self, key: str) -> Any:
        return self._cfg[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._cfg[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._cfg.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self._cfg

    @property
    def filename(self) -> str:
        if self._cfg.filename is None:
            raise ValueError("Config filename is None.")
        return self._cfg.filename

    def write(self) -> None:
        self._cfg.write()


class DaqReader:
    def __init__(self, fname):
        self.fname = fname
        self.config: dict[str, Any] = ConfigObj(fname)

    def _load_channels(self) -> list:
        """Parse DAQ channel definitions from the config file."""
        channels = []
        for _, v in self.config["DAQ channels"].items():
            channel_args: tuple[int, str, tuple[float, float], float, bool, str] = (
                int(v["chNum"]),  # chNum (int)
                str(v["chName"]),  # chName (str)
                (float(v["chLimits"][0]), float(v["chLimits"][1])),  # chLimits (tuple[float,float])
                float(v["default value"]),  # default value (float)
                bool(v["UIvisible"]),  # UIvisible (bool) or use v['UIvisible'] if already bool
                str(v["calibrationFname"]),  # calibrationFname (str)
            )
            channels.append(DAQChannel(*channel_args))
        return channels

    def _load_dios(self) -> list:
        """Parse DIO definitions from the config file."""
        dios = []
        for _, v in self.config["DIOs"].items():
            dio_name = str(v["dioName"])
            dio_num = int(v["dioNum"])

            if v["port"].upper() in [Channel_P1A, "A"]:
                port = Channel_P1A
            elif v["port"].upper() in [Channel_P1B, "B"]:
                port = Channel_P1B
            elif v["port"].upper() in [Channel_P1C, "C"]:
                port = Channel_P1C
            elif v["port"].upper() in [Channel_P1CL, "CL"]:
                port = Channel_P1CL
            elif v["port"].upper() in [Channel_P1CH, "CH"]:
                port = Channel_P1CH
            else:
                port = int(v["port"])

            line = int(v["line"])

            if v["direction"].lower() in ("out", "output", "o"):
                direction = OUTPUT_LINE
            elif v["direction"].lower() in ("in", "input", "i"):
                direction = INPUT_LINE
            else:
                direction = int(v["direction"])

            if v["enabled state"].lower() in ["high", "5", "5v", "1"]:
                enabled_state = 1
            elif v["enabled state"].lower() in ["low", "0", "0v"]:
                enabled_state = 0
            else:
                enabled_state = int(v["enabled state"])

            dios.append(DAQDio(dio_name, dio_num, port, line, direction, enabled_state))
        return dios

    def load_daq_controller(self) -> DAQController:
        """Returns a DAQ controller object as configured in the config file."""

        channels = self._load_channels()
        dios = self._load_dios()

        daq_master = DAQCard(
            card_number=int(self.config["DAQ cards"]["master"]["card number"]),
            channels=[
                next(ch for ch in channels if ch.chNum == int(x))
                for x in self.config["DAQ cards"]["master"]["channels"]
            ],
            dios=[
                x
                for x in [
                    next((dio for dio in dios if dio.dio_num == int(x)), None)
                    for x in self.config["DAQ cards"]["master"]["dios"]
                ]
                if x is not None
            ],
        )
        daq_slaves: list[DAQCard] = []

        for _, v in self.config["DAQ cards"]["slaves"].items():
            try:
                daq_slaves.append(
                    DAQCard(
                        card_number=int(v["card number"]),
                        channels=[
                            next(ch for ch in channels if ch.chNum == int(x)) for x in v["channels"]
                        ],
                        dios=[
                            x
                            for x in [
                                next((dio for dio in dios if dio.dio_num == int(x)), None)
                                for x in v["dios"]
                            ]
                            if x is not None
                        ],
                    )
                )
            except StopIteration as err:
                logger.error(
                    "It looks like one of the DAQ cards has a channel expected that does not exist"
                )
                logger.error([ch.chNum for ch in channels])
                raise err

        return DAQController(daq_master, daq_slaves)

    def load_dummy_daq_controller(self):
        """Create a DummyDAQController with channels and DIOs parsed from the config file.

        This avoids any hardware interaction while retaining the real
        channel definitions (names, limits, calibrations, DIOs).
        """
        from instruments.dummy import DummyDAQController

        channels = self._load_channels()
        dios = self._load_dios()
        return DummyDAQController(channels=channels, dios=dios)


class DaqWriter:
    def __init__(self, fname):
        self.fname = fname
        self.config = ConfigObj(fname)

    def save(self, master, *slaves):

        daq_cards = {}

        daq_cards["master"] = {
            "card number": master.card,
            "channels": [ch.chNum for ch in master.channels],
        }
        daq_cards["slaves"] = {}
        for idx, slave in enumerate(slaves, start=1):
            daq_cards["slaves"][str(idx)] = {
                "card number": slave.card,
                "channels": [ch.chNum for ch in slave.channels],
            }

        self.config["DAQ cards"] = daq_cards

        daq_channels = {}

        # Note sum(x,[]) is a cheeky way to flatten a list of lists (x).
        for i, ch in enumerate(
            functools.reduce(operator.iadd, [card.channels for card in [master, *list(slaves)]], [])
        ):
            daq_channels[str(i)] = {
                "chNum": ch.chNum,
                "chName": ch.chName,
                "chLimits": ch.chLimits,
                "default value": ch.defaultValue,
                "UIvisible": ch.isUIVisable,
                "calibrationFname": ch.calibrationFname if ch.isCalibrated else "",
            }

        self.config["DAQ channels"] = daq_channels

        self.config.write()


class SequenceReader:
    def __init__(self, fname):
        self.fname = fname
        self.config = MyConfig(self.fname)

    def load_sequence(self):
        seq = DaqSequence(*self.get_sequence_init_args())
        sequence_channels: dict[str, Any] = {}
        sequence_channels = self.config["sequence channels"]

        for _, v in sequence_channels.items():
            ch = int(v["chNum"])
            tv_pairs = [tuple(ast.literal_eval(x)) for x in v["tV_pairs"]]
            v_interval_styles = [int(x) for x in v["V_interval_styles"]]

            seq.add_channel_seq(ch, tv_pairs, v_interval_styles)

        return seq

    def get_sequence_init_args(self):
        return int(self.config["sequence"]["n_samples"]), int(self.config["sequence"]["t_step"])

    def get_global_timings(self):
        return [ast.literal_eval(x) for x in self.config["sequence"]["global_timings"]]

    def get_name(self):
        return self.config.filename

    def get_time(self):
        return self.config["time"]

    def get_date(self):
        return self.config["date"]

    def get_channel_assignment_notes(self):
        return self.config["notes"]["config_ch_assignments"]

    def get_user_notes(self):
        return self.config["notes"]["user"]


class SequenceWriter:
    def __init__(self, fname):
        self.fname = fname
        self.config = MyConfig(fname)

    def save(self, sequence, sequence_channel_labels, global_timings, user_notes):

        self.config["date"] = time.strftime("%d/%m/%y")
        self.config["time"] = time.strftime("%H:%M:%S")

        self.config["notes"] = {}
        self.config["notes"]["user"] = user_notes
        self.config["notes"]["config_ch_assignments"] = [
            (k, v) for k, v in sequence_channel_labels.items()
        ]

        self.config["sequence"] = {
            "n_samples": sequence.n_samples,
            "t_step": sequence.t_step,
            "global_timings": global_timings,
        }

        self.config["sequence channels"] = {}

        for ch_num, ch in sequence.chSeqs.items():
            self.config["sequence channels"][str(ch_num)] = {
                "chNum": ch_num,
                "tV_pairs": ch.tV_pairs,
                "V_interval_styles": ch.V_interval_styles,
            }

        self.config.write()


class AwgConfigReader:
    """Reads a standalone AWG configuration file and produces an AwgConfiguration object.

    The config file is expected to have top-level keys for the AWG parameters and a
    ``[waveforms]`` section containing numbered sub-sections, each specifying a waveform's
    modulation frequency, phases and CSV filename.  See
    ``configs/pulse_shaping_expt/awg_configs/feb26_awg_updated.ini`` for an example.
    """

    def __init__(self, fname: str):
        self.fname = fname
        self.config = MyConfig(fname)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_awg_configuration(self) -> AwgConfiguration:
        """Parse the config file and return a fully-populated ``AwgConfiguration``."""
        waveforms: dict[int, Waveform] = self._parse_waveforms()
        output_channels = self._parse_output_channels(
            raw_channels=self.config["waveform output channels"]
        )

        cfg = self.config

        raw_seq = ast.literal_eval(self.config["waveform sequence"])
        waveform_sequence = list(list(ch) for ch in raw_seq)

        awg_config = AwgConfiguration(
            waveform_sequence=waveform_sequence,
            waveforms=waveforms,
            sample_rate=float(cfg["sample rate"]),
            burst_count=int(cfg["burst count"]),
            waveform_output_channels=tuple(output_channels),
            waveform_output_channel_lags=self._extract_lags(cfg),
            marker_width_samps=self._extract_marker_width(cfg),
            waveform_stitch_delays=tuple(
                tuple(x) if isinstance(x, list) else (x,)
                for x in ast.literal_eval(self.config["waveform stitch delays"])
            )
            if "waveform stitch delays" in self.config
            else None,
            interleave_waveforms=to_bool(self.config["interleave waveforms"])
            if "interleave waveforms" in self.config
            else None,
            marked_channels=tuple(self.config["marked channels"])
            if "marked channels" in self.config
            else None,
        )
        return awg_config

    # Convenience alias matching the SequenceReader.load_sequence() pattern
    get_awg_config = load_awg_configuration

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_waveforms(self) -> dict[int, Waveform]:
        """Read the ``[waveforms]`` section and return a dict of ``Waveform`` objects.

        Each waveform sub-section supports the following keys:

        ``filename`` (required)
            Path to a CSV file containing the waveform envelope.
        ``modulated`` (optional)
            Boolean indicating whether sinusoidal modulation should be applied.
            If omitted, inferred as ``True`` when a non-zero ``modulation frequency``
            is present, ``False`` otherwise.
        ``modulation frequency`` (optional)
            Carrier frequency in Hz.  Defaults to ``0.0``.
        ``phases`` (optional)
            Mid-waveform phase-jump specification.  Defaults to ``[]``.
        """
        waveforms: dict[int, Waveform] = {}
        for idx, wform in self.config["waveforms"].items():
            phases = self._parse_phases(wform.get("phases"))
            fname = resolve_config_path(wform["filename"])

            # Parse modulation frequency (optional, defaults to 0.0)
            mod_frequency = (
                float(wform["modulation frequency"]) if "modulation frequency" in wform else 0.0
            )

            # Parse modulated flag (optional, inferred from mod_frequency if absent)
            modulated = to_bool(wform["modulated"]) if "modulated" in wform else None

            waveforms[int(idx)] = Waveform(
                fname=fname,
                modulated=modulated,
                mod_frequency=mod_frequency,
                phases=phases,
            )
        return waveforms

    @staticmethod
    def _parse_phases(raw_phases) -> list[tuple[float, int]]:
        """Convert the raw phases value from the config into a list of (phase, index) tuples.

        Handles:
        - ``None`` / empty string / list of empty strings  -> ``[]`` with warning
        - A list of numeric strings -> ``[(float, index), ...]``
        - A string like ``"(0.0, 0) (1.57, 100)"`` -> parsed accordingly
        """
        if raw_phases is None:
            return []

        # ConfigObj may return a list of strings (e.g. ['', ''] for "phases = ,")
        if isinstance(raw_phases, list):
            stripped = [s.strip() for s in raw_phases if s.strip()]
            if not stripped:
                return []
            # Check if this looks like tuple strings "(phase, index)"
            joined = " ".join(stripped)
            if "(" in joined:
                joined = re.sub(r"\(([^)]+) ([^)]+)\)", r"(\1, \2)", joined)
                joined = joined.replace(") (", "), (")
                return list(ast.literal_eval(joined))
            # Otherwise treat as simple float list -> (float, index)
            return [(float(p), i) for i, p in enumerate(stripped)]

        # Single string value
        raw = str(raw_phases).strip()
        if not raw:
            return []
        if "(" in raw:
            raw = re.sub(r"\(([^)]+) ([^)]+)\)", r"(\1, \2)", raw)
            raw = raw.replace(") (", "), (")
            return list(ast.literal_eval(raw))
        return [(float(raw), 0)]

    @staticmethod
    def _parse_output_channels(raw_channels: Iterable[Any]) -> tuple[int, ...]:
        """
        Pure function to map a sequence of channel strings to integer IDs.
        """
        return tuple(
            int(str(ch).replace(" ", "").lower().replace("channel", "")) for ch in raw_channels
        )

    @staticmethod
    def _extract_lags(cfg: MyConfig) -> tuple[float, ...]:
        if "waveform output channel lags" not in cfg:
            return tuple(0.0 for _ in cfg["waveform output channels"])
        else:
            return tuple(map(float, cfg["waveform output channel lags"]))

    @staticmethod
    def _extract_marker_width(cfg: MyConfig) -> int | None:
        if "marker width samples" in cfg:
            return int(cfg["marker width samples"])
        elif "marker width samps" in cfg:
            return int(cfg["marker width samps"])
        elif "marker width us" in cfg:
            marker_width_us = float(cfg["marker width"])
            sample_rate = float(cfg["sample rate"])
            # Round to nearest even integer, minimum 2 samples
            return max(2, round((marker_width_us * sample_rate / 1e6) / 2) * 2)
        elif "marker width" in cfg:
            warnings.warn(
                "Assuming marker width in microseconds; converting to samples."
                " To avoid this warning, specify marker width in samples using 'marker width samples'"
                " or 'marker width samps' in the config file.",
                UserWarning,
                stacklevel=2,
            )
            marker_width_us = float(cfg["marker width"])
            sample_rate = float(cfg["sample rate"])
            # Round to nearest even integer, minimum 2 samples
            return max(2, round((marker_width_us * sample_rate / 1e6) / 2) * 2)
        else:
            return None


class ScopeConfigReader:
    """Reads a standalone oscilloscope configuration file and produces a ``ScopeConfiguration``.

    The config file should have top-level keys for trigger settings and sub-sections
    ``[data_channels]``, ``[data_channel_impedance]`` and ``[data_channel_coupling]``.
    """

    def __init__(self, fname: str):
        self.fname = fname
        self.config = MyConfig(fname)

    def load_scope_configuration(self) -> ScopeConfiguration:
        """Parse the config file and return a ``ScopeConfiguration`` object."""
        return self._parse_scope_config(self.config)

    @staticmethod
    def _parse_scope_config(cfg) -> ScopeConfiguration:
        """Build a ``ScopeConfiguration`` from a config section or standalone config.

        This static method is also used internally by ``ExperimentConfigReader`` to
        parse inline ``[scope_settings]`` sections for backward compatibility.
        """
        data_chs: dict[int, dict] = {}
        impedance_section = cfg.get("data_channel_impedance", {})
        coupling_section = cfg.get("data_channel_coupling", {})
        for ch_idx, limits in cfg["data_channels"].items():
            if isinstance(limits, (list, tuple)):
                low, high = float(limits[0]), float(limits[1])
            else:
                parts = [x.strip() for x in str(limits).split(",")]
                low, high = float(parts[0]), float(parts[1])
            impedance = impedance_section.get(ch_idx, "high")
            if isinstance(impedance, list):
                impedance = impedance[0] if impedance else "high"
            impedance = str(impedance).strip().lower()
            coupling = coupling_section.get(ch_idx, "DC")
            if isinstance(coupling, list):
                coupling = coupling[0] if coupling else "DC"
            coupling = str(coupling).strip().upper()
            data_chs[int(ch_idx)] = {
                "range": (low, high),
                "impedance": impedance,
                "coupling": coupling,
            }
        return ScopeConfiguration(
            trigger_channel=int(cfg["trigger_channel"]),
            trigger_level=float(cfg["trigger_level"]),
            sample_rate=float(cfg["sample_rate"]),
            time_range=cast(tuple[float, float], to_float_tuple(cfg["time_range"])),
            data_channels=data_chs,
        )


class ExperimentConfigReader:
    """
    A class to read experimental config files. First the get_expt_type() method should be
    called to determine the type of experiment the config file is set up for. Then the
    relevant get_[expt_type]_configuration() method should be called which returns a
    GenericConfiguration object for the experiment type specified in the config file.
    The config file should contain:
     - an initial section without a heading containing general properties shared by all
     config files, such as the save location and the MOT reload time
     - sections containing the parameters for the experiment apparatus
     - a final metadata section containing the experiment type
    """

    def __init__(self, fname):
        self.fname = fname
        logger.info(f"Reading config file: {fname}")
        self.config = MyConfig(fname)
        metadata = self.config.get("metadata", {})
        config_type = metadata.get("config_type") if isinstance(metadata, dict) else None
        if config_type is not None and str(config_type).strip().lower() != "experiment":
            warnings.warn(
                f"Experiment config has config_type={config_type!r}; expected 'experiment' or leave unset.",
                UserWarning,
                stacklevel=2,
            )

    def _validate_experiment_config_structure(self):
        """Check required keys for MOT fluorescence experiment config. Only runs when metadata.config_type == 'experiment'."""
        required_top = [
            "save location",
            "mot reload",
            "iterations",
            "metadata",
        ]
        missing = [k for k in required_top if k not in self.config]
        if missing:
            raise ValueError(f"Experiment config missing required keys: {missing}")
        if "metadata" not in self.config or "experiment_type" not in self.config["metadata"]:
            raise ValueError("Experiment config [metadata] must contain experiment_type")

        # New format: top-level scope_config / awg_config keys
        has_new_scope = "scope_config" in self.config
        has_new_awg = "awg_config" in self.config

        # Old format: use_scope/use_awg booleans with inline sections
        has_old_scope = "use_scope" in self.config
        has_old_awg = "use_awg" in self.config

        if has_old_scope and not has_new_scope and to_bool(self.config["use_scope"]):
            scope = self.config.get("scope_settings")
            if not scope:
                raise ValueError("use_scope is True but [scope_settings] is missing")
            for k in [
                "trigger_channel",
                "trigger_level",
                "sample_rate",
                "time_range",
                "data_channels",
            ]:
                if k not in scope:
                    raise ValueError(f"[scope_settings] missing required key: {k}")
        if has_old_awg and not has_new_awg and to_bool(self.config["use_awg"]):
            awg = self.config.get("awg_settings")
            if not awg or "config_path" not in awg:
                raise ValueError("use_awg is True but [awg_settings] or config_path is missing")

    def get_expt_type(self):
        """
        Method to extract the experiment type from the config file
        """

        metadata = self.config.get("metadata", {})
        expt_type = metadata.get("experiment_type")
        if expt_type is None:
            logger.error(
                r"To fix this error you probably need to add a 'metadata' section to the config file. See configs\sequence\pulse_shaping_expt\photon_prod_config.ini"
            )
            raise KeyError("No experiment type specified in the config file.")

        return expt_type.lower()

    def get_photon_production_configuration(self):

        # Delegate AWG config parsing to AwgConfigReader
        awg_reader = AwgConfigReader(self.fname)
        awg_config = awg_reader.load_awg_configuration()

        tdc_config = TdcConfiguration(
            counter_channels=list(map(ast.literal_eval, self.config["TDC"]["counter channels"])),
            marker_channel=int(self.config["TDC"]["marker channel"]),
            timestamp_buffer_size=int(self.config["TDC"]["timestamp buffer size"]),
        )

        photon_production_config = PhotonProductionConfiguration(
            save_location=self.config["save location"],
            mot_reload=ast.literal_eval(self.config["mot reload"]),
            iterations=int(self.config["iterations"]),
            waveform_sequence=awg_config.waveform_sequence,
            waveforms=awg_config.waveforms,
            waveform_stitch_delays=None,  # deprecated, should be set to None and ignored by AWG control code
            interleave_waveforms=None,  # deprecated
            awg_configuration=awg_config,
            tdc_configuration=tdc_config,
        )

        return photon_production_config

    def get_mot_flourescence_configuration(self):
        """
        Method to extract the mot fluorescence configuration from the config file.

        Supports two formats:
        - **New format**: top-level ``scope_config``, ``awg_config``, ``sequence_config``
          keys pointing to standalone instrument config files.
        - **Old format**: ``use_scope``/``use_awg``/``use_cam`` booleans with inline
          ``[scope_settings]`` and ``[awg_settings]`` sections.  Emits
          ``DeprecationWarning`` when the old format is detected.
        """

        # --- Determine which instruments are used (new vs old format) ---
        has_new_scope = "scope_config" in self.config
        has_new_awg = "awg_config" in self.config

        # Camera detection: camera_settings section or use_cam boolean
        if "use_cam" in self.config:
            use_camera = to_bool(self.config["use_cam"])
        else:
            use_camera = "camera_settings" in self.config

        # --- Scope ---
        scope_config: ScopeConfiguration | None = None
        if has_new_scope:
            scope_path = resolve_config_path(self.config["scope_config"], get_config_root())
            scope_config = ScopeConfigReader(scope_path).load_scope_configuration()
        elif "use_scope" in self.config and to_bool(self.config["use_scope"]):
            warnings.warn(
                "Inline [scope_settings] is deprecated; use a standalone scope config file "
                "referenced by a top-level 'scope_config' key.",
                DeprecationWarning,
                stacklevel=2,
            )
            scope_section = self.config["scope_settings"]
            scope_config = ScopeConfigReader._parse_scope_config(scope_section)

        # --- AWG ---
        awg_config: AwgConfiguration | None = None
        awg_config_path: str | None = None
        if has_new_awg:
            awg_config_path = resolve_config_path(self.config["awg_config"], get_config_root())
            awg_reader = AwgConfigReader(awg_config_path)
            awg_config = awg_reader.load_awg_configuration()
        elif "use_awg" in self.config and to_bool(self.config["use_awg"]):
            warnings.warn(
                "Inline [awg_settings] with config_path is deprecated; use a top-level "
                "'awg_config' key pointing to the AWG config file.",
                DeprecationWarning,
                stacklevel=2,
            )
            awg_section = self.config["awg_settings"]
            awg_config_path = resolve_config_path(awg_section["config_path"], get_config_root())
            awg_reader = AwgConfigReader(awg_config_path)
            awg_config = awg_reader.load_awg_configuration()

        # --- Camera (unchanged — kept as dict for now) ---
        camera_settings_dict: dict | None = None
        if use_camera:
            camera = self.config["camera_settings"]
            camera_settings_dict = {
                "cam_exposure": int(camera["cam_exposure"]),
                "cam_gain": int(camera["cam_gain"]),
                "camera_trig_ch": int(camera["camera_trig_ch"]),
                "camera_trig_levs": to_float_tuple(camera["camera_trig_levs"]),
                "camera_pulse_width": float(camera["camera_pulse_width"]),
                "save_images": to_bool(camera["save_images"]),
            }

        # --- Sequence (new format only) ---
        sequence_config_path: str | None = None
        if "sequence_config" in self.config:
            sequence_config_path = resolve_config_path(
                self.config["sequence_config"], get_config_root()
            )

        # --- Validate if metadata says this is an experiment config ---
        metadata = self.config.get("metadata") or {}
        ct = metadata.get("config_type", "").strip().lower() if isinstance(metadata, dict) else ""
        if ct == "experiment":
            self._validate_experiment_config_structure()

        mot_fluoresce_config = MotFluoresceConfiguration(
            save_location=self.config["save location"],
            mot_reload=ast.literal_eval(self.config["mot reload"]),
            iterations=int(self.config["iterations"]),
            scope_config=scope_config,
            awg_config=awg_config,
            awg_config_path=awg_config_path,
            cam_dict=camera_settings_dict,
            sequence_config_path=sequence_config_path,
        )

        return mot_fluoresce_config

    def get_mot_flourescence_configuration_sweep(self) -> tuple[str, int, dict[str, Any]]:
        """
        Method to extract the MOT fluorescence configuration for sweep experiments.
        First determines the sweep type, and then does different things from there.
        Returns:
         - sweep_type (str): The type of sweep being performed, e.g. "awg_sequence" or "mot_imaging".
         - num_shots (int): The number of shots to take for the sweep.
         - sweep_dict (dict): A dictionary containing the parameters for the sweep.
        """

        def generate_int_list(section):
            start = float(self.config[section]["start"])
            stop = float(self.config[section]["stop"])
            step = float(self.config[section]["step"])

            if step == 0:
                return [round(start)]

            return list(np.round(np.arange(start, stop + step, step)).astype(int))

        def generate_float_list(section):
            start = float(self.config[section]["start"])
            stop = float(self.config[section]["stop"])
            num_points = int(self.config[section]["num_points"])

            if num_points == 1:
                return [start] if start == stop else []

            array = np.linspace(start, stop, num_points)
            return array.tolist()

        def ensure_list(value):
            if isinstance(value, list):
                return value
            elif value is None:
                return None
            else:
                return [value]

        sweep_type = self.config["sweep_type"]
        num_shots = int(self.config["num_shots"])

        if sweep_type == "awg_sequence":
            defaults = self.config["defaults"]
            wave_idxs = to_int_list(defaults.get("waveform_indices", None))
            rabi_freqs = to_float_list(defaults.get("rabi_frequencies", None))
            mod_freqs = to_float_list(defaults.get("modulation_frequencies", None))
            waveforms = ensure_list(defaults.get("waveforms", None))
            calib_paths = ensure_list(defaults.get("calibration_paths", None))

            all_sweeps = []
            for sweep_idx in self.config["sweeps"]:
                sweep = self.config["sweeps"][sweep_idx]
                sweep_changes = {"title": sweep["title"]}
                for key, value in sweep.items():
                    if key == "title":
                        continue
                    elif key == "rabi_frequencies" or key == "modulation_frequencies":
                        sweep_changes[key] = to_float_list(value)
                    elif key == "waveforms" or key == "calibration_paths":
                        sweep_changes[key] = ensure_list(value)
                    if wave_idxs is not None:
                        assert len(sweep_changes[key]) == len(wave_idxs), (
                            f"Length mismatch for {key} in sweep {sweep_idx}"
                        )

                all_sweeps.append(sweep_changes)

            sweep_dict = {
                "waveform_indices": wave_idxs,
                "rabi_frequencies": rabi_freqs,
                "modulation_frequencies": mod_freqs,
                "waveforms": waveforms,
                "calibration_paths": calib_paths,
                "sweeps": all_sweeps,
            }

            return sweep_type, num_shots, sweep_dict

        elif sweep_type == "mot_imaging":
            beam_powers = generate_float_list("beam_powers")
            beam_frequencies = generate_float_list("beam_frequencies")
            pulse_lengths = generate_int_list("pulse_lengths")
            pulse_times = generate_int_list("pulse_times")
            sweep_dict = {
                "beam_powers": beam_powers,
                "beam_frequencies": beam_frequencies,
                "pulse_lengths": pulse_lengths,
                "pulse_times": pulse_times,
            }
            return sweep_type, num_shots, sweep_dict

        else:
            raise ValueError(f"Unknown sweep type: {sweep_type}")

    def get_absorbtion_imaging_configuration(self):

        return AbsorbtionImagingConfiguration(
            scan_abs_img_freq=ast.literal_eval(self.config["scan_abs_img_freq"]),
            abs_img_freq_ch=int(self.config["abs_img_freq_ch"]),
            abs_img_freqs=to_float_list(self.config["abs_img_freqs"]),
            camera_trig_ch=int(self.config["camera_trig_ch"]),
            imag_power_ch=int(self.config["imag_power_ch"]),
            camera_trig_levs=to_float_tuple(self.config["camera_trig_levs"]),
            imag_power_levs=to_float_tuple(self.config["imag_power_levs"]),
            camera_pulse_width=float(self.config["camera_pulse_width"]),
            imag_pulse_width=float(self.config["imag_pulse_width"]),
            t_imgs=to_float_list(self.config["t_imgs"]),
            mot_reload=float(self.config["mot_reload_time"]),
            n_backgrounds=int(self.config["n_backgrounds"]),
            bkg_off_channels=to_int_list(self.config["bkg_off_channels"]),
            cam_gain=int(self.config["cam_gain"]),
            cam_exposure=int(self.config["cam_exposure"]),
            cam_gain_lims=to_int_tuple(self.config["cam_gain_lims"]),
            cam_exposure_lims=to_int_tuple(self.config["cam_exposure_lims"]),
            save_location=self.config["save_location"],
            save_raw_images=to_bool(self.config["save_raw_images"]),
            save_processed_images=to_bool(self.config["save_processed_images"]),
            review_processed_images=to_bool(self.config["review_processed_images"]),
        )

    def get_correct_config(self):
        """
        Method to extract the correct configuration object based on the experiment type
        specified in the config file.

        Returns the appropriate configuration object:
        - ``"mot fluorescence"`` → ``MotFluoresceConfiguration``
        - ``"mot fluorescence sweep"`` → ``MotFluoresceConfigurationSweep``
        - ``"mot fluorescence alignment"`` → ``MotFluorescenceAlignmentConfiguration``
        - ``"photon production"`` → ``PhotonProductionConfiguration``
        - ``"absorbtion imaging"`` → ``AbsorbtionImagingConfiguration``
        """

        expt_type = self.get_expt_type()

        if expt_type == "photon production":
            return self.get_photon_production_configuration()
        elif expt_type == "mot fluorescence":
            return self.get_mot_flourescence_configuration()
        elif expt_type == "mot fluorescence sweep":
            return self.get_full_sweep_configuration()
        elif expt_type == "mot fluorescence alignment":
            return self.get_mot_fluorescence_alignment_configuration()
        elif expt_type == "absorbtion imaging":
            return self.get_absorbtion_imaging_configuration()
        else:
            raise ValueError(f"Unknown experiment type: {expt_type}")

    def get_sequence(self) -> DaqSequence:
        """Load the sequence from the ``sequence_config`` path in this experiment config.

        Raises ``KeyError`` if the config file does not contain a ``sequence_config`` key.
        """
        if "sequence_config" not in self.config:
            raise KeyError(
                "Experiment config does not contain a 'sequence_config' key. "
                "The sequence must be specified in the experiment config file."
            )
        seq_path = resolve_config_path(self.config["sequence_config"], get_config_root())
        return SequenceReader(seq_path).load_sequence()

    def get_mot_fluorescence_alignment_configuration(self) -> MotFluorescenceAlignmentConfiguration:
        """Build a ``MotFluorescenceAlignmentConfiguration`` from the config file.

        The config file uses the same format as a standard MOT fluorescence
        experiment (with ``scope_config``, ``awg_config``, ``sequence_config``
        etc.) but sets ``experiment_type = "MOT Fluorescence Alignment"``.

        An optional top-level ``background_folder`` key specifies the path to
        a directory of background measurement data.  If present, the alignment
        loop will compute F_norm; otherwise it shows raw F_img.
        """
        base_config = self.get_mot_flourescence_configuration()
        sequence = self.get_sequence()

        background_folder: str | None = None
        if "background_folder" in self.config:
            background_folder = resolve_config_path(
                self.config["background_folder"], get_config_root()
            )

        return MotFluorescenceAlignmentConfiguration(
            base_config=base_config,
            base_sequence=sequence,
            background_folder=background_folder,
        )

    def get_full_sweep_configuration(self) -> MotFluoresceConfigurationSweep:
        """Build a complete ``MotFluoresceConfigurationSweep`` from a self-contained sweep config.

        The config file must contain all experiment parameters (same as MOT fluorescence)
        plus a ``[sweep]`` section with ``[[defaults]]`` and ``[[sweeps]]`` sub-sections,
        and ``sweep_type`` / ``num_shots`` at the top-level or inside ``[sweep]``.
        """
        # Build the base experiment config (reuses get_mot_flourescence_configuration)
        base_config = self.get_mot_flourescence_configuration()

        # Load the sequence from the experiment config
        sequence = self.get_sequence()

        # Parse sweep params (reuses existing logic from get_mot_flourescence_configuration_sweep)
        sweep_type, num_shots, sweep_params = self.get_mot_flourescence_configuration_sweep()

        return MotFluoresceConfigurationSweep.from_config_reader(
            experiment_config=base_config,
            sequence=sequence,
            sweep_type=sweep_type,
            num_shots=num_shots,
            sweep_params=sweep_params,
        )


class PhotonProductionWriter:
    def __init__(self, fname):
        warnings.warn(
            "PhotonProductionWriter is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.fname = fname
        self.config = MyConfig(fname)

    def save(self, photon_producion_config: PhotonProductionConfiguration):

        self.config["date"] = time.strftime("%d/%m/%y")
        self.config["time"] = time.strftime("%H:%M:%S")

        self.config["save location"] = photon_producion_config.save_location
        self.config["mot reload"] = photon_producion_config.mot_reload
        self.config["iterations"] = photon_producion_config.iterations

        self.config["waveform sequence"] = photon_producion_config.waveform_sequence
        self.config["waveforms"] = photon_producion_config.waveforms
        self.config["waveform stitch delays"] = photon_producion_config.waveform_stitch_delays

        awg_config: AwgConfiguration = photon_producion_config.awg_configuration

        self.config["AWG"] = {}
        self.config["AWG"]["sample rate"] = awg_config.sample_rate
        self.config["AWG"]["burst count"] = awg_config.burst_count

        tdc_config = photon_producion_config.tdc_configuration

        self.config["TDC"]["counter channels"] = tdc_config.counter_channels
        self.config["TDC"]["marker channel"] = tdc_config.marker_channels
        self.config["TDC"]["timestamp buffer size"] = tdc_config.timestamp_buffer_size

        self.config.write()


class AbsorbtionImagingWriter:
    def __init__(self, fname):
        self.fname = fname
        self.config = ConfigObj(fname)

    def save(self, sequence_fname, daq_config_fname, absorbtion_imaging_config_fname):

        # TODO

        self.config.write()


class ExperimentalAutomationReader:
    def __init__(self, fname):
        self.fname = fname
        self.config = MyConfig(fname)

    def get_experimental_automation_configuration(self):

        automated_experiment_configurations = []

        for _, v in sorted(self.config["experiments"].items()):
            automated_experiment_configurations.append(
                SingleExperimentConfig(
                    daq_channel_static_values=map(
                        lambda x: (int(ast.literal_eval(x)[0]), float(ast.literal_eval(x)[1])),
                        v["daq_channel_static_values"]
                        if v["daq_channel_static_values"] != []
                        else [],
                    ),
                    sequence=SequenceReader(v["sequence_fname"]).load_sequence(),
                    sequence_fname=v["sequence_fname"],
                    iterations=int(v["iterations"]),
                    mot_reload=ast.literal_eval(v["mot_reload"]),
                    modulation_frequencies=map(
                        float,
                        v["modulation_frequencies"] if v["modulation_frequencies"] != [] else [],
                    ),
                )
            )

        return ExperimentSessionConfig(
            save_location=self.config["save_location"],
            summary_fname=self.config["summary_fname"],
            automated_experiment_configurations=automated_experiment_configurations,
            daq_channel_update_steps=float(self.config["daq_channel_update_steps"]),
            daq_channel_update_delay=float(self.config["daq_channel_update_delay"]),
        )


class ExperimentalAutomationWriter:
    def __init__(self, fname):
        self.fname = fname
        self.config = ConfigObj(fname)

    def save(self, photon_producion_config):
        # TODO
        pass
