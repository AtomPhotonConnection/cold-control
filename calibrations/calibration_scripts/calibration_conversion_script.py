# import pyvisa as visa
from pathlib import Path

from classes.config_readers import ConfigReader, DaqReader
from classes.daq import DAQChannel

config_reader = ConfigReader(Path.cwd() / "configs" / "rootConfig.ini")
daq_config_fname = (
    config_reader.get_daq_config_fname()
)  # gets the name of the config file for the DAQ cards
daq_reader = DaqReader(daq_config_fname)

channels: list[DAQChannel] = []
for _, v in daq_reader.config["DAQ channels"].items():
    channel_args: tuple[int, str, tuple[float, float], float, bool, str] = (
        int(v["chNum"]),  # chNum (int)
        str(v["chName"]),  # chName (str)
        (float(v["chLimits"][0]), float(v["chLimits"][1])),  # chLimits (tuple[float,float])
        float(v["default value"]),  # default value (float)
        bool(v["UIvisible"]),  # UIvisible (bool) or use v['UIvisible'] if already bool
        str(v["calibrationFname"]),  # calibrationFname (str)
    )
    channels.append(DAQChannel(*channel_args))

# print(channels)


def main_loop():
    print("\n\n**Starting program to convert between voltages and calibration values**\n")
    print("enter the number of the channel to find a value for:")
    ch_num = input("")

    try:
        ch_num = int(ch_num)
    except ValueError:
        print("Invalid channel number")
        if ch_num in ["x", "e", "q", "quit", "exit"]:
            return
        main_loop()
        return

    calib_from_v = calib_to_v = None

    for channel in channels:
        # print(channel.chNum)
        if channel.chNum == ch_num:
            if getattr(channel, "calibration", None) is not None:
                calib_to_v = channel.calibration.to_voltage
                calib_from_v = channel.calibration.from_voltage
            print(f"This channel is {channel.chName}")

    if calib_to_v is None or calib_from_v is None:
        print("channel not found")
        main_loop()
        return

    print("Do you want to find a voltage (v) or a calibration value (c)?")
    conv_type = input("").lower()
    if conv_type in ["v", "volts", "voltage"]:
        conv_type = 0
    elif conv_type in ["c", "calib", "calibration"]:
        conv_type = 1
    else:
        print("invalid conversion type")
        main_loop()
        return

    print("What value do you want to convert?")
    value = input("")
    try:
        value = float(value)
    except ValueError:
        print("Invalid value to convert")
        main_loop()
        return

    print("result:")
    if conv_type:
        print(calib_from_v(value))
    else:
        print(calib_to_v(value))

    main_loop()
    return


main_loop()


# cool_upper_freq =r"C:\Users\apc\Documents\Python Scripts\Cold Control Heavy\calibrations\jan\cool_upper_freq.txt"
# cool_lower_freq =r"C:\Users\apc\Documents\Python Scripts\Cold Control Heavy\calibrations\jan\cool_lower_freq.txt"
# cool_centre_freq = r"C:\Users\apc\Documents\Python Scripts\Cold Control Heavy\calibrations\jan\cool_centre_freq.txt"
# filename = cool_lower_freq
# r"C:\Users\apc\Documents\Python Scripts\Cold Control Heavy\calibrations\jan\cool_lower_freq.txt"
# value = 102


# def calibrate_from_txt(calibrationFname, reReadIn = r'([\+|\-]?[\d|\.]+)[ \t]*([\+|\-]?[\d|\.]+)'):


#     #print("WARNING: calibrate_from_txt() METHOD IS DEPRECATED. USE CALIBRATE WITH CSV FILES INSTEAD.")

#     vData, calData = [], []
#     with open(calibrationFname) as f:
#         calibrationUnits = re.split(r'[ \t]*', f.readline())[-1].strip()
#         for line in f.readlines():
#             match = re.match(reReadIn, line.strip())
#             if match:
#                 vData.append(float(match.group(1)))
#                 calData.append(float(match.group(2)))

#     if calData[0] <= calData[-1]:
#         calibrationToVFunc = lambda x: np.interp(x, calData, vData)
#     else:
#         calibrationToVFunc = lambda x: np.interp(x, [x for x in reversed(calData)], [x for x in reversed(vData)])

#     if vData[0] <= vData[-1]:
#         calibrationFromVFunc = lambda x: np.interp(x, vData, calData)
#     else:
#         calibrationFromVFunc = lambda x: np.interp(x, [x for x in reversed(vData)], [x for x in reversed(calData)])

#     return calibrationToVFunc, calibrationFromVFunc

# calib_to_V, calib_from_V = calibrate_from_txt(filename)
