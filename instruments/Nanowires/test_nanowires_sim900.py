"""
Created on 8 Feb 2017

@author: Tom Barrett
"""

import serial

from instruments.GammaVacuumDigitalSPC import GammaVacuumDigitalSPC

try:
    ion_pump = GammaVacuumDigitalSPC.GammaVacuumDigitalSPC(port="COM1")
except serial.SerialException as err:
    print("Pump could not be found")
    raise err
#
# print ionPump.query(r'7e 20 30 35 20 30 31 20 30 30 0D')
# print ionPump.query(r'~ 00 01 00\r')
print(ion_pump.query("VOLT?"))

ion_pump.close()
print("...finished!")
