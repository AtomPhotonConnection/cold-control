"""
Module containing low-level DAQ objects.

Created on 2 Apr 2016. Revised 8 Jan 2025. Refactored Feb 2026.

@author: tombarrett, Matt King

DLL-dependent code (DAQ2502, dll prototypes) has been moved to DAQ_dll.py.
This module can be imported safely on machines without the D2K-Dask64 DLL.
"""

import functools
import operator
import re
from ctypes import c_double, c_float, c_long, c_short, c_ubyte, c_ulong, c_ushort
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Conditional import of hardware-dependent code from DAQ_dll.py
# In development mode (or on machines without the DLL), these will be stubs.
# ---------------------------------------------------------------------------
if TYPE_CHECKING:
    from .DAQ_dll import DAQ2502, Daq2502Exception, dll
else:
    try:
        from classes.DAQ_dll import DAQ2502, Daq2502Exception, dll
    except (OSError, ImportError):
        dll = None  # type: ignore[assignment]

        class _DAQ2502: ...

        class _Daq2502Error(Exception): ...

        DAQ2502 = _DAQ2502
        Daq2502Exception = _Daq2502Error

        print("[DAQ] D2K-Dask64 DLL not available — running with stub DAQ2502.")

# DAQ2000 Device
DAQ_2010 = 1
DAQ_2205 = 2
DAQ_2206 = 3
DAQ_2005 = 4
DAQ_2204 = 5
DAQ_2006 = 6
DAQ_2501 = 7
DAQ_2502 = 8
DAQ_2208 = 9
DAQ_2213 = 10
DAQ_2214 = 11
DAQ_2016 = 12
DAQ_2020 = 13
DAQ_2022 = 14

# DASK Data Types
I16 = c_short
I32 = c_long
F32 = c_float
F64 = c_double
U8 = c_ubyte
U16 = c_ushort
U32 = c_ulong

MAX_CARD = 32

# Error Number
warning_code = {
    0: "NoError",
    -1: "ErrorUnknownCardType",
    -2: "ErrorInvalidCardNumber",
    -3: "ErrorTooManyCardRegistered",
    -4: "ErrorCardNotRegistered",
    -5: "ErrorFuncNotSupport",
    -6: "ErrorInvalidIoChannel",
    -7: "ErrorInvalidAdRange",
    -8: "ErrorContIoNotAllowed",
    -9: "ErrorDiffRangeNotSupport",
    -10: "ErrorLastChannelNotZero",
    -11: "ErrorChannelNotDescending",
    -12: "ErrorChannelNotAscending",
    -13: "ErrorOpenDriverFailed",
    -14: "ErrorOpenEventFailed",
    -15: "ErrorTransferCountTooLarge",
    -16: "ErrorNotDoubleBufferMode",
    -17: "ErrorInvalidSampleRate",
    -18: "ErrorInvalidCounterMode",
    -19: "ErrorInvalidCounter",
    -20: "ErrorInvalidCounterState",
    -21: "ErrorInvalidBinBcdParam",
    -22: "ErrorBadCardType",
    -23: "ErrorInvalidDaRefVoltage",
    -24: "ErrorAdTimeOut",
    -25: "ErrorNoAsyncAI",
    -26: "ErrorNoAsyncAO",
    -27: "ErrorNoAsyncDI",
    -28: "ErrorNoAsyncDO",
    -29: "ErrorNotInputPort",
    -30: "ErrorNotOutputPort",
    -31: "ErrorInvalidDioPort",
    -32: "ErrorInvalidDioLine",
    -33: "ErrorContIoActive",
    -34: "ErrorDblBufModeNotAllowed",
    -35: "ErrorConfigFailed",
    -36: "ErrorInvalidPortDirection",
    -37: "ErrorBeginThreadError",
    -38: "ErrorInvalidPortWidth",
    -39: "ErrorInvalidCtrSource",
    -40: "ErrorOpenFile",
    -41: "ErrorAllocateMemory",
    -42: "ErrorDaVoltageOutOfRange",
    -43: "ErrorInvalidSyncMode",
    -44: "ErrorInvalidBufferID",
    -45: "ErrorInvalidCNTInterval",
    -46: "ErrorReTrigModeNotAllowed",
    -47: "ErrorResetBufferNotAllowed",
    -48: "ErrorAnaTriggerLevel",
    -49: "ErrorDAQEvent",
    -50: "ErrorInvalidCounterValue",
    -51: "ErrorOffsetCalibration",
    -52: "ErrorGainCalibration",
    -53: "ErrorCountOutofSDRAMSize",
    -54: "ErrorNotStartTriggerModule",
    -55: "ErrorInvalidRouteLine",
    -56: "ErrorInvalidSignalCode",
    -57: "ErrorInvalidSignalDirection",
    -58: "ErrorTRGOSCalibration",
    -59: "ErrorNoSDRAM",
    -60: "ErrorIntegrationGain",
    -61: "ErrorAcquisitionTiming",
    -62: "ErrorIntegrationTiming",
    -70: "ErrorInvalidTimeBase",
    -71: "ErrorUndefinedParameter",
    -110: "ErrorCalAddress",
    -111: "ErrorInvalidCalBank",
    -201: "ErrorConfigIoctl",
    -202: "ErrorAsyncSetIoctl",
    -203: "ErrorDBSetIoctl",
    -204: "ErrorDBHalfReadyIoctl",
    -205: "ErrorContOPIoctl",
    -206: "ErrorContStatusIoctl",
    -207: "ErrorPIOIoctl",
    -208: "ErrorDIntSetIoctl",
    -209: "ErrorWaitEvtIoctl",
    -210: "ErrorOpenEvtIoctl",
    -211: "ErrorCOSIntSetIoctl",
    -212: "ErrorMemMapIoctl",
    -213: "ErrorMemUMapSetIoctl",
    -214: "ErrorCTRIoctl",
    -215: "ErrorGetResIoctl",
    -216: "ErrorCalIoctl",
    -217: "ErrorPMIntSetIoctl",
    -301: "ErrorNotSuportOldDriver",
}

# NoError = 0
# ErrorUnknownCardType = -1
# ErrorInvalidCardNumber = -2
# ErrorTooManyCardRegistered = -3
# ErrorCardNotRegistered = -4
# ErrorFuncNotSupport = -5
# ErrorInvalidIoChannel = -6
# ErrorInvalidAdRange = -7
# ErrorContIoNotAllowed = -8
# ErrorDiffRangeNotSupport = -9
# ErrorLastChannelNotZero = -10
# ErrorChannelNotDescending = -11
# ErrorChannelNotAscending = -12
# ErrorOpenDriverFailed = -13
# ErrorOpenEventFailed = -14
# ErrorTransferCountTooLarge = -15
# ErrorNotDoubleBufferMode = -16
# ErrorInvalidSampleRate = -17
# ErrorInvalidCounterMode = -18
# ErrorInvalidCounter = -19
# ErrorInvalidCounterState = -20
# ErrorInvalidBinBcdParam = -21
# ErrorBadCardType = -22
# ErrorInvalidDaRefVoltage = -23
# ErrorAdTimeOut = -24
# ErrorNoAsyncAI = -25
# ErrorNoAsyncAO = -26
# ErrorNoAsyncDI = -27
# ErrorNoAsyncDO = -28
# ErrorNotInputPort = -29
# ErrorNotOutputPort = -30
# ErrorInvalidDioPort = -31
# ErrorInvalidDioLine = -32
# ErrorContIoActive = -33
# ErrorDblBufModeNotAllowed = -34
# ErrorConfigFailed = -35
# ErrorInvalidPortDirection = -36
# ErrorBeginThreadError = -37
# ErrorInvalidPortWidth = -38
# ErrorInvalidCtrSource = -39
# ErrorOpenFile = -40
# ErrorAllocateMemory = -41
# ErrorDaVoltageOutOfRange = -42
# ErrorInvalidSyncMode = -43
# ErrorInvalidBufferID = -44
# ErrorInvalidCNTInterval  = -45
# ErrorReTrigModeNotAllowed = -46
# ErrorResetBufferNotAllowed = -47
# ErrorAnaTriggerLevel = -48
# ErrorDAQEvent = -49
# ErrorInvalidCounterValue = -50
# ErrorOffsetCalibration = -51
# ErrorGainCalibration = -52
# ErrorCountOutofSDRAMSize = -53
# ErrorNotStartTriggerModule = -54
# ErrorInvalidRouteLine = -55
# ErrorInvalidSignalCode = -56
# ErrorInvalidSignalDirection = -57
# ErrorTRGOSCalibration = -58
# ErrorNoSDRAM = -59
# ErrorIntegrationGain = -60
# ErrorAcquisitionTiming = -61
# ErrorIntegrationTiming = -62
# ErrorInvalidTimeBase = -70
# ErrorUndefinedParameter = -71
#
## Error number for calibration API
# ErrorCalAddress = -110
# ErrorInvalidCalBank = -111
#
## Error number for driver API
# ErrorConfigIoctl = -201
# ErrorAsyncSetIoctl = -202
# ErrorDBSetIoctl = -203
# ErrorDBHalfReadyIoctl = -204
# ErrorContOPIoctl = -205
# ErrorContStatusIoctl = -206
# ErrorPIOIoctl = -207
# ErrorDIntSetIoctl = -208
# ErrorWaitEvtIoctl = -209
# ErrorOpenEvtIoctl = -210
# ErrorCOSIntSetIoctl = -211
# ErrorMemMapIoctl = -212
# ErrorMemUMapSetIoctl = -213
# ErrorCTRIoctl = -214
# ErrorGetResIoctl = -215
# ErrorCalIoctl = -216
# ErrorPMIntSetIoctl = -217
# ErrorNotSuportOldDriver = -301

TRUE = 1
FALSE = 0

# Synchronous Mode
SYNCH_OP = 1
ASYNCH_OP = 2

# AD Range
AD_B_10_V = 1
AD_B_5_V = 2
AD_B_2_5_V = 3
AD_B_1_25_V = 4
AD_B_0_625_V = 5
AD_B_0_3125_V = 6
AD_B_0_5_V = 7
AD_B_0_05_V = 8
AD_B_0_005_V = 9
AD_B_1_V = 10
AD_B_0_1_V = 11
AD_B_0_01_V = 12
AD_B_0_001_V = 13
AD_U_20_V = 14
AD_U_10_V = 15
AD_U_5_V = 16
AD_U_2_5_V = 17
AD_U_1_25_V = 18
AD_U_1_V = 19
AD_U_0_1_V = 20
AD_U_0_01_V = 21
AD_U_0_001_V = 22
AD_B_2_V = 23
AD_B_0_25_V = 24
AD_B_0_2_V = 25
AD_U_4_V = 26
AD_U_2_V = 27
AD_U_0_5_V = 28
AD_U_0_4_V = 29

# DIO Port Direction
INPUT_PORT = 1
OUTPUT_PORT = 2

# DIO Line Direction
INPUT_LINE = 1
OUTPUT_LINE = 2

# Channel & Port
Channel_P1A = 0
Channel_P1B = 1
Channel_P1C = 2
Channel_P1CL = 3
Channel_P1CH = 4
Channel_P1AE = 10
Channel_P1BE = 11
Channel_P1CE = 12
Channel_P2A = 5
Channel_P2B = 6
Channel_P2C = 7
Channel_P2CL = 8
Channel_P2CH = 9
Channel_P2AE = 15
Channel_P2BE = 16
Channel_P2CE = 17
Channel_P3A = 10
Channel_P3B = 11
Channel_P3C = 12
Channel_P3CL = 13
Channel_P3CH = 14
Channel_P4A = 15
Channel_P4B = 16
Channel_P4C = 17
Channel_P4CL = 18
Channel_P4CH = 19
Channel_P5A = 20
Channel_P5B = 21
Channel_P5C = 22
Channel_P5CL = 23
Channel_P5CH = 24
Channel_P6A = 25
Channel_P6B = 26
Channel_P6C = 27
Channel_P6CL = 28
Channel_P6CH = 29

# -------- Constants for DAQ2000 --------------------
All_Channels = -1
BufferNotUsed = -1

# Constants for Analog trigger
# define analog trigger condition constants
Below_Low_level = 0x0000
Above_High_Level = 0x0100
Inside_Region = 0x0200
High_Hysteresis = 0x0300
Low_Hysteresis = 0x0400

# define analog trigger Dedicated Channel */
CH0ATRIG = 0x00
CH1ATRIG = 0x02
CH2ATRIG = 0x04
CH3ATRIG = 0x06
EXTATRIG = 0x01
ADCATRIG = 0x00  # used for DAQ_old-2205/2206

# Time Base
DAQ2K_IntTimeBase = 0x00
DAQ2K_ExtTimeBase = 0x01
DAQ2K_SSITimeBase = 0x02
DAQ2K_ExtTimeBase_AFI0 = 0x3
DAQ2K_ExtTimeBase_AFI1 = 0x4
DAQ2K_ExtTimeBase_AFI2 = 0x5
DAQ2K_ExtTimeBase_AFI3 = 0x6
DAQ2K_ExtTimeBase_AFI4 = 0x7
DAQ2K_ExtTimeBase_AFI5 = 0x8
DAQ2K_ExtTimeBase_AFI6 = 0x9
DAQ2K_ExtTimeBase_AFI7 = 0xA
DAQ2K_PXI_CLK = 0xC
DAQ2K_StarTimeBase = 0xD
DAQ2K_SMBTimeBase = 0xE

# Constants for AD
DAQ2K_AI_ADSTARTSRC_Int = 0x00
DAQ2K_AI_ADSTARTSRC_AFI0 = 0x10
DAQ2K_AI_ADSTARTSRC_SSI = 0x20
DAQ2K_AI_ADCONVSRC_Int = 0x00
DAQ2K_AI_ADCONVSRC_AFI0 = 0x04
DAQ2K_AI_ADCONVSRC_SSI = 0x08
DAQ2K_AI_ADCONVSRC_AFI1 = 0x0C
DAQ2K_AI_ADCONVSRC_AFI2 = 0x100
DAQ2K_AI_ADCONVSRC_AFI3 = DAQ2K_AI_ADCONVSRC_AFI2 + 0x100
DAQ2K_AI_ADCONVSRC_AFI4 = DAQ2K_AI_ADCONVSRC_AFI2 + 0x200
DAQ2K_AI_ADCONVSRC_AFI5 = DAQ2K_AI_ADCONVSRC_AFI2 + 0x300
DAQ2K_AI_ADCONVSRC_AFI6 = DAQ2K_AI_ADCONVSRC_AFI2 + 0x400
DAQ2K_AI_ADCONVSRC_AFI7 = DAQ2K_AI_ADCONVSRC_AFI2 + 0x500
DAQ2K_AI_ADCONVSRC_PFI0 = DAQ2K_AI_ADCONVSRC_AFI0

# AI Delay Counter SRC: only available for DAQ_old-250X
DAQ2K_AI_DTSRC_Int = 0x00
DAQ2K_AI_DTSRC_AFI1 = 0x10
DAQ2K_AI_DTSRC_GPTC0 = 0x20
DAQ2K_AI_DTSRC_GPTC1 = 0x30
DAQ2K_AI_TRGSRC_SOFT = 0x00
DAQ2K_AI_TRGSRC_ANA = 0x01
DAQ2K_AI_TRGSRC_ExtD = 0x02
DAQ2K_AI_TRSRC_SSI = 0x03
DAQ2K_AI_TRGMOD_POST = 0x00  # Post Trigger Mode
DAQ2K_AI_TRGMOD_DELAY = 0x08  # Delay Trigger Mode
DAQ2K_AI_TRGMOD_PRE = 0x10  # Pre-Trigger Mode
DAQ2K_AI_TRGMOD_MIDL = 0x18  # Middle Trigger Mode
DAQ2K_AI_ReTrigEn = 0x80
DAQ2K_AI_Dly1InSamples = 0x100
DAQ2K_AI_Dly1InTimebase = 0x000
DAQ2K_AI_MCounterEn = 0x400
DAQ2K_AI_TrgPositive = 0x0000
DAQ2K_AI_TrgNegative = 0x1000
DAQ2K_AI_TRGSRC_AFI0 = 0x10000
DAQ2K_AI_TRGSRC_AFI1 = DAQ2K_AI_TRGSRC_AFI0 + 0x10000
DAQ2K_AI_TRGSRC_AFI2 = DAQ2K_AI_TRGSRC_AFI0 + 0x20000
DAQ2K_AI_TRGSRC_AFI3 = DAQ2K_AI_TRGSRC_AFI0 + 0x30000
DAQ2K_AI_TRGSRC_AFI4 = DAQ2K_AI_TRGSRC_AFI0 + 0x40000
DAQ2K_AI_TRGSRC_AFI5 = DAQ2K_AI_TRGSRC_AFI0 + 0x50000
DAQ2K_AI_TRGSRC_AFI6 = DAQ2K_AI_TRGSRC_AFI0 + 0x60000
DAQ2K_AI_TRGSRC_AFI7 = DAQ2K_AI_TRGSRC_AFI0 + 0x70000
DAQ2K_AI_TRGSRC_PXIStar = DAQ2K_AI_TRGSRC_AFI0 + 0x90000
DAQ2K_AI_TRGSRC_SMB = DAQ2K_AI_TRGSRC_AFI0 + 0xA0000

# AI Reference ground
AI_RSE = 0x0000
AI_DIFF = 0x0100
AI_NRSE = 0x0200

# Constants for DA
# DA CH config constant
DAQ2K_DA_BiPolar = 0x1
DAQ2K_DA_UniPolar = 0x0
DAQ2K_DA_Int_REF = 0x0
DAQ2K_DA_Ext_REF = 0x1

# DA control constant
DAQ2K_DA_WRSRC_Int = 0x00
DAQ2K_DA_WRSRC_AFI1 = 0x01
DAQ2K_DA_WRSRC_SSI = 0x02
DAQ2K_DA_WRSRC_AFI0 = DAQ2K_DA_WRSRC_AFI1
DAQ2K_DA_WRSRC_PFI0 = DAQ2K_DA_WRSRC_AFI0

# DA group
DA_Group_A = 0x00
DA_Group_B = 0x04
DA_Group_AB = 0x08

# DA TD Counter SRC: only available for DAQ_old-250X
DAQ2K_DA_TDSRC_Int = 0x00
DAQ2K_DA_TDSRC_AFI0 = 0x10
DAQ2K_DA_TDSRC_GPTC0 = 0x20
DAQ2K_DA_TDSRC_GPTC1 = 0x30

# DA BD Counter SRC: only available for DAQ_old-250X
DAQ2K_DA_BDSRC_Int = 0x00
DAQ2K_DA_BDSRC_AFI0 = 0x40
DAQ2K_DA_BDSRC_GPTC0 = 0x80
DAQ2K_DA_BDSRC_GPTC1 = 0xC0

# DA trigger constant
DAQ2K_DA_TRGSRC_SOFT = 0x00
DAQ2K_DA_TRGSRC_ANA = 0x01
DAQ2K_DA_TRGSRC_ExtD = 0x02
DAQ2K_DA_TRSRC_SSI = 0x03
DAQ2K_DA_TRGMOD_POST = 0x00
DAQ2K_DA_TRGMOD_DELAY = 0x04
DAQ2K_DA_ReTrigEn = 0x20
DAQ2K_DA_Dly1InUI = 0x40
DAQ2K_DA_Dly1InTimebase = 0x00
DAQ2K_DA_Dly2InUI = 0x80
DAQ2K_DA_Dly2InTimebase = 0x00
DAQ2K_DA_DLY2En = 0x100
DAQ2K_DA_TrgPositive = 0x000
DAQ2K_DA_TrgNegative = 0x200

# DA stop mode
DAQ2K_DA_TerminateImmediate = 0
DAQ2K_DA_TerminateUC = 1
DAQ2K_DA_TerminateIC = 2
DAQ2K_DA_TerminateFIFORC = DAQ2K_DA_TerminateIC

# DA stop source : only available for DAQ_old-250X
DAQ2K_DA_STOPSRC_SOFT = 0
DAQ2K_DA_STOPSRC_AFI0 = 1
DAQ2K_DA_STOPSRC_ATrig = 2
DAQ2K_DA_STOPSRC_AFI1 = 3

# -------- Timer/Counter -----------------------------
# Counter Mode (8254)
TOGGLE_OUTPUT = 0  # Toggle output from low to high on terminal count
PROG_ONE_SHOT = 1  # Programmable one-shot
RATE_GENERATOR = 2  # Rate generator
SQ_WAVE_RATE_GENERATOR = 3  # Square wave rate generator
SOFT_TRIG = 4  # Software-triggered strobe
HARD_TRIG = 5  # Hardware-triggered strobe

# 16-bit binary or 4-decade BCD counter
BIN = 0
BCD = 1

# General Purpose Timer/Counter
# Counter Mode
SimpleGatedEventCNT = 0x01
SinglePeriodMSR = 0x02
SinglePulseWidthMSR = 0x03
SingleGatedPulseGen = 0x04
SingleTrigPulseGen = 0x05
RetrigSinglePulseGen = 0x06
SingleTrigContPulseGen = 0x07
ContGatedPulseGen = 0x08

# GPTC clock source
GPTC_GATESRC_EXT = 0x04
GPTC_GATESRC_INT = 0x00
GPTC_CLKSRC_EXT = 0x08
GPTC_CLKSRC_INT = 0x00
GPTC_UPDOWN_SEL_EXT = 0x10
GPTC_UPDOWN_SEL_INT = 0x00

# GPTC clock polarity
GPTC_CLKEN_LACTIVE = 0x01
GPTC_CLKEN_HACTIVE = 0x00
GPTC_GATE_LACTIVE = 0x02
GPTC_GATE_HACTIVE = 0x00
GPTC_UPDOWN_LACTIVE = 0x04
GPTC_UPDOWN_HACTIVE = 0x00
GPTC_OUTPUT_LACTIVE = 0x08
GPTC_OUTPUT_HACTIVE = 0x00
GPTC_INT_LACTIVE = 0x10
GPTC_INT_HACTIVE = 0x00

# GPTC paramID
GPTC_IntGATE = 0x00
GPTC_IntUpDnCTR = 0x01
GPTC_IntENABLE = 0x02

# SSI signal code
SSI_TIME = 1
SSI_CONV = 2
SSI_WR = 4
SSI_ADSTART = 8
SSI_ADTRIG = 0x20
SSI_DATRIG = 0x40

# signal code for GPTC
GPTC_CLK_0 = 0x100
GPTC_GATE_0 = 0x200
GPTC_OUT_0 = 0x300
GPTC_CLK_1 = 0x400
GPTC_GATE_1 = 0x500
GPTC_OUT_1 = 0x600

# signal code for clockoutToSMB source
PXI_CLK_10_M = 0x1000
CLK_20_M = 0x2000

# signal code for external SMB clk
SMB_CLK_IN = 0x3000

# signal route lines
PXI_TRIG_0 = 0
PXI_TRIG_1 = 1
PXI_TRIG_2 = 2
PXI_TRIG_3 = 3
PXI_TRIG_4 = 4
PXI_TRIG_5 = 5
PXI_TRIG_6 = 6
PXI_TRIG_7 = 7
PXI_STAR_TRIG = 8
TRG_IO = 9
SMB_CLK_OUT = 10
AFI0 = 0x10
AFI1 = 0x11
AFI2 = 0x12
AFI3 = 0x13
AFI4 = 0x14
AFI5 = 0x15
AFI6 = 0x16
AFI7 = 0x17
PXI_CLK = 0x18

# export signal plarity
Signal_ActiveHigh = 0x0
Signal_ActiveLow = 0x1

# DAQ_old Event type for the event message
DAQEnd = 0
DBEvent = 1
TrigEvent = 2
DAQEnd_A = 0
DAQEnd_B = 2
DAQEnd_AB = 3
DATrigEvent = 4
DATrigEvent_A = 4
DATrigEvent_B = 5
DATrigEvent_AB = 6

# Not_Reset_Code
DIONotRest = 0x01


class DAQChannel:
    """A simple class for the persistance of labels and settings of individual DAQ channels."""

    def __init__(
        self,
        ch_num,
        ch_name="",
        ch_limits=(-10, 10),
        default_value=0.0,
        is_ui_visible=True,
        calibration_fname="",
    ):

        self.chNum = ch_num
        self.chName = ch_name.strip() if ch_name.strip() else "Ch " + str(ch_num)
        self.chLimits = ch_limits
        self.defaultValue = default_value
        self.isUIVisible = is_ui_visible

        self.isCalibrated = False
        self.calibrationUnits = ""
        if calibration_fname.strip() != "":
            self.calibrate(calibration_fname, from_csv=False)

    def calibrate_from_txt(
        self, calibration_fname, re_read_in=r"([\+|\-]?[\d|\.]+)[ \t]*([\+|\-]?[\d|\.]+)"
    ):
        """
        WARNING: THIS METHOD IS DEPRECATED. USE CALIBRATE (WHICH TAKES A CSV FILE AS INPUT) INSTEAD.
        """

        print(
            "WARNING: calibrate_from_txt() METHOD IS DEPRECATED. USE CALIBRATE WITH CSV FILES INSTEAD."
        )

        # calibrationFname = os.path.join(REPO_PATH, calibrationFname)

        v_data, cal_data = [], []
        with Path(calibration_fname).open() as f:
            self.calibrationUnits = re.split(r"[ \t]*", f.readline())[-1].strip()
            for line in f.readlines():
                match = re.match(re_read_in, line.strip())
                if match:
                    v_data.append(float(match.group(1)))
                    cal_data.append(float(match.group(2)))

        if cal_data[0] <= cal_data[-1]:
            self.calibrationToVFunc = lambda x: np.interp(x, cal_data, v_data)
        else:
            print(self.chName, ": calibration to Voltage being reversed...")
            self.calibrationToVFunc = lambda x: np.interp(
                x, [x for x in reversed(cal_data)], [x for x in reversed(v_data)]
            )

        if v_data[0] <= v_data[-1]:
            self.calibrationFromVFunc = lambda x: np.interp(x, v_data, cal_data)
        else:
            print(self.chName, ": calibration from Voltage being reversed...")
            self.calibrationFromVFunc = lambda x: np.interp(
                x, [x for x in reversed(v_data)], [x for x in reversed(cal_data)]
            )

        self.isCalibrated = True
        self.calibrationFname = calibration_fname

    def calibrate(self, calibration_fname, from_csv=True):
        """
        Calibrates the channel using a calibration file.

        Args:
            calibrationFname (str): The name of the calibration file.
            from_csv (bool): If this is false, the old calibrate method is used instead.

        Returns:
            None
        """

        if not from_csv:
            self.calibrate_from_txt(calibration_fname)
            return

        try:
            df = pd.read_csv(calibration_fname)
        except FileNotFoundError:
            print(f"Calibration file not found: {calibration_fname}")
            return

        try:
            voltage_col = df.columns[0]  # Get the voltage column name (e.g., "Voltage (V)")
            data_col = df.columns[1]  # get the column containing the calibration data
            units = str(data_col).split(" ")[-1].strip("()")  # Extract units
        except IndexError:
            print(f"Invalid calibration file format: {calibration_fname}")
            return

        self.calibrationUnits = units
        v_data = df[voltage_col].values
        cal_data = df[data_col].values

        # Sort data by voltage for consistent interpolation
        sorted_idx = np.argsort(np.array(v_data))
        v_data = np.array(v_data)[sorted_idx]
        cal_data = np.array(cal_data)[sorted_idx]

        self.calibrationToVFunc = lambda x: np.interp(x, cal_data, v_data)
        self.calibrationFromVFunc = lambda x: np.interp(x, v_data, cal_data)

        self.isCalibrated = True
        self.calibrationFname = calibration_fname

    def remove_calibration(self):
        self.isCalibrated = False
        self.calibrationToVFunc, self.calibrationFromVFunc = None, None
        self.calibrationUnits = ""

    def get_help_text(self):
        format_args = [self.chNum, self.chLimits, self.defaultValue]
        if self.isCalibrated and self.calibrationFromVFunc is not None:
            format_args[2] = (
                f"{self.calibrationFromVFunc(self.defaultValue)}{self.calibrationUnits}"
            )
        return (
            "DAQ channel: {0}\n"
            + "Channel limits: {1}V\n"
            + "Default value: {2}\n"
            + self.get_calibration_text()
        ).format(*format_args)

    def get_calibration_text(self):
        if (
            not self.isCalibrated
            or self.calibrationToVFunc is None
            or self.calibrationFromVFunc is None
        ):
            return "There is no calibration on this channel."
        else:
            return ("Channel units: {0}\n" + "Calibration range: {1}V <-> {2}{3}").format(
                self.calibrationUnits,
                self.calibrationToVFunc((-np.inf, np.inf)),
                self.calibrationFromVFunc((-np.inf, np.inf)),
                self.calibrationUnits,
            )


class DAQDio:
    def __init__(self, dio_name, dio_num, port, line, direction, enabled_state):
        self.dio_name: str = dio_name
        self.dio_num: int = dio_num
        self.port: int = port
        self.line: int = line
        self.direction: int = direction
        self.enabled_state: int = enabled_state

        self.write_fn, self.read_fn = None, None

    def register_write_fn(self, write_fn):
        self.write_fn = write_fn

    def register_read_fn(self, read_fn):
        self.read_fn = read_fn

    def write(self, value):
        if self.write_fn is None:
            raise Exception("No write function has been registered for this digital IO.")
        return self.write_fn(value)

    def read(self):
        if self.read_fn is None:
            raise Exception("No read function has been registered for this digital IO.")
        return self.read_fn()

    def toggle_state(self, return_state=False):
        self.write(1 if self.read() == 0 else 0)
        if return_state:
            return self.read()

    def get_help_text(self):
        direction = (
            "output"
            if self.direction == OUTPUT_LINE
            else "input"
            if self.direction == INPUT_LINE
            else "unknown"
        )

        return (
            "Digital {0} channel registered on digital channel {1}.\n"
            + "Enabled state is {2}.\n"
            + "(Technical details: port {3},  line {4})."
        ).format(
            direction,
            self.dio_num,
            "HIGH" if self.enabled_state == 1 else "LOW",
            self.port,
            self.line,
        )

    def get_state(self):
        return self.read()


class DAQCard(DAQ2502):  # type: ignore
    """A subclass of DAQ2502 to extend it's functionality to be more user friendly.  In particular the conversion of
    sequences from a user friendly format (arrays of voltages on channel in numeric order) to the form expected by the
    DAQ card is handled at this level."""

    def __init__(self, card_number, channels=None, dios=None):
        if dios is None:
            dios = []
        if channels is None:
            channels = []
        DAQ2502.__init__(self, card_number)
        # Hard-coded limits - there are exactly 8 channels on the DAC card, each capable of outputting digital
        # values from 0 to 4095.<--> -/+10V.
        # When passing a full sequence to the DAQ card as an array the n-th channel sequence doesn't necessarily correspond
        # to the n-th DAQ channel - because fuck you - so we define the order expected here and will re-order our arrays before
        # sending them.
        """IMPORTANT NOTES:
        1. the expectedChOrderForSeq doesn not refer to the channel numbers, but the index of each channel in a
        list when they are sorted by channel number. e.g. if a DAQ card has channels 8,9,10,...15 - the expectedChOrderForSeq is still
        [0,4,1,5,2,6,3,7], which corresponds to [8,11,9,12,...].
        2. update_interval: From function reference pdf:
                When the device has an external time base, the range of valid value is 8 to 16777215. If the
                time base is internal, the range of valid value is 40 to 16777215."""
        self.numChs = 8
        self.expectedChOrderForSeq = [0, 4, 1, 5, 2, 6, 3, 7]
        self.chDigitalLimits = (0, 4095)
        self.chVoltageLimits = (-10, 10)
        # Clock speed in Hz
        self.clock_speed = 40 * 10**6
        self.useInternalTimeBasis = True
        self.updateIntervalLimits = (40, 16777215) if self.useInternalTimeBasis else (8, 16777215)

        # Perform some basic validation on the channels provided and sort them by channel number
        self.channels = self.validate_and_sort_channels(channels)

        self.dios = self.validate_and_register_digital_ios(dios)

    def array_to_digital_values(self, sequence_array, req_ch_order=None):
        """Takes a numpy array denoting the desired voltages on each DAQ channel of the form:
        [[Ch0_t0,Ch0_t1,Ch0_t2, ...],
         [Ch1_t0,Ch1_t1,Ch1_t2, ...],
         [Ch2_t0,Ch2_t1,Ch2_t2, ...],
         ...                         ]
        and converts it to a numpy array of digital values of the data type and order expected
        by the DAQ card."""
        num_chs, num_samps = sequence_array.shape
        if num_chs != self.numChs:
            print(
                "WARNING: the sequence being loaded is for",
                num_chs,
                "but DAQ card",
                self.card,
                "has",
                self.numChs,
                "channels.",
            )

        # The digital values representing the sequence that will be put to the card (note the data type is predetermined as uint16).
        digital_values = np.zeros((num_chs, num_samps), dtype=np.uint16)

        # Populate the digital_values array. Three things are done here
        #   1. The sequence is clipped according to the user set limits on the DAC channel output.
        #   2. The channel values are scaled to be digital values within the limits of the DAQ card...
        #   3. The order the channels as listed in the array is changed to match that expected by the dll.D2K_AO_Group_WFM_Start function on the card.
        if req_ch_order is None:
            # Don't reorder the channels of no order was provided
            req_ch_order = range(0, num_chs)
        for i in range(0, num_chs):
            digital_values[req_ch_order.index(i)] = np.interp(
                np.clip(
                    sequence_array[i], self.channels[i].chLimits[0], self.channels[i].chLimits[1]
                ),
                self.chVoltageLimits,
                self.chDigitalLimits,
            )

        # NOTE: The following was the old way of ensuring the array was in the right format for the DAQ card
        # # I think the DAQ card expects the matrix shape to be (numSamps, numChs) so let's correct for that -
        # # however, .transpose only changes the representation of the data (i.e. for the user/validation)m
        # # to change the order the card access the array data we set order='c'. (Thanks Dustin!)
        # digital_values= digital_values.transpose()
        # return digital_values.astype(np.uint16, order='c')

        # NOTE: Transpose, force C-contiguous layout, and set data type to uint16
        digital_values = digital_values.T
        digital_values = np.ascontiguousarray(digital_values, dtype=np.uint16)
        return digital_values

    def play(self, update_interval: float = 1.0, buffer_id=None):
        """Note update_interval is in microseconds for DAQCard (converted to clock ticks internally)"""
        update_interval_ticks = round(update_interval * 10**-6 * self.clock_speed)
        if (
            self.updateIntervalLimits[0] > update_interval_ticks
            or self.updateIntervalLimits[1] < update_interval_ticks
        ):
            raise DaqPlayError(
                "Error on DAQ card {}: update interval of {} is not between card limits of {} to {}.".format(
                    self.card, update_interval_ticks, *self.updateIntervalLimits
                )
            )
        DAQ2502.play(self, update_interval=update_interval_ticks, buffer_id=buffer_id)

    def write(self, digital_values):
        """NOTE: digital_values isn't actually an array of digital values. It must be converted."""
        return DAQ2502.write(
            self, self.array_to_digital_values(digital_values, [0, 1, 2, 3, 4, 5, 6, 7])
        )

    def load(self, digital_values):
        """NOTE: digital_values isn't actually an array of digital values. It must be converted."""
        return DAQ2502.load(
            self, self.array_to_digital_values(digital_values, self.expectedChOrderForSeq)
        )

    def validate_and_sort_channels(self, channels):
        """Check the right number of channels are registered and attempt to fix it if they are not."""
        for ch in channels:
            if type(ch) is not DAQChannel:
                raise TypeError("Only DAQChannel objects can registered channels on a DAQCard")

        # Check we have the right number of channels registered
        reg_chs = len(channels)
        if self.numChs < reg_chs:
            print(
                "WARNING: more DAQ channels were registered than are available. Ignoring additional channel definitions."
            )
            channels = channels[: self.numChs]
        elif self.numChs > reg_chs:
            print(
                "WARNING: fewer DAQ channels were registered than are available. Unassigned channels will use default labelling and values."
            )
            channels += [DAQChannel(i) for i in range(reg_chs, self.numChs)]

        # Sort channels by number and check that we have the expected channel numbers (e.g. 0,1,2,...) registered.
        # Note that for slaves the first channel number might be, e.g., 8 which would correspond to ch 0 on the card
        channels = sorted(channels, key=lambda ch: ch.chNum)
        if [ch.chNum for ch in channels] != [
            i for i in range(channels[0].chNum, channels[0].chNum + self.numChs)
        ]:
            raise Exception(
                "Unexpected channels registered.\nRegistered channel numbers: "
                + str([ch.chNum for ch in channels])
                + "\nExpected channel numbers: "
                + str([i for i in range(channels[0].chNum, self.numChs)])
            )

        return channels

    def validate_and_register_digital_ios(self, dios):
        """
        WARNING:  Currently the code allows for lines to override the config of the port when they are registered.
        e.g. a port must be input or output only, so if mupltiple lines on that port are input and output,
        things will go wrong...
        """
        registered_lines = []
        for dio in dios:
            try:
                DAQ2502.configure_digital_port(self, dio.port, dio.direction)
                if dio.direction == OUTPUT_LINE:
                    dio.register_write_fn(
                        lambda state, card=self, port=dio.port, line=dio.line: (
                            DAQ2502.write_digital_line(card, port, line, state)
                        )
                    )
                # TODO: register read functions
                dio.register_read_fn(
                    lambda card=self, port=dio.port, line=dio.line, direction=dio.direction: (
                        DAQ2502.read_digital_line(card, port, line, direction)
                    )
                )

                registered_lines.append(dio)

            except Daq2502Exception:
                print(
                    f"Error configuring digital line ('{dio.dio_name}') on card {dio.dio_name}, port {self.card}, line {dio.port}.  Not registering line."
                )

        return registered_lines


class DAQController:
    """A class for controlling one or more DAQ_2502 cards.  For multiple cards, all timings synchronised to a chosen 'master' card.
    The aim is for this to be the lowest level for the user control the DAQ cards - i.e. the DAQ cards act like one giant card through
    this interface."""

    def __init__(
        self, master: DAQCard, slaves: Optional[list[DAQCard]] = None, continuous_output=False
    ):
        """Initialise the DAQ_controller with:
        master : a DAQ2502/DAQCard instance
        slaves : one or more DAQ2502/DAQCard instances, slaves = myDAQ or slaves=[myDAQ1, myDAQ2...]"""

        #         check that master is one DAQ card, slave is list of DAQ cards
        if slaves is None:
            slaves = []
        #         for card in slaves + [master]:
        #             if not isinstance(card, DAQ2502):
        #                 raise TypeError("Only DAQ2502 objects can be passed to the DAQ_controller")

        self.master = master
        self.slaves = slaves

        #         Enslave all the slave cards to the master
        for slave in self.slaves:
            self.enslave(slave)

        self.continuousOutput = continuous_output

        self.channelValues = {ch.chNum: ch.defaultValue for ch in self.get_channels()}
        if continuous_output:
            self.write_channel_values()

    def update_channel_value(self, ch_num, new_value):
        self.channelValues[ch_num] = new_value
        if self.continuousOutput:
            # TODO : WHY DO I NEED THIS HACK???
            self.write(np.array([[v] for _, v in sorted(self.channelValues.items())]))
            self.write(np.array([[v] for _, v in sorted(self.channelValues.items())]))

    def update_dio(self, dio_num: int, value: bool):
        """
        Set a digital output line by its DIO number.
        Example: daq.update_dio(5, True)  # set DIO 5 high
        """
        for dio in self.get_dios():
            if dio.dio_num == dio_num:
                try:
                    dio.write(int(value))
                except Exception as e:
                    raise RuntimeError(f"Failed to write DIO {dio_num}: {e}") from e
                return
        raise ValueError(f"No DIO found with dio_num={dio_num}")

    def write_channel_values(self):
        # TODO : WHY DO I NEED THIS HACK???
        self._write_channel_values()
        self._write_channel_values()

    def _write_channel_values(self):
        self.write(np.array([[v] for _, v in sorted(self.channelValues.items())]))

    def get_channel_values(self):
        return np.array([[v] for _, v in sorted(self.channelValues.items())])

    def toggle_continuous_ouput(self):
        self.continuousOutput = not self.continuousOutput
        if self.continuousOutput:
            self.write(np.array([[v] for _, v in sorted(self.channelValues.items())]))
        else:
            self.write(np.zeros((len(self.get_channels()), 1)))

    def validate_and_correct_control_array(self, control_array):
        """Ensure the control array has for the correct number of channels."""
        seq_chs, num_samps = control_array.shape
        tot_chs = sum([card.numChs for card in [self.master, *self.slaves]])
        if seq_chs < tot_chs:
            print(
                "WARNING: Attempting to load an array for",
                seq_chs,
                "channels when there are",
                tot_chs,
                "channels available. Extra channels will be set to zero.",
            )
            control_array = np.vstack([control_array, np.zeros([tot_chs - seq_chs, num_samps])])
        elif seq_chs > tot_chs:
            print(
                "WARNING: Attempting to load an array for",
                seq_chs,
                "channels when there are",
                tot_chs,
                "channels available. Extra channels will be ignored.",
            )
            control_array = control_array[:tot_chs]

        return control_array

    def write(self, value_array):
        """Write a value array into the DAQ cards. Note the expected ordering of the array is that the first n1 channels correspond
        to the n1 channels on the master card, the next n2 channels to the channels on the first listed slave card, the next n3 to the
        second listed slave card and so on.  The order of the slave cards is defined by there order in the list with which the controller
        was initialised."""
        value_array = self.validate_and_correct_control_array(value_array)
        # Now it is the right size, split the value array between the DAQ cards. (Note - write to the master last so the update
        # signal is sent to the salves after the values are updated).
        for card in reversed([self.master, *self.slaves]):
            vals = value_array[-card.numChs :]
            value_array = value_array[: -card.numChs]
            #             time.sleep(0.1)
            card.write(vals)

    def load(self, sequence_array):
        """Load a sequence into the DAQ cards. Note the expected ordering of the sequence is that the first n1 channels correspond
        to the n1 channels on the master card, the next n2 channels to the channels on the first listed slave card, the next n3 to the
        second liste slave card and so on.  The order of the slave cards is defined by there order in the list with which the controller
        was initialised."""
        sequence_array = self.validate_and_correct_control_array(sequence_array)
        # Now it is the right size, split the sequence between the DAQ cards.
        n_chs_loaded = 0
        for card in [self.master, *self.slaves]:
            card.load(sequence_array[n_chs_loaded : n_chs_loaded + card.numChs])
            n_chs_loaded += card.numChs

    def play(self, t_step: float = 1.0, clear_cards=True, buffer_id=None):
        """
        Note t_step is in microseconds

        Play the sequence last loaded onto the DAQ cards.  Talk to Dustin to confirm usage of buffer_id...
           The order of events is:
                1. Play all the slaves - they will not start until the master is started due to the timing synchronisation set up in the enslave function.
                2. Start the master card, triggering the sequence.
                3. Wait for the mater card to finish it's sequence.
                4. Stop the master card. (It's not yet clear if this step is essential.)
                5. Wait for the slaves to finish if they are still playing.
                6. Stop the slave cards."""
        for slave in self.slaves:
            slave.play(t_step)
        self.master.play(t_step)
        self.master.wait()
        self.master.stop()
        #         for slave in self.slaves:
        #             print 'waiting for card: ', slave.card
        #             slave.wait()
        for slave in self.slaves:
            slave.stop()
        if clear_cards:
            self.clear_cards()

    def clear_cards(self):
        """
        Clear all the cards redy for a new sequence to be loaded.
        """
        for card in [self.master, *self.slaves]:
            card.clear()

    def enslave(self, slave):
        """Enslave a card to the master"""
        print(f"Enslaved card {slave.card} to card {self.master.card}")
        if dll is None:
            return
        #         dll.D2K_AO_Config(slave.card, DAQ2K_DA_WRSRC_SSI, DAQ2K_DA_TRSRC_SSI | DAQ2K_DA_TRGMOD_POST, 0, 0, 0, 0) # OLD and depricated by Tom 1/9/16
        dll.D2K_AO_Config(
            slave.card,
            DAQ2K_DA_WRSRC_SSI | DA_Group_AB,
            DAQ2K_DA_TRSRC_SSI | DAQ2K_DA_TRGMOD_POST,
            0,
            0,
            0,
            0,
        )
        dll.D2K_SSI_SourceConn(self.master.card, SSI_WR | SSI_DATRIG)

    def emancipate(self, slave):
        """Free a card from the master"""
        print(f"Freed card {slave.card} from card {self.master.card}")
        if dll is None:
            return
        # Should the second argument be DAQ2K_DA_WRSRC_Int | DA_Group_AB for consistancy with enslave()?
        dll.D2K_AO_Config(
            slave.card, DAQ2K_DA_WRSRC_Int, DAQ2K_DA_TRGSRC_SOFT | DAQ2K_DA_TRGMOD_POST, 0, 0, 0, 0
        )
        dll.D2K_SSI_SourceClear(self.master.card)

    def release_all(self):
        for card in [*self.slaves, self.master]:
            card.release()

    def get_channels(self, only_visible=False) -> list[DAQChannel]:
        """Returns a list of all the DAQChannel objects registered with the controller."""
        channels = functools.reduce(
            operator.iadd, [card.channels for card in [self.master, *self.slaves]], []
        )
        if only_visible:
            channels = [ch for ch in channels if ch.isUIVisable]
        return channels

    def get_dios(self) -> list[DAQDio]:
        """Returns a list of all the DAQDio (digital in/out) objects registered with the controller."""
        return functools.reduce(
            operator.iadd, [card.dios for card in [self.master, *self.slaves]], []
        )

    def get_channel_number_name_dict(self, only_visible=False):
        """Returns a list of all the DAQChannel in a dict. of the form {chNum: chName}."""
        return dict([(ch.chNum, ch.chName) for ch in self.get_channels(only_visible)])

    def get_channel_calibration_dict(self):
        """Returns a dictonary of all calibrated channels of the form
        {channel number:(calibrationUnits, calibrationToVFunc, calibrationFromVFunc)}."""
        return dict(
            [
                (ch.chNum, (ch.calibrationUnits, ch.calibrationToVFunc, ch.calibrationFromVFunc))
                for ch in self.get_channels(only_visible=False)
                if ch.isCalibrated
            ]
        )

    def get_master(self):
        return self.__master

    def get_slaves(self):
        return self.__slaves

    def set_master(self, value):
        self.__master = value

    def set_slaves(self, value):
        self.__slaves = value

    def del_master(self):
        del self.__master

    def del_slaves(self):
        del self.__slaves

    master = property(get_master, set_master, del_master, "The master DAQ card")
    slaves = property(
        get_slaves,
        set_slaves,
        del_slaves,
        "The list of slaves that get there timings from the master DAQ card",
    )


class DaqPlayError(Exception):
    def __init__(self, message, errors=None):
        # Call the base class constructor with the parameters it needs
        if errors is None:
            errors = []
        super().__init__(message)
        self.errors = errors
