# Changes to pulse shape optimisation

## Minor changes

- The plots and optimised waveform should be saved to pulse_shaping_data/optimisation_results/yyyy-mm-dd/hh-mm/
- The results csvs, optimised csv, and plotted waveforms should all be normalised to 1. The measured waveform should also be scaled to range between 0 and 1.

## Major changes

- I want to be able to run optimisation experiments with more complex optmisation procedures. One option would be for these optimisation procedures to be defined in a file such that they can be imported into the main script, but if it works better then each optimisation method could have its own script.
- First I want an iterative feedback procedure that does the following:
    1. Run an experiment with the current waveform
    2. Compute the error between the measured and theoretical waveform
    3. Compute a correction to the waveform based on the error
    4. Update the waveform with the correction
    5. Repeat until the error is below a certain threshold or a maximum number of iterations is reached

- I also want an optimisation script that uses the M-LOOP method, using Bayseian optimisation to find the optimal waveform.

- I also want an optimisation method using memory polynomials to find the optimal waveform.
