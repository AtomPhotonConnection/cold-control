"""
Shared pytest fixtures for cold-control tests.

Every test module that needs a DaqSequence, DummyDAQController, or
MotFluoresceConfiguration can import these fixtures simply by requesting
them as function arguments - pytest discovers them automatically from
this file.
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so every `from classes.xxx import`
# works regardless of which directory pytest is invoked from.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Some config readers look for this env-var to resolve relative paths.
os.environ.setdefault("COLD_CONTROL_CONFIG_ROOT", str(PROJECT_ROOT))

import pytest  # noqa: E402 (must come after sys.path manipulation)

from classes.daq import DAQChannel  # noqa: E402
from classes.daq_sequence import DaqSequence, IntervalStyle  # noqa: E402
from classes.experimental_configs import (  # noqa: E402
    MotFluoresceConfiguration,
    MotFluorescenceAlignmentConfiguration,
    ScopeConfiguration,
)
from instruments.dummy import DummyDAQController  # noqa: E402

# ---------------------------------------------------------------------------
# DaqSequence fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_seq():
    """A 100-sample, 10 µs/step sequence (length = 990 µs) with two channels.

    Channel 0: flat at 0 V for the whole sequence.
    Channel 1: flat at 5 V for the whole sequence.
    """
    seq = DaqSequence(n_samples=100, t_step=10)
    seq.add_channel_seq(0, tv_pairs=[(0.0, 0.0)], v_interval_styles=[IntervalStyle.FLAT])
    seq.add_channel_seq(1, tv_pairs=[(0.0, 5.0)], v_interval_styles=[IntervalStyle.FLAT])
    return seq


# ---------------------------------------------------------------------------
# DummyDAQController fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def dummy_daq():
    """A DummyDAQController with two channels (ch 0 and ch 1)."""
    channels = [
        DAQChannel(ch_num=0, ch_name="Test Ch 0", ch_limits=(-10, 10), default_value=0.0),
        DAQChannel(ch_num=1, ch_name="Test Ch 1", ch_limits=(-10, 10), default_value=0.0),
    ]
    return DummyDAQController(channels=channels, continuous_ouput=False)


# ---------------------------------------------------------------------------
# MotFluoresceConfiguration fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mot_config_no_hw(tmp_path):
    """MotFluoresceConfiguration with no hardware (no scope, AWG, or camera)."""
    return MotFluoresceConfiguration(
        save_location=str(tmp_path / "experiment"),
        mot_reload=0,  # 0 ms → instant sleep in run loops
        iterations=1,
        scope_config=None,
        awg_config=None,
        cam_dict=None,
    )


@pytest.fixture
def minimal_scope_config():
    """A minimal ScopeConfiguration for use in tests."""
    return ScopeConfiguration(
        trigger_channel=1,
        trigger_level=0.5,
        sample_rate=1e9,
        time_range=(-2.5e-3, 2.5e-3),
        data_channels={1: {"range": (-5.0, 5.0), "impedance": "1MOhm", "coupling": "DC"}},
    )


@pytest.fixture
def mot_config_with_scope(tmp_path, minimal_scope_config):
    """MotFluoresceConfiguration with a scope but no AWG or camera."""
    return MotFluoresceConfiguration(
        save_location=str(tmp_path / "experiment"),
        mot_reload=0,
        iterations=1,
        scope_config=minimal_scope_config,
        awg_config=None,
        cam_dict=None,
    )


# ---------------------------------------------------------------------------
# MotFluorescenceAlignmentConfiguration fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def alignment_config(mot_config_no_hw, basic_seq):
    """MotFluorescenceAlignmentConfiguration with no hardware and no background."""
    return MotFluorescenceAlignmentConfiguration(
        base_config=mot_config_no_hw,
        base_sequence=basic_seq,
        background_folder=None,
    )
