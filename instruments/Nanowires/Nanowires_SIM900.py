"""
A wrapper class for talking to the nanowires SIM900 module
via a serial port.

Created on 7 May 2016

@author: Tom Barrett
"""

import time

import serial


class NanowiresSIM900mMainframe(serial.Serial):
    def __init__(self, port="COM1", detector_ports=None, timeout=3, **kwargs):
        if detector_ports is None:
            detector_ports = range(1, 9)

        print(f"Opening serial connection to nanowires (SIM900m) mainframe on port {port}...")
        serial.Serial.__init__(
            self,
            port=port,
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=timeout,
        )
        print("...connection {}".format("successful" if self.is_open else "failed"))

    def _write(self, string):
        return serial.Serial.write(self, string + "\r\n")

    def _read(self, size=1):
        out = b""
        while self.in_waiting > 0:
            out += serial.Serial.read(self, size=size)
        return out

    def _query(self, string, delay=1):
        """Write a query and return the result after a designated delay (1s by default)."""
        self.write(string)
        time.sleep(delay)
        return self.read()

    def _close(self):
        serial.Serial.close(self)
        print("Serial connection to nanowires (SIM900m) mainframe closed")


class NanowireDetectorSIM928m(serial.Serial):
    def __init__(self, port, status=None, voltage=None):

        self.port = port
        self.status = status
        self.voltage = voltage


# (Command, queryed, args)


class SerialDeviceCommands:
    # Interface Commands
    IDENTITY = "*IDN", True, None

    def generate(self, command, query=False, *args):
        cmd = str(command[0])

        if command[1] not in (query, None):
            raise SerialCommandError(
                "Command {} {} be queried.".format(cmd, "can" if command[1] else "can not")
            )

        if query:
            cmd += "?"

        if command[2] and not args:
            raise SerialCommandError(f"Command {cmd} requires arguments")
        if not command[2] and args != []:
            raise SerialCommandError(f"Command {cmd} can not take arguments")

        if args != []:
            cmd += " " + ",".join(map(str, args))

        return cmd


class NanowiresSIM900mMainframeCommands(SerialDeviceCommands):
    # Communication commands
    SEND_TO_PORT_TERMINATED = "SNDT", False, True
    SEND_TO_PORT = "SEND", False, True
    BROADCAST_TO_ALL_PORTS = "BRDC", False, True
    BROADCAST_TO_ALL_PORTS_TERMINATED = "BRDT", False, True
    GET_BYTES_FROM_PORT = "GETN", True, True

    # Configuration commands
    BROADCAST_ENABLE = "BRER", None, True
    INPUT_BYTES_WAITING_ON_PORT = "NINP", True, True
    OUTPUT_BYTES_WAITING_ON_PORT = "NOUT", True, True


class NanowireDetectorSIM928mCommands(SerialDeviceCommands):
    # Output commands
    VOLTAGE = "VOLT", None, None
    OUTPUT_ON = "OPON", False, False
    OUTPUT_OFF = "OPOF", False, False
    EXCITATION = "EXON", None, None


class SerialCommandError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
