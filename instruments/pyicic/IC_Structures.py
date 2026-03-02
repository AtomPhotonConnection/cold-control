#!/usr/bin/env python

from ctypes import Structure, c_int


class GrabberHandle(Structure):
    pass


GrabberHandle._fields_ = [("unused", c_int)]
