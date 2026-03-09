#!/usr/bin/env python

from ctypes import byref, c_int, c_long

from .ic_exception import ICError
from .ic_grabber_dll import ICGrabberDLL


class ICProperty:
    @property
    def available(self):
        """ """
        # returns boolean value
        iav = self._avail_funcs[self._prop_type](self._handle, c_int(self._prop_index))
        return bool(iav)

    @property
    def auto_available(self):
        """ """
        # returns boolean value
        iaa = self._auto_avail_funcs[self._prop_type](self._handle, c_int(self._prop_index))
        return bool(iaa)

    @property
    def range(self):
        """
        Get valid range of values for the property.

        :returns: tuple -- (range min, range max).
        """
        rmin = c_long()
        rmax = c_long()
        err = self._range_funcs[self._prop_type](
            self._handle, c_int(self._prop_index), byref(rmin), byref(rmax)
        )
        if err != 1:
            raise ICError(err)
        else:
            return (rmin.value, rmax.value)

    @property
    def min(self):
        """ """
        return self.range[0]

    @property
    def max(self):
        """ """
        return self.range[1]

    @property
    def value(self):
        """ """
        val = c_long()

        err = self._get_value_funcs[self._prop_type](
            self._handle, c_int(self._prop_index), byref(val)
        )
        if err != 1:
            raise ICError(err)
        else:
            return val.value

    @value.setter
    def value(self, val):
        """ """

        # turn off auto first TOM EDIT: if auto is available
        if self.auto_available:
            self.auto = False

        # set value
        err = self._set_value_funcs[self._prop_type](
            self._handle, c_int(self._prop_index), c_long(val)
        )
        if err != 1:
            raise ICError(err)

    @property
    def auto(self):
        """ """
        aut = c_int()

        err = self._get_auto_funcs[self._prop_type](
            self._handle, c_int(self._prop_index), byref(aut)
        )
        if err != 1:
            raise ICError(err)
        else:
            return bool(aut.value)

    @auto.setter
    def auto(self, aut):
        """ """
        err = self._set_auto_funcs[self._prop_type](
            self._handle, c_int(self._prop_index), c_long(int(aut))
        )
        if err != 1:
            raise ICError(err)

    @property
    def type(self):
        """ """
        return self._prop_type

    @staticmethod
    def get_video_property_names():
        """ """
        return [
            "brightness",
            "contrast",
            "hue",
            "saturation",
            "sharpness",
            "gamma",
            "colorenable",
            "whitebalance",
            "blacklightcompensation",
            "gain",
        ]

    @staticmethod
    def get_camera_property_names():
        """ """
        return ["pan", "tilt", "roll", "zoom", "exposure", "iris", "focus"]

    @staticmethod
    def get_all_property_names():
        """ """
        return ICProperty.get_video_property_names() + ICProperty.get_camera_property_names()

    def __init__(self, handle, name):

        self._handle = handle
        self._prop_name = name

        self._avail_funcs = {
            "video": ICGrabberDLL.is_video_property_available,
            "camera": ICGrabberDLL.is_camera_property_available,
        }
        self._auto_avail_funcs = {
            "video": ICGrabberDLL.is_video_property_auto_available,
            "camera": ICGrabberDLL.is_camera_property_auto_available,
        }
        self._range_funcs = {
            "video": ICGrabberDLL.video_property_get_range,
            "camera": ICGrabberDLL.camera_property_get_range,
        }
        self._get_value_funcs = {
            "video": ICGrabberDLL.get_video_property,
            "camera": ICGrabberDLL.get_camera_property,
        }
        self._set_value_funcs = {
            "video": ICGrabberDLL.set_video_property,
            "camera": ICGrabberDLL.set_camera_property,
        }
        self._get_auto_funcs = {
            "video": ICGrabberDLL.get_auto_video_property,
            "camera": ICGrabberDLL.get_auto_camera_property,
        }
        self._set_auto_funcs = {
            "video": ICGrabberDLL.enable_auto_video_property,
            "camera": ICGrabberDLL.enable_auto_camera_property,
        }

        vid_props = ICProperty.get_video_property_names()
        cam_props = ICProperty.get_camera_property_names()

        if name in vid_props:
            self._prop_type = "video"
            self._prop_index = vid_props.index(name)
        elif name in cam_props:
            self._prop_type = "camera"
            self._prop_index = cam_props.index(name)
        else:
            raise ICError(0)
