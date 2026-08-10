"""Convert legacy calibration .txt files into canonical CSV files.

Usage: run this script from the repository root. It will scan the `calibrations/`
directory for .txt files and write corresponding .csv files next to them.
"""

from __future__ import annotations

from pathlib import Path
import re
import csv
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def parse_two_column_txt(path: Path) -> Tuple[str, list[tuple[float, float]]]:
    """Parse a simple two-column legacy calibration file.

    Returns the units string and a list of (voltage, value) rows.
    """
    re_read_in = re.compile(r"([\+\-]?\d+\.?\d*)[ \t,]+([\+\-]?\d+\.?\d*)")
    rows = []
    units = ""
    with path.open() as f:
        first = f.readline().strip()
        # try to extract units from header like 'Voltage (V)  Power (uW)'
        m = re.search(r"\(([^\)]+)\)", first)
        if m:
            units = m.group(1)
        else:
            # fallback: last token
            units = first.split()[-1] if first else ""
        for line in f:
            line = line.strip()
            if not line:
                continue
            match = re_read_in.search(line)
            if match:
                rows.append((float(match.group(1)), float(match.group(2))))
    return units, rows


def migrate(root: Path) -> None:
    cal_dir = root / "calibrations"
    if not cal_dir.exists():
        logger.error("calibrations/ directory not found: %s", cal_dir)
        return

    for txt in cal_dir.rglob("*.txt"):
        try:
            units, rows = parse_two_column_txt(txt)
            if not rows:
                logger.warning("No data parsed from %s; skipping", txt)
                continue
            # Ensure sorted by voltage
            rows = sorted(rows, key=lambda r: r[0])
            out = txt.with_suffix(".csv")
            with out.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Voltage (V)", f"Value ({units})"])
                for v, u in rows:
                    writer.writerow([v, u])
            logger.info("Converted %s -> %s", txt, out)
        except Exception:
            logger.exception("Failed to convert %s", txt)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root (default: .)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    migrate(Path(args.root))
