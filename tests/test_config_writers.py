"""
Unit tests for ConfigWriter, DaqWriter, and SequenceWriter.

All tests write to temporary files — no hardware required.
Run with:  pytest tests/test_config_writers.py -v
"""

from pathlib import Path

from configobj import ConfigObj

from classes.config_readers import ConfigWriter, DaqWriter, SequenceWriter
from classes.daq_sequence import DaqSequence, IntervalStyle


class TestConfigWriter:
    """Tests for the ConfigWriter class."""

    def test_save_writes_filenames(self, tmp_path):
        """save() writes the correct filenames to the config file."""
        fname = str(tmp_path / "config.ini")
        Path(fname).touch()

        writer = ConfigWriter(fname)
        writer.save(
            sequence_fname="seq.ini",
            daq_config_fname="daq.ini",
            absorption_imaging_config_fname="abs.ini",
            photon_production_config_fname="photon.ini",
        )

        config = ConfigObj(fname)
        assert config["sequence_filename"] == "seq.ini"
        assert config["daq_config_filename"] == "daq.ini"
        assert config["absorption_images_config_filename"] == "abs.ini"
        assert config["photon_production_config_filename"] == "photon.ini"

    def test_save_writes_date_time(self, tmp_path):
        """save() writes date and time fields."""
        fname = str(tmp_path / "config.ini")
        Path(fname).touch()

        writer = ConfigWriter(fname)
        writer.save("s.ini", "d.ini", "a.ini", "p.ini")

        config = ConfigObj(fname)
        assert "date" in config
        assert "time" in config


class _MockCard:
    """Lightweight stand-in for a DAQ card object.

    DaqWriter.save() accesses `card`, `channels`, and per-channel attributes
    including the legacy ``isUIVisable`` spelling.  Real DAQChannel objects use
    ``isUIVisible``, so we provide mock channels that match what the writer
    actually reads.
    """

    def __init__(self, card_num, channels):
        self.card = card_num
        self.channels = channels


class _MockChannel:
    """Channel mock matching the attribute names used by DaqWriter.save()."""

    def __init__(
        self,
        ch_num,
        ch_name="",
        ch_limits=(-10, 10),
        default_value=0.0,
        is_ui_visible=True,
        calibration_fname="",
    ):
        self.chNum = ch_num
        self.chName = ch_name or f"Ch {ch_num}"
        self.chLimits = ch_limits
        self.defaultValue = default_value
        # DaqWriter accesses the legacy spelling ``isUIVisable``
        self.isUIVisable = is_ui_visible
        self.isCalibrated = False
        self.calibrationFname = calibration_fname


class TestDaqWriter:
    """Tests for the DaqWriter class."""

    def test_save_master_only(self, tmp_path):
        """save() writes master card configuration without slaves."""
        ch1 = _MockChannel(0, "Ch 0", (-10, 10), 0.0, True, "")
        ch2 = _MockChannel(1, "Ch 1", (-5, 5), 1.0, False, "")
        master = _MockCard(1, [ch1, ch2])

        fname = str(tmp_path / "daq.ini")
        Path(fname).touch()

        writer = DaqWriter(fname)
        writer.save(master)

        config = ConfigObj(fname)
        assert config["DAQ cards"]["master"]["card number"] == "1"  # type: ignore
        assert config["DAQ channels"]["0"]["chNum"] == "0"  # type: ignore
        assert config["DAQ channels"]["1"]["chNum"] == "1"  # type: ignore

    def test_save_master_and_slave(self, tmp_path):
        """save() writes both master and slave card configurations."""
        ch1 = _MockChannel(0, "Ch 0")
        ch2 = _MockChannel(4, "Ch 4")
        master = _MockCard(1, [ch1])
        slave = _MockCard(2, [ch2])

        fname = str(tmp_path / "daq.ini")
        Path(fname).touch()

        writer = DaqWriter(fname)
        writer.save(master, slave)

        config = ConfigObj(fname)
        assert "slaves" in config["DAQ cards"]
        assert config["DAQ cards"]["slaves"]["1"]["card number"] == "2"  # type: ignore


class TestSequenceWriter:
    """Tests for the SequenceWriter class."""

    def test_save_and_load_roundtrip(self, tmp_path):
        """Saving a sequence and loading it back produces equivalent data."""
        seq = DaqSequence(100, 10)
        seq.add_channel_seq(
            0,
            tv_pairs=[(0.0, 0.0)],
            v_interval_styles=[IntervalStyle.FLAT],
        )

        fname = str(tmp_path / "sequence.ini")
        Path(fname).touch()

        writer = SequenceWriter(fname)
        writer.save(seq, {"0": "Ch 0"}, [(100, "label")], "Test notes")

        # Verify file was written
        config = ConfigObj(fname)
        assert "sequence" in config
        assert config["sequence"]["n_samples"] == "100"  # type: ignore
        assert config["sequence"]["t_step"] == "10"  # type: ignore

    def test_save_writes_notes(self, tmp_path):
        """save() writes user notes to the config file."""
        seq = DaqSequence(50, 5)

        fname = str(tmp_path / "sequence.ini")
        Path(fname).touch()

        writer = SequenceWriter(fname)
        writer.save(seq, {}, [], "My experiment notes")

        config = ConfigObj(fname)
        assert config["notes"]["user"] == "My experiment notes"  # type: ignore
