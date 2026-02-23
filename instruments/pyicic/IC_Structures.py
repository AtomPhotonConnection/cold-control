#!/usr/bin/env python

from ctypes import *


class GrabberHandle(Structure):
    pass


GrabberHandle._fields_ = [("unused", c_int)]
