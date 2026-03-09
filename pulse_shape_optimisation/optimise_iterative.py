"""
Iterative Feedback Pulse Shape Optimisation

Corrects the AWG waveform by repeatedly:
    1. Running an experiment with the current waveform
    2. Computing the signed error (measured - theoretical)
    3. Subtracting a fraction (gain) of the error from the waveform
    4. Running again until the error is below threshold or max iterations

All results (plots, CSVs) are saved to the timestamped output directory
configured in the .ini file.

Usage::

    python optimise_iterative.py                     # uses default config
    python optimise_iterative.py path/to/config.ini  # custom config
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parent.parent))
from pulse_shape_optimisation.pulse_experiment import (
    PulseShapeConfig,
    PulseShapeExperimentResult,
    PulseShapeExperimentRunner,
    load_signal_from_path,
)

SCRIPT_DIR = Path(__file__).resolve().parent


def run_iterative_optimisation(cfg: PulseShapeConfig) -> PulseShapeExperimentResult:
    """
    Run the iterative feedback optimisation loop.

    Returns the final :class:`PulseShapeExperimentResult`.
    """
    # Load and normalise the theoretical waveform
    theoretical = load_signal_from_path(cfg.get_theoretical_signal_path(), cfg.amplitude)

    waveform = theoretical.copy()
    runner = PulseShapeExperimentRunner(cfg, waveform)

    best_result: PulseShapeExperimentResult | None = None
    best_mse = float("inf")

    try:
        for iteration in range(1, cfg.max_iterations + 1):
            print(f"\n{'=' * 60}")
            print(f"  Iteration {iteration}/{cfg.max_iterations}")
            print(f"{'=' * 60}")

            # Update the runner's waveform
            runner.waveform = waveform
            result = runner.run()

            print(f"  MSE:  {result.mse:.6e}")
            print(f"  RMSE: {result.rmse:.6e}")
            print(f"  MAE:  {result.mae:.6e}")

            # Save plot for this iteration
            result.plot(
                output_dir=cfg.output_dir,
                filename=f"iteration_{iteration:03d}.png",
                title=(f"Iteration {iteration} — MSE = {result.mse:.4e}"),
            )

            # Save normalised waveform CSV
            waveform_norm = result._normalise_01(waveform)
            np.savetxt(
                cfg.output_dir / f"waveform_{iteration:03d}.csv",
                waveform_norm,
                delimiter=",",
            )

            # Track best
            if result.mse < best_mse:
                best_mse = result.mse
                best_result = result

            # Check convergence
            if result.mse < cfg.error_threshold:
                print(f"\n  Converged! MSE {result.mse:.6e} < threshold {cfg.error_threshold}")
                break

            # Compute correction using the RAW (un-normalised) signals
            raw_error = result._raw_measured_signal - result._raw_theoretical_signal

            # Apply correction: subtract a fraction of the error
            waveform = waveform - cfg.gain * raw_error

            # Clip to valid AWG range and renormalise
            waveform = np.clip(waveform, 0, None)
            if np.max(np.abs(waveform)) > 0:
                waveform = (waveform / np.max(np.abs(waveform))) * cfg.amplitude

        else:
            print(f"\n  Reached max iterations ({cfg.max_iterations}). Best MSE: {best_mse:.6e}")

        # Save the optimised waveform (normalised to [0, 1])
        if best_result is not None:
            optimised_norm = best_result._normalise_01(waveform)
            np.savetxt(
                cfg.output_dir / "optimised_waveform.csv",
                optimised_norm,
                delimiter=",",
            )
            print(f"\nSaved optimised waveform to {cfg.output_dir / 'optimised_waveform.csv'}")

    finally:
        runner.close()

    assert best_result is not None
    return best_result


def main():
    config_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else SCRIPT_DIR / "config_pulse_experiment.ini"
    )
    print(f"Loading config: {config_path}")
    cfg = PulseShapeConfig(config_path)
    print(f"Output directory: {cfg.output_dir}")

    result = run_iterative_optimisation(cfg)
    print(f"\nFinal best MSE: {result.mse:.6e}")


if __name__ == "__main__":
    main()
