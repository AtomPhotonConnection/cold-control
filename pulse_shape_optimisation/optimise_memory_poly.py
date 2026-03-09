"""
Memory Polynomial Predistortion for Pulse Shapes

Identifies the AWG-to-scope transfer function as a memory polynomial and
inverts it to compute a pre-distorted waveform.  This compensates for
nonlinear amplitude distortion and short-range memory effects.

The model:

    y[n] = Σ_{k=0}^{K} Σ_{q=0}^{Q} a_{kq} · x[n-q] · |x[n-q]|^k

where x is the AWG input, y is the scope measurement, K is the polynomial
degree and Q is the memory depth.

Usage::

    python optimise_memory_poly.py                     # uses default config
    python optimise_memory_poly.py path/to/config.ini  # custom config
"""

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


# ---------------------------------------------------------------------------
# Memory Polynomial helpers
# ---------------------------------------------------------------------------


def build_memory_poly_matrix(
    signal: np.ndarray,
    poly_degree: int,
    mem_depth: int,
) -> np.ndarray:
    """
    Build the regression matrix for a memory polynomial model.

    For signal x of length N, produce a matrix Φ of shape (N, (K+1)*(Q+1))
    where each column corresponds to x[n-q] · |x[n-q]|^k.

    Args:
        signal:      Input signal of length N.
        poly_degree: Maximum polynomial degree K (includes odd and even).
        mem_depth:   Number of memory taps Q (0 = memoryless).

    Returns:
        Φ matrix of shape (N, num_coefficients).
    """
    big_n = len(signal)
    columns = []

    for q in range(mem_depth + 1):
        # Create delayed version x[n-q]
        if q == 0:
            x_delayed = signal.copy()
        else:
            x_delayed = np.zeros(big_n)
            x_delayed[q:] = signal[:-q]

        for k in range(poly_degree + 1):
            # x[n-q] · |x[n-q]|^k
            col = x_delayed * np.abs(x_delayed) ** k
            columns.append(col)

    return np.column_stack(columns)


def fit_memory_poly(
    input_signal: np.ndarray,
    output_signal: np.ndarray,
    poly_degree: int,
    mem_depth: int,
) -> np.ndarray:
    """
    Fit memory polynomial coefficients via least squares.

    Args:
        input_signal:  AWG input (x).
        output_signal: Scope measurement (y).
        poly_degree:   Maximum polynomial degree.
        mem_depth:     Memory depth.

    Returns:
        Coefficient vector a of shape ((K+1)*(Q+1),).
    """
    phi = build_memory_poly_matrix(input_signal, poly_degree, mem_depth)
    # Least-squares solve: Phi @ a ≈ output_signal
    coeffs, _, _, _ = np.linalg.lstsq(phi, output_signal, rcond=None)
    return coeffs


def apply_memory_poly(
    signal: np.ndarray,
    coeffs: np.ndarray,
    poly_degree: int,
    mem_depth: int,
) -> np.ndarray:
    """Apply the memory polynomial model with the given coefficients."""
    phi = build_memory_poly_matrix(signal, poly_degree, mem_depth)
    return phi @ coeffs


def invert_memory_poly(
    desired_output: np.ndarray,
    coeffs: np.ndarray,
    poly_degree: int,
    mem_depth: int,
    amplitude: float,
    max_iterations: int = 50,
    tol: float = 1e-8,
) -> np.ndarray:
    """
    Invert the memory polynomial to find the pre-distorted input.

    Uses iterative fixed-point inversion:
        x_{k+1} = x_k + (y_desired - model(x_k))

    Args:
        desired_output: The target waveform we want the scope to produce.
        coeffs:         Fitted polynomial coefficients.
        poly_degree:    Polynomial degree.
        mem_depth:      Memory depth.
        amplitude:      Maximum amplitude for clipping.
        max_iterations: Max iterations for the fixed-point solver.
        tol:            Convergence tolerance.

    Returns:
        Pre-distorted input signal.
    """
    # Initialise with the desired output as a starting guess
    x = desired_output.copy()

    for i in range(max_iterations):
        y_pred = apply_memory_poly(x, coeffs, poly_degree, mem_depth)
        residual = desired_output - y_pred
        x = x + residual

        # Clip to valid range
        x = np.clip(x, 0, None)
        if np.max(np.abs(x)) > 0:
            x = (x / np.max(np.abs(x))) * amplitude

        if np.max(np.abs(residual)) < tol:
            print(f"  Inversion converged at iteration {i + 1}")
            break

    return x


def normalise_01(signal: np.ndarray) -> np.ndarray:
    """Scale signal to [0, 1]."""
    sig = np.asarray(signal, dtype=float)
    smin, smax = sig.min(), sig.max()
    if smax - smin == 0:
        return np.zeros_like(sig)
    return (sig - smin) / (smax - smin)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_memory_poly_optimisation(
    cfg: PulseShapeConfig,
) -> PulseShapeExperimentResult:
    """
    Execute memory polynomial predistortion:
        1. Run baseline experiment
        2. Fit memory polynomial from input → output
        3. Invert model to compute pre-distorted waveform
        4. Validate with a second experiment
    """
    theoretical = load_signal_from_path(cfg.get_theoretical_signal_path(), cfg.amplitude)

    runner = PulseShapeExperimentRunner(cfg, theoretical)

    try:
        # ── Step 1: Baseline ─────────────────────────────────────────────
        print("Step 1: Running baseline experiment...")
        baseline = runner.run()
        print(f"  Baseline MSE: {baseline.mse:.6e}")

        baseline.plot(
            output_dir=cfg.output_dir,
            filename="mempoly_01_baseline.png",
            title=f"Baseline — MSE = {baseline.mse:.4e}",
        )

        # ── Step 2: Fit memory polynomial ────────────────────────────────
        print(
            f"\nStep 2: Fitting memory polynomial "
            f"(degree={cfg.poly_degree}, depth={cfg.mem_depth})..."
        )
        coeffs = fit_memory_poly(
            input_signal=baseline._raw_waveform_sent,
            output_signal=baseline._raw_measured_signal,
            poly_degree=cfg.poly_degree,
            mem_depth=cfg.mem_depth,
        )
        num_coeffs = len(coeffs)
        print(f"  Fitted {num_coeffs} coefficients")

        # Save coefficients
        np.savetxt(
            cfg.output_dir / "mempoly_coefficients.csv",
            coeffs,
            delimiter=",",
        )

        # Evaluate model fit
        y_model = apply_memory_poly(
            baseline._raw_waveform_sent,
            coeffs,
            cfg.poly_degree,
            cfg.mem_depth,
        )
        model_mse = float(
            np.mean((y_model - baseline._raw_measured_signal) ** 2)
            / np.mean(baseline._raw_measured_signal**2)
        )
        print(f"  Model fit MSE: {model_mse:.6e}")

        # ── Step 3: Invert to find pre-distorted input ───────────────────
        print("\nStep 3: Computing pre-distorted waveform...")
        predistorted = invert_memory_poly(
            desired_output=theoretical,
            coeffs=coeffs,
            poly_degree=cfg.poly_degree,
            mem_depth=cfg.mem_depth,
            amplitude=cfg.amplitude,
        )

        # Save pre-distorted waveform (normalised)
        np.savetxt(
            cfg.output_dir / "mempoly_predistorted.csv",
            normalise_01(predistorted),
            delimiter=",",
        )

        # ── Step 4: Validation experiment ────────────────────────────────
        print("\nStep 4: Running validation experiment with pre-distorted waveform...")
        runner.waveform = predistorted
        validation = runner.run()
        print(f"  Validation MSE: {validation.mse:.6e}")
        print(
            f"  Improvement: {baseline.mse:.4e} → {validation.mse:.4e} "
            f"({(1 - validation.mse / baseline.mse) * 100:.1f}%)"
        )

        validation.plot(
            output_dir=cfg.output_dir,
            filename="mempoly_02_validation.png",
            title=(f"Memory Polynomial — MSE = {validation.mse:.4e} (was {baseline.mse:.4e})"),
        )

        # Save optimised waveform
        np.savetxt(
            cfg.output_dir / "mempoly_optimised_waveform.csv",
            normalise_01(predistorted),
            delimiter=",",
        )
        print(f"\nSaved results to {cfg.output_dir}")

        return validation

    finally:
        runner.close()


def main():
    config_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else SCRIPT_DIR / "config_pulse_experiment.ini"
    )

    print(f"Loading config: {config_path}")
    cfg = PulseShapeConfig(config_path)
    print(f"Output directory: {cfg.output_dir}")

    result = run_memory_poly_optimisation(cfg)
    print(f"\nFinal MSE: {result.mse:.6e}")


if __name__ == "__main__":
    main()
