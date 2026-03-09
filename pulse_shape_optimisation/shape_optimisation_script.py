"""
Pulse Shape Optimisation — Example Script

Demonstrates the new experiment API from pulse_experiment.py:
  1. Load config and theoretical waveform
  2. Run a baseline experiment
  3. Compute a corrected waveform from the result
  4. Run a validation experiment with the correction
  5. Compare both results

Replace the optimisation step (step 3) with any algorithm you like —
NLMS, Wiener, gradient descent, etc.  The experiment runner is agnostic.
"""

import sys
from pathlib import Path

import numpy as np

# Ensure the parent directory is on the path so imports resolve
sys.path.append(str(Path(__file__).resolve().parent.parent))

from pulse_shape_optimisation.pulse_experiment import (
    PulseShapeConfig,
    PulseShapeExperimentRunner,
    load_signal_from_path,
)

SCRIPT_DIR = Path(__file__).resolve().parent


def main():
    # ── 1. Configuration ─────────────────────────────────────────────────
    config_path = SCRIPT_DIR / "config_pulse_experiment.ini"
    cfg = PulseShapeConfig(config_path)

    # ── 2. Load theoretical waveform ─────────────────────────────────────
    theoretical_signal = load_signal_from_path(
        cfg.get_theoretical_signal_path(),
        cfg.amplitude,
    )

    # ── 3. Baseline experiment ───────────────────────────────────────────
    runner = PulseShapeExperimentRunner(cfg, waveform=theoretical_signal)

    try:
        baseline = runner.run()
        print(f"Baseline MSE:  {baseline.mse:.6e}")
        print(f"Baseline RMSE: {baseline.rmse:.6e}")
        print(f"Baseline MAE:  {baseline.mae:.6e}")

        baseline.plot(
            output_dir=cfg.output_dir,
            filename="01_baseline.png",
            title="Baseline — theoretical waveform sent directly",
        )

        # ── 4. Compute a corrected waveform ──────────────────────────────
        #  Simple additive correction: subtract the signed error from the
        #  input.  Replace this with your own optimisation algorithm.
        corrected_waveform = theoretical_signal - baseline.signed_error

        # Renormalise to the target amplitude
        if np.max(np.abs(corrected_waveform)) > 0:
            corrected_waveform = (
                corrected_waveform / np.max(np.abs(corrected_waveform)) * cfg.amplitude
            )

        # ── 5. Validation experiment ─────────────────────────────────────
        runner.waveform = corrected_waveform
        validation = runner.run()
        print(f"\nValidation MSE:  {validation.mse:.6e}")
        print(f"Validation RMSE: {validation.rmse:.6e}")
        print(f"Validation MAE:  {validation.mae:.6e}")

        validation.plot(
            output_dir=cfg.output_dir,
            filename="02_validation.png",
            title=(
                f"Validation — corrected waveform  |  "
                f"MSE {validation.mse:.4e} (was {baseline.mse:.4e})"
            ),
        )

        # ── 6. Save optimised waveform ───────────────────────────────────
        if cfg.save_optimized_to:
            np.savetxt(cfg.save_optimized_to, corrected_waveform, delimiter=",")
            print(f"\nSaved corrected waveform to {cfg.save_optimized_to}")

    finally:
        runner.close()


if __name__ == "__main__":
    main()
