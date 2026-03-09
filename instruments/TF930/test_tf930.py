"""
Created on 17 Feb 2016

@author: Tom Barrett
"""

import re
import time
from pathlib import Path

import serial

from instruments.TF930 import tf930_manager

target_file_name = r"C:\Users\apc\Desktop\TF930monitoring.txt"
target_file_path = Path(target_file_name)

try:
    counter = tf930_manager.TF930(port="COM5")
except serial.SerialException as err:
    print("Cannot find counter")
    raise err

i = 0

with target_file_path.open("w+") as f:
    while i < 1:
        output = counter.query("N?", delay=0.5)
        # Parse the output, once for units and once for values
        r = r"([\d|\.|e|\+]+)([a-zA-Z]*)\r\n"

        match = re.match(r, output)
        if match:
            freq, units = float(match.group(1)), match.group(2)

            # Just a hack to convert Hz to MHz as it's nicer.
            if units == "Hz":
                freq = freq / 10**6
                units = "MHz"

            print(f"TF930 is reading {freq}{units}")
            f.write(f"{time.strftime('%X')},{freq}\n")
        else:
            print("TF930 reading: N/A")

        time.sleep(10)
        i += 1
        print(i)

counter.close()
