import matplotlib.pyplot as plt
import pandas as pd

if __name__ == "__main__":
    if False:
        stokes_path = r"C:\Users\LabUser\Documents\cold-control\waveforms\pulse_shaping_exp\stirap\sin_700ns_stokes.csv"
        pump_path = r"C:\Users\LabUser\Documents\cold-control\waveforms\pulse_shaping_exp\stirap\sin_700ns_pump.csv"


        df = pd.read_csv(stokes_path,\
                        sep=None, engine='python', header=None)  # don't treat first row as header
        if df.shape[0] == 1 and df.shape[1] > 1:  # single row of values → convert to a column
            df = df.T
        df = df.apply(pd.to_numeric, errors='coerce').dropna(axis=1, how='all')
        df.plot(legend=False)
        plt.xlabel("Index")
        plt.ylabel("Value")
        plt.show()
    else:
        data_path = r"C:\Users\LabUser\Documents\cold-control\waveforms\pulse_shaping_exp\stirap\test_output_waveform.csv"
        plt.plot(pd.read_csv(data_path, header=None))
        plt.show()