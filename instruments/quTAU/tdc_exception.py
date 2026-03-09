_ERROR_CODES = {
    0: "SUCCESS",
    -1: "UNSPECIFIED ERROR",
    1: "RECEIVE TIMED OUT",
    2: "NO CONNECTION WAS ESTABLISHED",
    3: "ERROR ACCESSING THE USB DRIVER",
    7: "CAN'T CONNECT DEVICE BECAUSE ALREADY IN USE",
    8: "UNKNOWN ERROR",
    9: "INVALID DEVICE NUMBER USED IN CALL",
    10: "PARAMETER IN FUNCTION CALL IS OUT OF RANGE",
    11: "FAILED TO OPEN SPECIFIED FILE",
    12: "LIBRARY HAS NOT BEEN INITIALIZED",
    13: "REQUESTED FEATURE IS NOT ENABLED",
    14: "REQUESTED FEATURE IS NOT AVAILABLE",
    -100: "ERROR CODE NOT SPECIFIED IN DOCUMENTATION",
}


class TdcError(Exception):
    """
    An exception for the TDC software. It contains a message property which is a string indicating what went wrong.

    :param error_code: Error code to be used to look up error message.
    """

    @property
    def message(self):
        return _ERROR_CODES[self.error_code]

    @property
    def error_code(self):
        return self._error_code

    def __init__(self, error_code):
        # if error code does not match expected codes then assign invalid code
        if error_code in _ERROR_CODES:
            self._error_code = error_code
        else:
            self._error_code = -100
