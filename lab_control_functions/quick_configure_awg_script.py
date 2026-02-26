import logging

from classes.experimental_configs import AwgConfiguration, Waveform
from instruments.WX218x.awg_manager import AWGManager

# ensure logging goes to the right place
logging.basicConfig(
    level=logging.DEBUG,
    filename=r"C:\pulse_shaping_data\logging\test_script2.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
)

_waveforms = [
    Waveform(r"waveforms\new_Jan\tophat\tophat_1000ns.csv", 74e6, [(0, 0)]),
    Waveform(r"waveforms\new_Jan\tophat\tophat_1000ns.csv", 55e6, [(0, 0)]),
    Waveform(r"waveforms\marina\zeros\zero_1000.csv", 0, [(0, 0)]),
    Waveform(r"waveforms\pulse_shaping_exp\stirap\standard_200ns_pump.csv", 61e6, [(0, 0)]),
    Waveform(r"waveforms\pulse_shaping_exp\stirap\standard_200ns_stokes.csv", 80e6, [(0, 0)]),
]

awg_config = AwgConfiguration(
    waveform_sequence=[[2, 3], [0, 4], [1]],
    waveforms=_waveforms,
    sample_rate=1.25e9,
    burst_count=1,
    waveform_output_channels=[1, 2, 3],
    waveform_output_channel_lags=[0.0, 0.0, 0.0],
    marker_width=1e-9,
)

awg_config_simple = AwgConfiguration(
    waveform_sequence=[[0]],
    waveforms=[_waveforms[0]],
    sample_rate=1.25e9,
    burst_count=1,
    waveform_output_channels=[1],
    waveform_output_channel_lags=[0.0],
    marker_width=1e-9,
)

awg_config_justch3 = AwgConfiguration(
    waveform_sequence=[[0]],
    waveforms=[_waveforms[0]],
    sample_rate=1.25e9,
    burst_count=1,
    waveform_output_channels=[3],
    waveform_output_channel_lags=[0.0],
    marker_width=1e-9,
)


if __name__ == "__main__":
    awg = None
    try:
        # plt.plot(_waveforms[0].get(sample_rate=awg_config.sample_rate))
        # plt.show()

        awg = AWGManager()
        awg.upload_and_arm(awg_config)

    finally:
        if awg is not None:
            awg.close()
