"""
M-LOOP Bayesian Optimisation for Pulse Shapes

Uses Bayesian optimisation (Gaussian-process learner in M-LOOP) to optimise
low-frequency Fourier correction coefficients applied to the theoretical
waveform.  This efficiently explores the parameter space without needing
gradients.

Requirements::

    pip install M-LOOP

Usage::

    python optimise_mloop.py                     # uses default config
    python optimise_mloop.py path/to/config.ini  # custom config
"""

import os
import sys
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import mloop.interfaces as mli
import mloop.controllers as mlc

from marina.pulse_experiment import (
    PulseShapeConfig,
    PulseShapeExperimentRunner,
    load_signal_from_path,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Fourier helpers
# ---------------------------------------------------------------------------

def fourier_correction(
    base_waveform: np.ndarray,
    coeffs: np.ndarray,
    amplitude: float,
) -> np.ndarray:
    """
    Apply a smooth correction to *base_waveform* using Fourier coefficients.

    ``coeffs`` has length ``2*K``: the first K values are cosine amplitudes,
    the second K values are sine amplitudes.  These define a correction signal
    that is added to the waveform.

    The result is clipped to [0, amplitude].
    """
    N = len(base_waveform)
    K = len(coeffs) // 2
    t = np.linspace(0, 1, N, endpoint=False)

    correction = np.zeros(N)
    for k in range(K):
        freq = k + 1  # start at frequency 1
        correction += coeffs[k] * np.cos(2 * np.pi * freq * t)
        correction += coeffs[K + k] * np.sin(2 * np.pi * freq * t)

    corrected = base_waveform + correction
    corrected = np.clip(corrected, 0, None)

    # Renormalise to target amplitude
    peak = np.max(np.abs(corrected))
    if peak > 0:
        corrected = (corrected / peak) * amplitude

    return corrected


# ---------------------------------------------------------------------------
# M-LOOP Interface
# ---------------------------------------------------------------------------

class PulseShapeInterface(mli.Interface):
    """
    M-LOOP interface that maps Fourier coefficients → waveform → experiment → cost.
    """

    def __init__(
        self,
        cfg: PulseShapeConfig,
        runner: PulseShapeExperimentRunner,
        theoretical: np.ndarray,
    ):
        super().__init__()
        self.cfg = cfg
        self.runner = runner
        self.theoretical = theoretical
        self.iteration = 0

    def get_next_cost_dict(self, params_dict):
        """Called by M-LOOP with a new set of Fourier coefficients."""
        self.iteration += 1
        params = params_dict["params"]

        # Build corrected waveform from Fourier coefficients
        corrected = fourier_correction(
            self.theoretical, params, self.cfg.amplitude
        )

        # Run experiment
        self.runner.waveform = corrected
        try:
            result = self.runner.run()
        except Exception as e:
            print(f"  [Iteration {self.iteration}] Experiment failed: {e}")
            return {"bad": True}

        cost = result.mse
        print(f"  [Iteration {self.iteration}] MSE = {cost:.6e}")

        # Save plot every iteration
        result.plot(
            output_dir=str(self.cfg.output_dir),
            filename=f"mloop_iter_{self.iteration:03d}.png",
            title=f"M-LOOP Iteration {self.iteration} — MSE = {cost:.4e}",
        )

        # Save normalised waveform CSV
        waveform_norm = result._normalise_01(corrected)
        np.savetxt(
            self.cfg.output_dir / f"mloop_waveform_{self.iteration:03d}.csv",
            waveform_norm,
            delimiter=",",
        )

        return {"cost": float(cost), "uncer": 0.0, "bad": False}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_mloop_optimisation(cfg: PulseShapeConfig):
    """Execute M-LOOP Bayesian optimisation."""
    theoretical = load_signal_from_path(
        cfg.get_theoretical_signal_path(), cfg.amplitude
    )

    runner = PulseShapeExperimentRunner(cfg, theoretical)

    # Number of Fourier parameters = 2 * K (cosine + sine)
    K = cfg.num_fourier_coeffs
    num_params = 2 * K

    # Coefficient bounds — corrections should be small relative to amplitude
    max_coeff = cfg.amplitude * 0.5
    min_boundary = [-max_coeff] * num_params
    max_boundary = [max_coeff] * num_params

    try:
        interface = PulseShapeInterface(cfg, runner, theoretical)
        controller = mlc.create_controller(
            interface,
            controller_type="gaussian_process",
            max_num_runs=cfg.max_num_runs,
            num_params=num_params,
            min_boundary=min_boundary,
            max_boundary=max_boundary,
        )

        print(f"Starting M-LOOP optimisation with {num_params} Fourier parameters")
        print(f"Max runs: {cfg.max_num_runs}")
        print(f"Output directory: {cfg.output_dir}")
        controller.optimize()

        # Report results
        print(f"\n{'='*60}")
        print(f"  M-LOOP Optimisation Complete")
        print(f"{'='*60}")
        print(f"  Best cost (MSE): {controller.best_cost:.6e}")
        print(f"  Best parameters: {controller.best_params}")

        # Save optimised waveform
        best_waveform = fourier_correction(
            theoretical, controller.best_params, cfg.amplitude
        )
        best_norm = _normalise_01_static(best_waveform)
        np.savetxt(
            cfg.output_dir / "mloop_optimised_waveform.csv",
            best_norm,
            delimiter=",",
        )
        print(f"  Saved to {cfg.output_dir / 'mloop_optimised_waveform.csv'}")

    finally:
        runner.close()


def _normalise_01_static(signal):
    """Standalone normalise to [0, 1] for saving."""
    sig = np.asarray(signal, dtype=float)
    smin, smax = sig.min(), sig.max()
    if smax - smin == 0:
        return np.zeros_like(sig)
    return (sig - smin) / (smax - smin)


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        SCRIPT_DIR, "config_pulse_experiment.ini"
    )
    print(f"Loading config: {config_path}")
    cfg = PulseShapeConfig(config_path)
    print(f"Output directory: {cfg.output_dir}")

    run_mloop_optimisation(cfg)


if __name__ == "__main__":
    main()
