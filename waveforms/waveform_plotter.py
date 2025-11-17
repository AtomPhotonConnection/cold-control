import matplotlib.pyplot as plt
import pandas as pd

if __name__ == "__main__":
    stokes_path = r"C:\Users\LabUser\Documents\cold-control\waveforms\pulse_shaping_exp\stirap\standard_1000ns_stokes.csv"
    pump_path = r"C:\Users\LabUser\Documents\cold-control\waveforms\pulse_shaping_exp\stirap\standard_1000ns_pump.csv"


    df = pd.read_csv(stokes_path,\
                      sep=None, engine='python', header=None)  # don't treat first row as header
    if df.shape[0] == 1 and df.shape[1] > 1:  # single row of values → convert to a column
        df = df.T
    df = df.apply(pd.to_numeric, errors='coerce').dropna(axis=1, how='all')
    df.plot(legend=False)
    plt.xlabel("Index")
    plt.ylabel("Value")
    plt.show()