# single_pass_rescaled_correction.py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import os

def read_vector_csv(path):
    df = pd.read_csv(path, header=None)
    return df.values.flatten().astype(float)

def gaussian(x, amp, mean, std):
    return amp * np.exp(-((x - mean)**2) / (2 * (std**2 + 1e-12)))

def multi_gaussian(x, *params):
    y = np.zeros_like(x, dtype=float)
    n = len(params) // 3
    for i in range(n):
        amp, mean, std = params[3*i:3*i+3]
        y += gaussian(x, amp, mean, std)
    return y

def fit_gaussians_linear(x, y_diff, num_bands, maxfev=100000):
    n = len(x)
    if n < 3:
        raise ValueError("Too few points to fit.")
    p0 = []
    step = max(1, n // num_bands)
    for i in range(num_bands):
        s = i*step
        e = min(n, (i+1)*step)
        seg = y_diff[s:e]
        xseg = x[s:e]
        if len(seg) == 0:
            amp0 = 0.0
            mean0 = float(n//2)
            std0 = max(n/(4*num_bands), 1.0)
        else:
            idx_local = int(np.argmax(np.abs(seg)))
            amp0 = float(seg[idx_local])
            mean0 = float(xseg[idx_local])
            std0 = max((xseg[-1] - xseg[0]) / 4.0, 1.0)
        p0.extend([amp0, mean0, std0])

    xmin, xmax = float(np.min(x)), float(np.max(x))
    lower = []
    upper = []
    for _ in range(num_bands):
        lower += [-np.inf, xmin, 1e-6]
        upper += [ np.inf, xmax, (xmax-xmin) or 1.0]

    popt, _ = curve_fit(multi_gaussian, x, y_diff, p0=p0, bounds=(lower, upper), maxfev=maxfev)
    return popt.reshape(num_bands, 3)

def rescale_readout_to_reference(readout, reference):
    A = np.vstack([readout, np.ones_like(readout)]).T
    sol, *_ = np.linalg.lstsq(A, reference, rcond=None)
    a, b = float(sol[0]), float(sol[1])
    return a, b

def single_pass_rescaled_correction(reference_path, readout_path, num_bands=6, save_prefix=r"C:\pulse_shaping_data\optimisation_results\2026-02-11"):
    # 1) Read vectors
    ref = read_vector_csv(reference_path)
    read_raw = read_vector_csv(readout_path)

    # 2) resample readout to reference length if needed
    n_ref = len(ref)
    if len(read_raw) != n_ref:
        x_read = np.linspace(0, n_ref-1, len(read_raw))
        x_ref = np.arange(n_ref)
        read_resampled = np.interp(x_ref, x_read, read_raw)
    else:
        x_ref = np.arange(n_ref)
        read_resampled = read_raw.copy()

    # treat reference vector as initial input baseline
    input_vec = ref.copy()

    # 3) compute scaling (a,b) and scaled readout
    a, b = rescale_readout_to_reference(read_resampled, ref)
    read_scaled = a * read_resampled + b
    print(f"Scaling (applied to raw readout): a = {a:.6f}, b = {b:.6f}")

    # 4) compute difference and initial RMSE
    diff = ref - read_scaled
    rmse_before = np.sqrt(np.mean(diff**2))
    print(f"RMSE before correction (on scaled readout): {rmse_before:.6e}")

    # 5) fit gaussians to diff (on index axis)
    x = x_ref
    gauss_params = fit_gaussians_linear(x, diff, num_bands)
    print("Fitted Gaussian bands (amp, mean_index, stddev) on SCALED readout:")
    for i, (amp, mean, std) in enumerate(gauss_params, start=1):
        print(f"  band {i}: amp={amp:.6f}, mean={mean:.2f}, std={std:.3f}")

    # 6) build correction in scaled-readout space (C_scaled)
    C_scaled = np.zeros_like(read_scaled, dtype=float)
    for amp, mean, std in gauss_params:
        C_scaled += gaussian(x, amp, mean, std)

    # 7) apply correction to scaled readout
    corrected_read_scaled = read_scaled + C_scaled

    # 8) map correction back to original readout space: C_orig = C_scaled / a
    if abs(a) < 1e-9:
        # avoid division by zero: assume mapping is 1:1 if a is essentially zero (degenerate)
        print("Warning: scale a is extremely small; mapping correction back divided by 'a' is unstable.")
        C_orig = C_scaled.copy()  # fallback (best-effort)
    else:
        C_orig = C_scaled / a

    # 9) apply mapped correction to original readout and input
    corrected_read_orig = read_resampled + C_orig
    corrected_input = input_vec + C_orig  # assume input→raw readout is 1:1 for this test

    # 10) recompute scaling and final RMSE (optional)
    a2, b2 = rescale_readout_to_reference(corrected_read_orig, ref)
    corrected_read_scaled_after = a2 * corrected_read_orig + b2
    rmse_after = np.sqrt(np.mean((ref - corrected_read_scaled_after)**2))
    print(f"After correction: recomputed scale a2={a2:.6f}, b2={b2:.6f}, RMSE={rmse_after:.6e}")

    # 11) save outputs
    os.makedirs(os.path.dirname(save_prefix) or ".", exist_ok=True)
    corrected_input_path = f"{save_prefix}_corrected_input.csv"
    corrected_read_scaled_path = f"{save_prefix}_corrected_read_scaled.csv"
    corrected_read_orig_path = f"{save_prefix}_corrected_read_orig.csv"
    plot_path = f"{save_prefix}_plot.png"

    np.savetxt(corrected_input_path, corrected_input, delimiter=",")
    # np.savetxt(corrected_read_scaled_path, corrected_read_scaled, delimiter=",")
    # np.savetxt(corrected_read_orig_path, corrected_read_orig, delimiter=",")

    print(f"Saved corrected input -> {corrected_input_path}")
    print(f"Saved corrected readout (SCALED space) -> {corrected_read_scaled_path}")
    print(f"Saved corrected readout (ORIG space resampled) -> {corrected_read_orig_path}")

    # 12) Plot everything
    plt.figure(figsize=(10,4))
    plt.plot(x, ref, '--', label="Reference (and initial input baseline)")
    plt.plot(x, read_resampled, ':', alpha=0.6, label="Original readout (resampled)")
    plt.plot(x, read_scaled, '-', color='orange', alpha=0.8, label=f"Scaled readout (a*raw+b), a={a:.3f}, b={b:.3f}")
    plt.plot(x, C_scaled, color='green', linewidth=1, alpha=0.9, label="Correction applied (in SCALED space)")
    plt.plot(x, corrected_read_scaled, color='darkblue', linewidth=1, label="Corrected readout (SCALED space)")
    plt.plot(x, corrected_read_orig, color='magenta', linewidth=1, alpha=0.7, label="Corrected readout (ORIG space)")
    plt.legend()
    plt.xlabel("Sample index")
    plt.ylabel("Amplitude")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    # plt.savefig(plot_path, dpi=150)
    # plt.close()
    plt.show()
    print(f"Saved diagnostic plot -> {plot_path}")

    return {
        "a": a,
        "b": b,
        "gauss_params_scaled_space": gauss_params,
        "C_scaled": C_scaled,
        "C_orig": C_orig,
        "rmse_before": rmse_before,
        "rmse_after": rmse_after,
        "corrected_input_path": corrected_input_path,
        "corrected_read_scaled_path": corrected_read_scaled_path,
        "corrected_read_orig_path": corrected_read_orig_path,
        "plot_path": plot_path
    }

# -----------------------
# Example usage: edit these paths and run
# -----------------------
if __name__ == "__main__":
    reference_path = r"C:\Users\LabUser\Documents\cold-control\waveforms\pulse_shaping_exp\stirap\standard_200ns_pump.csv"   # also used as initial input
    readout_path = r"C:\pulse_shaping_data\optimisation_results\2026-02-11\15-50\baseline_measured_signal.csv"       # measured output
    out = single_pass_rescaled_correction(reference_path, readout_path, num_bands=10, save_prefix=r"C:\pulse_shaping_data\optimisation_results\2026-02-11\\")
    print("Done. Summary:")
    print(f"scale a = {out['a']:.6f}, offset b = {out['b']:.6f}")
    print(f"rmse before = {out['rmse_before']:.6e}, rmse after = {out['rmse_after']:.6e}")
