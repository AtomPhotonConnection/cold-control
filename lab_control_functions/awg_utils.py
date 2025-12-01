import numpy as np


def make_playable_waveform(data, tol=1e-12, eps=1e-4):
    """Ensure a waveform is playable by the AWG.

    Some AWG drivers or firmware may treat a waveform that is completely constant
    (every sample exactly equal) as invalid or optimize it away. For example,
    a CSV containing only zeros is a useful "wait" but can be silently ignored
    by the hardware.

    To avoid this, if the input array is constant we break the degeneracy by
    making a tiny alternating perturbation around the constant value while
    preserving the mean. The perturbation is clipped to [-1, 1] to keep data in
    the valid AWG range.

    Args:
        data: iterable of numeric samples (list or numpy array)
        tol: tolerance for constant detection (default 1e-12)
        eps: perturbation magnitude to apply to alternate samples (default 1e-4)

    Returns:
        A list of numeric samples guaranteed not to be completely constant.
    """
    arr = np.asarray(data, dtype=float)
    if arr.size == 0:
        return []

    # If all values equal within tolerance, create tiny alternating pattern
    if np.allclose(arr, arr[0], atol=tol, rtol=0):
        v = float(arr[0])
        # Choose a small epsilon relative to the AWG amplitude range [-1,1]
        perturb = float(eps)

        # Build alternating pattern v + perturb, v - perturb
        new = arr.copy()
        new[::2] = np.clip(v + perturb, -1.0, 1.0)
        if new.size > 1:
            new[1::2] = np.clip(v - perturb, -1.0, 1.0)
        # If size is 1, push a tiny offset (can't create alternating) — keep value inside bounds
        else:
            new[0] = np.clip(v + perturb, -1.0, 1.0)

        # Ensure the mean is unchanged (up to numerical precision)
        if arr.size > 1:
            mean_before = arr.mean()
            mean_after = new.mean()
            correction = mean_before - mean_after
            # spread small correction evenly over samples
            new += correction
            new = np.clip(new, -1.0, 1.0)

        return new.tolist()

    return data if isinstance(data, list) else arr.tolist()
