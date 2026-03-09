"""
A wrapper class for using a Gamma Vacuum Digital SPC ion getter pump
via a serial port.

Created on 7 May 2016

@author: Tom Barrett
"""  # noqa: N999

import time

import serial


class GammaVacuumDigitalSPC(serial.Serial):
    def __init__(self, port="COM1", timeout=3, **kwargs):
        print(f"Opening serial connection to ion pump on port {port}...")
        serial.Serial.__init__(
            self,
            port=port,
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=timeout,
        )
        print(f"...connection {'successful' if self.is_open else 'failed'}")

    def write(self, string):
        return serial.Serial.write(self, (string + "\n").encode())

    def read(self, size=1):
        out = b""
        while self.in_waiting > 0:
            out += serial.Serial.read(self, size=size)
        return out

    def query(self, string, delay=1):
        """Write a query and return the result after a designated delay (1s by default)."""
        self.write(string)
        time.sleep(delay)
        return self.read()

    def close(self):
        serial.Serial.close(self)
        print("Serial connection to ion pump closed")
