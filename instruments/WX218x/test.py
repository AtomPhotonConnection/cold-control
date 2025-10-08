# check_symbol_simple.py
import ctypes
dllpath = r"C:\Program Files\IVI Foundation\IVI\Bin\wx218x_64.dll"  # adjust if needed
sym = "wx218x_ConfigureOnceCount2"
try:
    dll = ctypes.WinDLL(dllpath)
    print("Loaded DLL:", dllpath)
    try:
        _ = getattr(dll, sym)
        print(f"Symbol {sym!r} FOUND in the DLL.")
    except AttributeError:
        print(f"Symbol {sym!r} NOT found in the DLL.")
except Exception as e:
    print("Failed to load DLL:", e)
