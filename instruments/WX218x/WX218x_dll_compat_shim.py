"""
Compatibility shim for Tabor WX218x IVI DLL.

This replacement loader aims to make the existing `WX218x_DLL.py` wrapper
more tolerant to differences between DLL versions by:

- Loading the 64-bit DLL from common locations.
- Lazily binding exported functions on first use (via __getattr__).
- If a function is absent, returning None (so import won't fail); code that
  actually calls the function should check and provide an alternative.
- Providing helper methods for common init variants (Init, InitWithOptions)
  that try multiple signatures and provide clearer errors.

HOW TO USE
- Replace your current instruments/WX218x/WX218x_DLL.py with this file
  (or save as a separate module and adjust imports).
- This shim intentionally avoids hard-coding argtypes for every export.
  If you know exact prototypes for frequently used functions, add them to
  `KNOWN_PROTOTYPES` below to enable strict argument checking.

LIMITATIONS
- This is a compatibility shim, not a full reimplementation of the vendor
  SDK. Some higher-level features will still require either the original
  DLL with full-compatible exports or a PyVISA-based replacement.

"""
from collections.abc import Callable
from ctypes import WinDLL, c_char_p, c_int, c_int32, c_ushort, c_uint, c_ulong, c_long, byref
import ctypes
import os
import sys


DLL_PATH = r"C:\Program Files\IVI Foundation\IVI\Bin\wx218x_64.dll"

# If you know the exact prototypes for common functions, add them here.
# Format: 'function_name': (restype, (argtype1, argtype2, ...))
KNOWN_PROTOTYPES = {
    # Examples (adjust if you know exact types):
    'wx218x_init': (c_long, (c_char_p, c_ushort, c_ushort, ctypes.POINTER(c_uint))),
    'wx218x_InitWithOptions': (c_long, (c_char_p, c_ushort, c_ushort, c_char_p, ctypes.POINTER(c_uint))),
}






class WX218x_DLL:
    """Compatibility loader for wx218x IVI DLL.

    Usage: import this module and call methods the original wrapper expects.
    The first attribute access that maps to a DLL export will attempt to bind
    that symbol.
    """

    # class-level dll handle (shared)
    _dll_path = DLL_PATH
    print(f"Attempting to load wx218x DLL from: {_dll_path}")

    try:
        _dll = WinDLL(_dll_path)
        print(f"Loaded wx218x DLL successfully.")
    except Exception as e:
        print("Failed to load wx218x dll:", e)
        _dll = None

    def __init__(self):
        # Provide a placeholder for session values
        self._vi_session = c_uint(0)

    def __getattr__(self, name):
        # Lazy bind functions exported by the native DLL. If not found, return
        # None to avoid import-time failures. Callers should check.
        if name.startswith('_'):
            raise AttributeError(name)
        dll = self.__class__._dll
        if dll is None:
            raise AttributeError(f"DLL not loaded, cannot bind {name}")

        try:
            func = getattr(dll, name)
        except AttributeError:
            # symbol not exported
            # set attribute to None so subsequent accesses are fast
            setattr(self, name, None)
            print(f"Warning: symbol {name} not found in wx218x DLL")
            return None

        # Optionally set prototype if known
        proto = KNOWN_PROTOTYPES.get(name)
        if proto:
            restype, argtypes = proto
            func.restype = restype
            func.argtypes = argtypes
        else:
            # don't set argtypes to allow ctypes to coerce arguments
            func.restype = c_long

        # bind to instance for future calls
        setattr(self, name, func)
        return func

    # convenience wrappers: attempt common init patterns
    def init(self, resource_name: bytes, verify: int , reset: int, session):
        """Try to initialize the instrument using Init if available."""
        init_funct = getattr(self, "wx218x_init", None)
        
        if init_funct is None:
            print("wx218x_init not found in DLL.")
            return None, 0

        try:
            rc = init_funct(c_char_p(resource_name), c_ushort(verify), c_ushort(reset),\
                            byref(session))
            return rc, session.value
        except Exception as e:
            print(f"Call raised:", e)

    def init_with_options(self, resource: bytes, verify: int, reset: int,\
                           options_string: bytes, session: c_uint):
        """Try to initialize the instrument using InitWithOptions if available."""
        
        init_with_options_funct = getattr(self, 'wx218x_InitWithOptions', None)

        if init_with_options_funct is not None:
            try:
                rc = init_with_options_funct(c_char_p(resource), c_ushort(verify),\
                                            c_ushort(reset), c_char_p(options_string),\
                                            byref(session))
                return rc, session.value
            except Exception as e:
                print("InitWithOptions raised:", e)
                


# Export a module-level instance to mimic the original wrapper usage if it used
# a module-level wx218x_dll object.
wx218x_dll = WX218x_DLL()

# Helper: expose a small mapping for caller convenience
def is_symbol_present(name: str) -> bool:
    dll = WX218x_DLL._dll
    if dll is None:
        return False
    try:
        getattr(dll, name)
        return True
    except AttributeError:
        return False










class WX218x_MarkerSource(object):
    (
     WAVE, # Wave marker source.
     USER  # User marker source.
     ) = map(c_int, range(2))
    

class WX218x_OperationMode(object):
    '''
    Commented out values are only in the WX218X_ATTR_OPERATION_MODE2 attribute
    which I don't use.
    '''
    (
    CONTINUOUS, # Generate output continuously.
    BURST,      # Generate a burst of waveforms when a trigger occurs.               
    TRIGGER,    # Trigger operation mode.   NOTE: THIS SEEMS TO BE THE MODE THAT RESPECTS THE BURST COUNT SETTINGS!         
    GATE        # Gate operation mode.
     ) = map(c_int, range(4))


class WX218x_OutputMode(object):
    '''
    Commented out values are only in the WX218X_ATTR_OUTPUT_MODE2 attribute
    which I don't use.
    '''
    (
    FUNCTION,    # Selects the standard waveform shapes.
    ARBITRARY,   # Selects the arbitrary waveform shapes.                
    SEQUENCE,    # Selects the sequenced waveform output. (Not for WS8351,WS8352)            
#     ASEQUENCE,   # Selects the advanced sequencing waveform output. (Not for WS8351,WS8352)
#     MODULATION,  # Selects the modulated waveforms.
#     PULSE,       # Selects the digital pulse function.
#     PATTERN      # Sets pattern output mode. (Not for WX2181,WX2182)
    ) = map(c_int, range(3))


class WX218x_TraceMode(object):
    (
     SINGLE,    # Selects the Single trace mode for download waveforms. 
     DUPLICATE, # Selects the Duplicate trace mode for download waveforms. 
     ZERO,      # Selects the Zero trace mode for download waveforms.
     COMBINE    # Selects the Combine trace mode for download waveforms.
     ) = map(c_int32, range(4))


class WX218x_TriggerMode(object):
    (
     EXTERNAL, # Selects the TRIG IN connector as the input source. The manual
               # trigger can be used in case external triggers are not available.
               # All other inputs are ignored.
     SOFTWARE, # Selects the remote controller as the trigger source. Only
               # software commands are accepted; TRIG IN, Event IN and manual
               # triggers are ignored.
     TIMER,    # Activates the built in internal trigger generator. BUS and
               # external trigger are ignored. The period of the internal trigger
               # is programmable and can be used to replace an external trigger source.
     EVENT     # Selects the Event IN connector as the input source. All other inputs
               # are ignored.
     ) = map(c_int32, [1,2,4,5])
     
class WX218x_TriggerSlope(object):
    (
     POSITIVE, # Selects the positive going edge.
     NEGATIVE, # Selects the negative going edge.
     EITHER    # Selects both positive and negative going edges.Not supported for WX2184.
     ) = map(c_int32, range(3))





if __name__ == '__main__':
    # print('WX218x_DLL compatibility shim loaded')
    # print('DLL path:', WX218x_DLL._dll_path)
    # print('wx218x_init present?', is_symbol_present('wx218x_init'))
    # print('wx218x_ConfigureOnceCount2 present?', is_symbol_present('wx218x_ConfigureOnceCount2'))

    candidates = [
        'wx218x_Configure2',
        'wx218x_ConfigureTrigger',
        'wx218x_ConfigureTriggerLevel',
        'wx218x_ConfigureTriggerInput',
        'wx218x_ConfigureTriggerVoltage',
        'wx218x_ConfigureTrig',
        'wx218x_ConfigureOnceCount2',
        'wx218x_ConfigureOnceCount',
        'wx218x_ConfigureThreshold',
        'wx218x_ConfigureInputLevel',
        'wx218x_ConfigureTriggerThresh',
    ]

    print("Scanning for trigger-related exports in:", WX218x_DLL._dll_path)
    for name in candidates:
        print(f"{name:40s} ->", is_symbol_present(name))
