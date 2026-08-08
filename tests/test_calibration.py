import csv
from pathlib import Path

import numpy as np
import pytest

from classes.calibration import Calibration


def write_simple_cal(path: Path):
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Voltage (V)", "Value (unit)"])
        writer.writerow([0.0, 0.0])
        writer.writerow([5.0, 50.0])
        writer.writerow([10.0, 100.0])


def test_from_file_loads_and_converts(tmp_path: Path):
    p = tmp_path / "cal.csv"
    write_simple_cal(p)

    cal = Calibration.from_file(p)
    assert cal.units == "unit"

    # scalar conversions
    assert cal.from_voltage(5.0) == pytest.approx(50.0)
    assert cal.to_voltage(50.0) == pytest.approx(5.0)

    # array conversions
    vals = np.array([0.0, 5.0, 10.0])
    out = cal.from_voltage(vals)
    assert (out == np.array([0.0, 50.0, 100.0])).all()


def test_extrapolate_clamp_and_error(tmp_path: Path):
    p = tmp_path / "cal.csv"
    write_simple_cal(p)

    cal_clamp = Calibration.from_file(p, extrapolate="clamp")
    # physical value above range should be clamped
    v = cal_clamp.to_voltage(200.0)
    assert v == pytest.approx(10.0)

    cal_err = Calibration.from_file(p, extrapolate="error")
    with pytest.raises(ValueError):
        cal_err.to_voltage(200.0)
