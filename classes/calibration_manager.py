from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
from typing import Dict
import logging

from .calibration import Calibration

logger = logging.getLogger(__name__)


class CalibrationManager:
    """Loads calibration mappings from a simple INI file and caches Calibration objects."""

    def __init__(self, ini_path: str | Path | None = None):
        self.root = Path.cwd()
        self.ini_path = Path(ini_path) if ini_path is not None else self.root / "calibration.ini"
        self._cache: Dict[str, Calibration] = {}
        self._mappings: Dict[str, str] = {}
        self.extrapolate_policy = "clamp"
        if self.ini_path.exists():
            self.reload()

    def reload(self) -> None:
        cfg = ConfigParser()
        cfg.read(self.ini_path)

        self._mappings.clear()
        if cfg.has_section("defaults"):
            self.extrapolate_policy = cfg.get("defaults", "extrapolate_policy", fallback="clamp")

        if cfg.has_section("calibrations"):
            for key, val in cfg.items("calibrations"):
                # allow values like: channel_name, path or just path
                parts = [p.strip() for p in val.split(",", 1)]
                if len(parts) == 2:
                    _, path = parts
                else:
                    path = parts[0]
                resolved = (self.root / path).resolve()
                self._mappings[key] = str(resolved)

        # Clear cache so reload picks up new files
        self._cache.clear()

    def get_calibration(self, key: str) -> Calibration | None:
        path = self._mappings.get(key)
        if path is None:
            return None
        if path in self._cache:
            return self._cache[path]
        try:
            cal = Calibration.from_file(path, extrapolate=self.extrapolate_policy)
        except Exception:
            logger.exception("Failed to load calibration for %s -> %s", key, path)
            return None
        self._cache[path] = cal
        return cal
