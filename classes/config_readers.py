"""
Created on 22 Apr 2016

@author: Tom Barrett, Jan Ole Ernst
"""

import ast
import functools
import operator
import os
import re
import time
import warnings
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

import numpy as np
from configobj import ConfigObj

from classes.DAQ import (
    INPUT_LINE,
    OUTPUT_LINE,
    Channel_P1A,
    Channel_P1B,
    Channel_P1C,
    Channel_P1CH,
    Channel_P1CL,
    DAQ_card,
    DAQ_channel,
    DAQ_controller,
    DAQ_dio,
)
from classes.experimental_configs import (
    AbsorbtionImagingConfiguration,
    AwgConfiguration,
    ExperimentSessionConfig,
    MotFluoresceConfiguration,
    PhotonProductionConfiguration,
    SingleExperimentConfig,
    TdcConfiguration,
    Waveform,
)

# from instruments.WX218x.WX218x_awg import Channel
from classes.Sequence import Sequence

GLOB_TRUE_BOOL_STRINGS = ["true", "t", "yes", "y"]


def get_config_root() -> str:
    """Return the directory used as the base for resolving relative config paths.
    Uses environment variable COLD_CONTROL_CONFIG_ROOT if set, otherwise Path.cwd()."""
    return os.environ.get("COLD_CONTROL_CONFIG_ROOT", str(Path.cwd()))


def resolve_config_path(path: str, base: Optional[str] = None) -> str:
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
        Warning("to_float_list received a string input. This may lead to unexpected behavior.")
        return [float(arg)]
    return list(map(float, arg))

    # def to_float_list(arg):
    #     if arg is None:
    #         return None
    #     if isinstance(arg, list):
    #         return list(map(float, arg))
    #     elif isinstance(arg, (int, float)):
    #         return [float(arg)]
    #     elif isinstance(arg, str):
    #         items = [x.strip() for x in arg.replace(',', '\n').split('\n') if x.strip()]
    #         try:
    #             return list(map(float, items))
    #         except ValueError as e:
    #             raise ValueError(f"Could not convert one of the entries to float: {items}") from e
    #     else:
    #         raise TypeError(f"Unsupported input type for to_float_list: {type(arg)}")


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
        print("Config keys:", self.config.keys())
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
            channels.append(DAQ_channel(*channel_args))
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

            dios.append(DAQ_dio(dio_name, dio_num, port, line, direction, enabled_state))
        return dios

    def load_daq_controller(self) -> DAQ_controller:
        """Returns a DAQ controller object as configured in the config file."""

        channels = self._load_channels()
        dios = self._load_dios()

        daq_master = DAQ_card(
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
        daq_slaves = []

        for _, v in self.config["DAQ cards"]["slaves"].items():
            try:
                daq_slaves.append(
                    DAQ_card(
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
                print(
                    "It looks like one of the DAQ cards has a channel expected that does not exist"
                )
                print([ch.chNum for ch in channels])
                raise err

        return DAQ_controller(daq_master, daq_slaves)

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
        seq = Sequence(*self.get_sequence_init_args())
        sequence_channels: dict[str, Any] = {}
        sequence_channels = self.config["sequence channels"]

        for _, v in sequence_channels.items():
            ch = int(v["chNum"])
            tv_pairs = [tuple(ast.literal_eval(x)) for x in v["tV_pairs"]]
            v_interval_styles = [int(x) for x in v["V_interval_styles"]]

            seq.addChannelSeq(ch, tv_pairs, v_interval_styles)

        return seq

    def get_sequence_init_args(self):
        return int(self.config["sequence"]["n_samples"]), int(self.config["sequence"]["t_step"])

    def get_global_timings(self):
        return [eval(x) for x in self.config["sequence"]["global_timings"]]

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

    #     writer.save(self.sequence, self.sequence_channel_labels, self.seqEditor.global_timings, self.notesFrame.getUserNotes())
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
        waveforms = self._parse_waveforms()
        output_channels = self._parse_output_channels(
            raw_channels=self.config["waveform output channels"]
        )

        raw_seq = eval(self.config["waveform sequence"])
        waveform_sequence = tuple(tuple(ch) for ch in raw_seq)

        awg_config = AwgConfiguration(
            waveform_sequence=waveform_sequence,
            waveforms=tuple(waveforms),
            sample_rate=float(self.config["sample rate"]),
            burst_count=int(self.config["burst count"]),
            waveform_output_channels=tuple(output_channels),
            waveform_output_channel_lags=tuple(
                map(float, self.config["waveform output channel lags"])
            ),
            marker_width=eval(self.config["marker width"]),
            waveform_stitch_delays=tuple(
                tuple(x) if isinstance(x, list) else (x,)
                for x in eval(self.config["waveform stitch delays"])
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

    def _parse_waveforms(self) -> tuple[Waveform, ...]:
        """Read the ``[waveforms]`` section and return a tuple of ``Waveform`` objects."""
        waveforms: list[Waveform] = []
        for _key, v in self.config["waveforms"].items():
            phases = self._parse_phases(v.get("phases"))
            fname = resolve_config_path(v["filename"])
            waveforms.append(
                Waveform(
                    fname=fname,
                    mod_frequency=float(v["modulation frequency"]),
                    phases=phases,
                )
            )
        return tuple(waveforms)

    @staticmethod
    def _parse_phases(raw_phases) -> list[tuple[float, int]]:
        """Convert the raw phases value from the config into a list of (phase, index) tuples.

        Handles:
        - ``None`` / empty string / list of empty strings  -> ``[]`` with warning
        - A list of numeric strings -> ``[(float, index), ...]``
        - A string like ``"(0.0, 0) (1.57, 100)"`` -> parsed accordingly
        """
        if raw_phases is None:
            warnings.warn(
                "Phases field is missing in waveform config; defaulting to empty list.",
                stacklevel=2,
            )
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
        print(f"Reading config file: {fname}")
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
            "use_cam",
            "use_scope",
            "use_awg",
            "metadata",
        ]
        missing = [k for k in required_top if k not in self.config]
        if missing:
            raise ValueError(f"Experiment config missing required keys: {missing}")
        if "metadata" not in self.config or "experiment_type" not in self.config["metadata"]:
            raise ValueError("Experiment config [metadata] must contain experiment_type")
        if self.config.get("use_scope"):
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
        if self.config.get("use_awg"):
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
            print(
                r"To fix this error you probably need to add a 'metadata' section to the config file. See configs\sequence\pulse_shaping_expt\photon_prod_config.ini"
            )
            raise KeyError("No experiment type specified in the config file.")

        return expt_type.lower()

    def get_photon_production_configuration(self):

        # Delegate AWG config parsing to AwgConfigReader
        awg_reader = AwgConfigReader(self.fname)
        awg_config = awg_reader.load_awg_configuration()

        tdc_config = TdcConfiguration(
            counter_channels=list(map(eval, self.config["TDC"]["counter channels"])),
            marker_channel=int(self.config["TDC"]["marker channel"]),
            timestamp_buffer_size=int(self.config["TDC"]["timestamp buffer size"]),
        )

        photon_production_config = PhotonProductionConfiguration(
            save_location=self.config["save location"],
            mot_reload=eval(self.config["mot reload"]),
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
        """

        use_camera = to_bool(self.config["use_cam"])
        use_scope = to_bool(self.config["use_scope"])
        use_awg = to_bool(self.config["use_awg"])

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

        else:
            camera_settings_dict = None

        if use_scope:
            scope = self.config["scope_settings"]
            data_chs = {}
            impedance_section = scope.get("data_channel_impedance", {})
            coupling_section = scope.get("data_channel_coupling", {})
            for ch_idx, limits in scope["data_channels"].items():
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
            scope_settings_dict = {
                "trigger_channel": int(scope["trigger_channel"]),
                "trigger_level": float(scope["trigger_level"]),
                "sample_rate": float(scope["sample_rate"]),
                "time_range": to_float_tuple(scope["time_range"]),
                "data_channels": data_chs,
            }
        else:
            scope_settings_dict = None

        if use_awg:
            awg = self.config["awg_settings"]
            config_path = awg["config_path"]

            # Delegate AWG config parsing to AwgConfigReader
            awg_reader = AwgConfigReader(config_path)
            awg_config = awg_reader.load_awg_configuration()

            awg_settings_dict = {
                "config_path_full": config_path,
                "awg_config": awg_config,
                "config_path_single": None,  # Default to None if not provided
                "awg_config_single": None,  # Default to None if not provided
                "sequence_config_single": None,  # Default to None if not provided
            }

            metadata = self.config.get("metadata") or {}
            ct = metadata.get("config_type", "").strip().lower()
            if ct == "experiment":
                self._validate_experiment_config_structure()

            mot_fluoresce_config = MotFluoresceConfiguration(
                save_location=self.config["save location"],
                mot_reload=eval(self.config["mot reload"]),
                iterations=int(self.config["iterations"]),
                use_cam=use_camera,
                use_scope=use_scope,
                use_awg=use_awg,
                cam_dict=camera_settings_dict,
                scope_dict=scope_settings_dict,
                awg_dict=awg_settings_dict,
            )

            return mot_fluoresce_config

        else:
            awg_settings_dict = None

        metadata = self.config.get("metadata") or {}
        ct = getattr(metadata, "get", lambda k, d="": d)("config_type", "").strip().lower()
        if ct == "experiment":
            self._validate_experiment_config_structure()

        mot_fluoresce_config = MotFluoresceConfiguration(
            save_location=self.config["save location"],
            mot_reload=eval(self.config["mot reload"]),
            iterations=int(self.config["iterations"]),
            use_cam=use_camera,
            use_scope=use_scope,
            use_awg=use_awg,
            cam_dict=camera_settings_dict,
            scope_dict=scope_settings_dict,
            awg_dict=awg_settings_dict,
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
            scan_abs_img_freq=eval(self.config["scan_abs_img_freq"]),
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
        """

        expt_type = self.get_expt_type()

        if expt_type == "photon production":
            return self.get_photon_production_configuration()
        elif expt_type == "mot fluorescence":
            return self.get_mot_flourescence_configuration()
        elif expt_type == "absorbtion imaging":
            return self.get_absorbtion_imaging_configuration()
        else:
            raise ValueError(f"Unknown experiment type: {expt_type}")


class PhotonProductionWriter:
    def __init__(self, fname):
        self.fname = fname
        self.config = MyConfig(fname)

    #     writer.save(self.sequence, self.sequence_channel_labels, self.seqEditor.global_timings, self.notesFrame.getUserNotes())
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
                        lambda x: (int(eval(x)[0]), float(eval(x)[1])),
                        v["daq_channel_static_values"]
                        if v["daq_channel_static_values"] != []
                        else [],
                    ),
                    sequence=SequenceReader(v["sequence_fname"]).load_sequence(),
                    sequence_fname=v["sequence_fname"],
                    iterations=int(v["iterations"]),
                    mot_reload=eval(v["mot_reload"]),
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

    #     writer.save(self.sequence, self.sequence_channel_labels, self.seqEditor.global_timings, self.notesFrame.getUserNotes())
    def save(self, photon_producion_config):
        # TODO
        pass
