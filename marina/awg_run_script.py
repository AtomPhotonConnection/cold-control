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

import os
import sys

# Ensure the parent directory is on the path so imports resolve
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from marina.pulse_experiment import (
    PulseShapeConfig,
    PulseShapeExperimentRunner,
    load_signal_from_path,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    # ── 1. Configuration ─────────────────────────────────────────────────
    config_path = os.path.join(SCRIPT_DIR, "config_pulse_experiment.ini")
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
            output_dir=str(cfg.output_dir),
            filename="01_baseline.png",
            title="Baseline — theoretical waveform sent directly",
        )


        baseline.save_to_csv(os.path.join(cfg.output_dir, "baseline_measured_signal.csv"), to_save="measured")

    finally:
        runner.close()


if __name__ == "__main__":
    main()
