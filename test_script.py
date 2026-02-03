from classes.ExperimentalConfigs import Waveform, AwgConfiguration
from lab_control_functions.awg_control_functions_psh import run_awg


if __name__ == "__main__":
    # Test the functionality of the Waveform class
    waveform_file = r"waveforms/marina/zeros/zero_40.csv"
    mod_frequency = 124000000
    phases = []

    waveform = Waveform(waveform_file, mod_frequency, phases)

    awg_config = AwgConfiguration(
        sample_rate=1e9,

    print(waveform.get_profile())
    print(waveform.get_n_samples())