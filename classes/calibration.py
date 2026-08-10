from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CalibrationMeta:
    units: str
    source_path: Path


class Calibration:
    """Encapsulates a 2-column calibration mapping between voltage and a physical value.

    The CSV must contain at least two columns: the first is voltage (V) and the
    second is the measured/display quantity with units in parentheses in the
    header (e.g. "Power (uW)").
    """

    def __init__(
        self,
        voltages: np.ndarray,
        values: np.ndarray,
        meta: CalibrationMeta,
        extrapolate: Literal["clamp", "warn", "error"] = "clamp",
    ) -> None:
        self._v = np.asarray(voltages, dtype=float)
        self._u = np.asarray(values, dtype=float)
        self.meta = meta
        if extrapolate not in ("clamp", "warn", "error"):
            raise ValueError("invalid extrapolate policy")
        self.extrapolate = extrapolate

        sort_idx = np.argsort(self._v)
        self._v = self._v[sort_idx]
        self._u = self._u[sort_idx]

    @classmethod
    def from_file(cls, path: str | Path, extrapolate: str = "clamp") -> "Calibration":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)

        try:
            df = pd.read_csv(p)
        except Exception as exc:  # pragma: no cover - IO errors surfaced to caller
            logger.error("Failed to read calibration file %s: %s", p, exc)
            raise

        try:
            vcol = df.columns[0]
            ucol = df.columns[1]
            units = str(ucol).split(" ")[-1].strip("()")
        except IndexError:
            raise ValueError(f"Invalid calibration file format: {p}")

        v = np.asarray(df[vcol].values, dtype=float)
        u = np.asarray(df[ucol].values, dtype=float)

        meta = CalibrationMeta(units=units, source_path=p)
        return cls(v, u, meta, extrapolate=extrapolate)

    def to_voltage(self, physical_val: float) -> float:
        u_min, u_max = float(np.min(self._u)), float(np.max(self._u))
        arr_like = isinstance(physical_val, (list, tuple, np.ndarray))
        if arr_like:
            pv = np.asarray(physical_val, dtype=float)
            if self.extrapolate == "error":
                if (pv < u_min).any() or (pv > u_max).any():
                    raise ValueError(f"Value outside bounds [{u_min}, {u_max}]")
            elif self.extrapolate == "clamp":
                pv = np.clip(pv, u_min, u_max)
            else:
                logger.warning(
                    "Extrapolating array values outside calibration bounds [%s,%s]", u_min, u_max
                )
            return np.interp(pv, self._u, self._v)

        # scalar path
        pv = float(physical_val)
        if not (u_min <= pv <= u_max):
            if self.extrapolate == "error":
                raise ValueError(f"Value {pv} outside bounds [{u_min}, {u_max}]")
            elif self.extrapolate == "clamp":
                pv = float(np.clip(pv, u_min, u_max))
            else:
                logger.warning(
                    "Extrapolating value %s outside calibration bounds [%s,%s]", pv, u_min, u_max
                )
        return float(np.interp(pv, self._u, self._v))

    def from_voltage(self, voltage: float) -> float:
        v_min, v_max = float(np.min(self._v)), float(np.max(self._v))
        arr_like = isinstance(voltage, (list, tuple, np.ndarray))
        if arr_like:
            vv = np.asarray(voltage, dtype=float)
            if self.extrapolate == "error":
                if (vv < v_min).any() or (vv > v_max).any():
                    raise ValueError(f"Voltage outside bounds [{v_min}, {v_max}]")
            elif self.extrapolate == "clamp":
                vv = np.clip(vv, v_min, v_max)
            else:
                logger.warning(
                    "Extrapolating array voltages outside calibration bounds [%s,%s]", v_min, v_max
                )
            return np.interp(vv, self._v, self._u)

        v = float(voltage)
        if not (v_min <= v <= v_max):
            if self.extrapolate == "error":
                raise ValueError(f"Voltage {v} outside bounds [{v_min}, {v_max}]")
            elif self.extrapolate == "clamp":
                v = float(np.clip(v, v_min, v_max))
            else:
                logger.warning(
                    "Extrapolating voltage %s outside calibration bounds [%s,%s]", v, v_min, v_max
                )
        return float(np.interp(v, self._v, self._u))

    def range_in_units(self) -> tuple[float, float]:
        return float(np.min(self._u)), float(np.max(self._u))

    def range_in_voltage(self) -> tuple[float, float]:
        return float(np.min(self._v)), float(np.max(self._v))

    @property
    def units(self) -> str:
        return self.meta.units
