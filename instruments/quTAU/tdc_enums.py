"""
Time-to-Digital Converter (TDC) Enumerations Module
This module defines enumeration classes for the quTAU TDC (Time-to-Digital Converter)
instrument. These enumerations represent various configuration and operational parameters
used when interfacing with TDC hardware devices.
Enumeration Classes:
    TdcDevTypeEnum: Device type identifiers for different TDC hardware variants.
    TdcFileFormatEnum: File format options for data export and storage.
    TdcSignalCondEnum: Signal conditioning modes for input signal processing.
    TdcSimTypeEnum: Simulation type modes for testing and development.
Created on: 22 Sep 2016
Original author: Tom Barrett
Updated by: Matt King
Last updated: 28/02/2026
"""

# from ctypes import *
from ctypes import (
    c_int,
)


class TdcDevTypeEnum:
    (DEVTYPE_1A, DEVTYPE_1B, DEVTYPE_1C, DEVTYPE_NONE) = map(int, range(4))


class TdcFileFormatEnum:
    (FORMAT_ASCII, FORMAT_BINARY, FORMAT_COMPRESSED, FORMAT_RAW, FORMAT_NONE) = map(c_int, range(5))


class TdcSignalCondEnum:
    (SCOND_TTL, SCOND_LVTTL, SCOND_NIM, SCOND_MISC, SCOND_NONE) = map(c_int, range(5))


class TdcSimTypeEnum:
    (SIM_FLAT, SIM_NORMAL, SIM_NONE) = map(c_int, range(3))
