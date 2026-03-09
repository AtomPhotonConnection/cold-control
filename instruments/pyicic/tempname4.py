#!/usr/bin/env python
# ic_structures.py
from ctypes import Structure, c_int


class GrabberHandle(Structure):
    pass


GrabberHandle._fields_ = [("unused", c_int)]
