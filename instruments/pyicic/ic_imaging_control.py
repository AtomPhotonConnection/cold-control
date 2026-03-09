#!/usr/bin/env python

from __future__ import annotations

from .ic_camera import ICCamera
from .ic_exception import ICError
from .ic_grabber_dll import ICGrabberDLL


class ICImagingControl:
    def __init__(self) -> None:
        self.initialised = False
        self._unique_device_names: list[bytes] | None = None
        self._devices: dict[bytes, ICCamera] = {}

    def init_library(self):
        """
        Initialise the IC Imaging Control library.
        """
        # remember list of unique device names
        self._unique_device_names = None

        # remember device objects by unique name
        self._devices = {}

        # no license key needed anymore
        err = ICGrabberDLL.init_library(None)
        if err != 1:
            raise ICError(err)

        self.initialised = True

    def get_unique_device_names(self):
        """
        Gets unique names (i.e. model + label + serial) of devices.

        :returns: list -- unique devices names.
        """
        if self._unique_device_names is None:
            # make new list
            self._unique_device_names = []

            # get num devices, must be called before get_unique_name_from_list()!
            num_devices = ICGrabberDLL.get_device_count()
            if num_devices < 0:
                raise ICError(num_devices)

            # populate list
            for i in range(num_devices):
                self._unique_device_names.append(ICGrabberDLL.get_unique_name_from_list(i))

        return self._unique_device_names

    def get_device(self, unique_device_name):
        """
        Gets camera device object based on unique name string.
        Will create one only if it doesn't already exist.

        :param device_name: string -- the unique name of the device.

        :returns: ICCamera object -- the camera device object requested.
        """
        # check name is valid
        if unique_device_name in self.get_unique_device_names():
            # check if already have a ref to device
            if unique_device_name not in self._devices:
                # if not, create one
                self._devices[unique_device_name] = ICCamera(unique_device_name)

            return self._devices[unique_device_name]

        raise ICError(-106)

    def close_library(self):
        """
        Close the IC Imaging Control library, and close and release all references to camera devices.
        """
        # release handle grabber objects of cameras as they won't be needed again.
        # try to close & delete each known device, but only if we own the reference to it!
        for unique_device_name in self.get_unique_device_names():
            if unique_device_name in self._devices:
                # close camera device if open
                if self._devices[unique_device_name].is_open():
                    self._devices[unique_device_name].close()

                # release grabber of camera device
                ICGrabberDLL.release_grabber(self._devices[unique_device_name]._handle)

        # kill refs
        self._unique_device_names = None
        self._devices = {}

        # close lib
        ICGrabberDLL.close_library()
