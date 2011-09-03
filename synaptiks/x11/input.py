# -*- coding: utf-8 -*-
# Copyright (C) 2010, 2011 Sebastian Wiesner <lunaryorn@googlemail.com>
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
    synaptiks.x11.input
    ===================

    This module mainly provides the :class:`InputDevice` class, which gives
    access to properties of input devices registered on the X11 server.

    Finding input devices
    ---------------------

    :class:`InputDevice` provides various class methods to find input devices.
    You can iterate over all devices using :meth:`InputDevice.all_devices()`,
    or you can get a filtered list of devices using
    :meth:`InputDevice.find_devices_by_name()` or
    :meth:`InputDevice.find_devices_with_property()`.

    Working with input devices
    --------------------------

    The :class:`InputDevice` class is a read-only mapping of property names to
    property values:

    >>> from synaptiks.x11 import Display
    >>> devices = list(InputDevice.find_devices_with_property(
    ...     Display.from_qt(), 'Synaptics Off'))
    >>> devices
    [<InputDevice(14, u'AlpsPS/2 ALPS GlidePoint')>]
    >>> devices[0].name
    u'AlpsPS/2 ALPS GlidePoint'
    >>> devices[0]['Synaptics Off']
    [0]
    >>> devices[0]['Synaptics Edge Scrolling']
    [0, 1, 0]

    To change properties, this interface can't be used, because properties
    require explicit type information on write access.  Therefore separate
    setters are provided:

    >>> devices[0].set_bool('Synaptics Edge Scrolling', [False, False, False])

    .. moduleauthor::  Sebastian Wiesner  <lunaryorn@googlemail.com>
"""

from __future__ import (print_function, division, unicode_literals,
                        absolute_import)

import struct
from functools import partial
from collections import Mapping, namedtuple
from operator import eq

from synaptiks._bindings import xlib, xinput
from synaptiks._bindings.util import scoped_pointer
from synaptiks.x11 import Atom
from synaptiks.util import ensure_unicode_string


class XInputVersion(namedtuple('_XInputVersion', 'major minor')):
    """
    A :func:`~collections.namedtuple` representing a XInput version.

    This class has two attributes, :attr:`major` and :attr:`minor`, which
    contain the corresponding parts of the version number as integers.
    """

    def __str__(self):
        return '{0.major}.{0.minor}'.format(self)


class XInputVersionError(Exception):
    """
    Raised on unexpected XInput versions.
    """

    def __init__(self, expected_version, actual_version):
        """
        Create a new instance of this error.

        ``expected_version`` is the expected version number as ``(major,
        minor)`` tuple, ``actual_version`` the actual version number in the
        same format.  ``major`` and ``minor`` are integers.
        """
        Exception.__init__(self, XInputVersion(*expected_version),
                           XInputVersion(*actual_version))

    @property
    def expected_version(self):
        """
        The expected XInput version as :class:`XInputVersion`.
        """
        return self.args[0]

    @property
    def actual_version(self):
        """
        The actual XInput version as :class:`XInputVersion`.
        """
        return self.args[1]

    def __str__(self):
        return ('XInputVersionError: Expected {0.expected_version}, '
                'got {0.actual_version}').format(self)


def assert_xinput_version(display):
    """
    Check, that the XInput version on the server side is sufficiently
    recent.

    Currently, at least version 2.0 is required.

    ``display`` is a :class:`~synaptiks.x11.Display` object.

    Raise :exc:`XInputVersionError`, if the version isn't sufficient.
    """
    matched, actual_version = xinput.query_version(display, (2, 0))
    if not matched:
        raise XInputVersionError((2, 0), actual_version)


class UndefinedPropertyError(KeyError):
    """
    Raised if a property is undefined on the server side.  Subclass of
    :exc:`~exceptions.KeyError`.
    """

    @property
    def name(self):
        """
        The name of the undefined property as string.
        """
        return self.args[0]


def _get_property_atom(display, name):
    """
    Get a :class:`~synaptiks.x11.Atom` for the given property.

    ``display`` is a :class:`~synaptiks.x11.Display` object.  ``name`` is the
    property name as byte or unicode string.  A unicode string is converted
    into a byte string according to the encoding of the current locale.

    Return the :class:`~synaptiks.x11.Atom` for the given property.

    Raise :exc:`UndefinedPropertyError`, if there is no atom for the given
    property.
    """
    atom = display.intern_atom(name)
    if not atom:
        raise UndefinedPropertyError(name)
    return atom


class InputDeviceNotFoundError(Exception):
    """
    Raised if a device with a certain id does not exist anymore.
    """

    @property
    def id(self):
        """
        The id of the non-existing device as integer.
        """
        return self.args[0]

    def __str__(self):
        return 'The device with id {0} does not exist'.format(self.id)


class PropertyTypeError(ValueError):
    """
    Raised if a property value has an unexpected type.  Subclass of
    :exc:`~exceptions.ValueError`.
    """

    @property
    def type_atom(self):
        """
        The property type that caused this error as X11 atom.
        """
        return self.args[0]

    def __str__(self):
        return 'Unexpected property type: {0}'.format(self.type_atom)


#: maps property formats to :mod:`struct` format codes
_TYPE_CODE_MAPPING = {8: 'B', 16: 'H', 32: 'L'}


def _make_struct_format(type_code, number_of_items):
    """
    Make a :mod:`struct` format for the given number of items of the given
    type.

    ``type_code`` is a one-character string with a :mod:`struct` type code.
    ``number_of_items`` is the number of items, which the returned format
    should parse.

    Return a byte string with a struct format suitable to parse the given
    number of items of the given type.

    .. note::

       The returned format parses types with *standard* byte length, not with
       *native* byte length.
    """
    # property data has always a fixed length, independent of architecture, so
    # force "struct" to use standard sizes for data types.  However, still use
    # native endianess, because the X server does byte swapping as necessary
    if len(type_code) != 1:
        raise ValueError('invalid type code')
    return b'={0}{1}'.format(number_of_items, type_code)


def _pack_property_data(type_code, values):
    """
    Pack the given list of property ``values`` of the given type into a byte
    string.

    ``type_code`` is a one-character string containing a :mod:`struct` type
    code corresponding of the indented type in the binary data.  ``values`` is
    a list of values to pack.

    Return a byte string encoding ``values`` in the given ``type_code``.
    """
    struct_format = _make_struct_format(type_code, len(values))
    return struct.pack(struct_format, *values)


def _unpack_property_data(type_code, number_of_items, data):
    """
    Unpack property values from the given binary ``data``.

    ``type_code`` is the type of the items in ``data``, as one-character string
    containing a :mod:`struct` type code.  ``number_of_items`` is the number of
    items, ``data`` is expected to contain. ``data`` is a byte string
    containing the packed property data.

    Return a list containing the unpacked property values.  The items in this
    list have a type corresponding to the given ``type_code``.
    """
    struct_format = _make_struct_format(type_code, number_of_items)
    assert struct.calcsize(struct_format) == len(data)
    return list(struct.unpack(struct_format, data))


class InputDevice(Mapping):
    """
    An input device registered on the X11 server.

    This class subclasses the ``Mapping`` ABC, providing a dictionary mapping
    device property names to the corresponding values. Therefore all well-known
    dicitionary methods and operators (e.g. ``.keys()``, ``.items()``, ``in``)
    are available to access the properties of a input device.

    :class:`InputDevice` objects compare equal and unequal to other devices
    and to strings (based on :attr:`id`). However, there is no ordering on
    and the corresponding operators >, <, <= and >= raise TypeError.
    """

    @classmethod
    def all_devices(cls, display):
        """
        Iterate over all input devices registered on the given ``display``.

        ``display`` is a :class:`~synaptiks.x11.Display` object.

        Return an iterator over :class:`InputDevice` objects.

        Raise :exc:`XInputVersionError`, if the XInput version isn't sufficient
        to support input device management.
        """
        assert_xinput_version(display)
        number_of_devices, devices = xinput.query_device(
            display, xinput.ALL_DEVICES)
        with scoped_pointer(devices, xinput.free_device_info) as devices:
            if not devices:
                raise EnvironmentError('Failed to query devices')
            for i in xrange(number_of_devices):
                yield cls(display, devices[i].deviceid)

    @classmethod
    def find_devices_by_name(cls, display, name):
        """
        Find all devices with the given ``name`` on the given ``display``.

        ``display`` is a :class:`~synaptiks.x11.Display` object.  ``name`` is
        either a string, which has to match the device name literally, or a
        regular expression pattern, which is searched in the device name.

        Return an iterator over all :class:`InputDevice` objects with a
        matching name.

        Raise :exc:`XInputVersionError`, if the XInput version isn't sufficient
        to support input device management.
        """
        if isinstance(name, basestring):
            matches = partial(eq, name)
        else:
            matches = name.search
        return (d for d in cls.all_devices(display) if matches(d.name))

    @classmethod
    def find_devices_with_property(cls, display, name):
        """
        Find all devices which have the given property.

        ``display`` is a :class:`~synaptiks.x11.Display` object.  ``name`` is a
        string with the property name.

        Return an iterator over all :class:`InputDevice` objects, which have
        this property defined.

        Raise :exc:`XInputVersionError`, if the XInput version isn't sufficient
        to support input device management.
        """
        return (d for d in cls.all_devices(display) if name in d)

    def __init__(self, display, deviceid):
        self.id = deviceid
        self.display = display

    @property
    def name(self):
        """
        The name of this device as unicode string.
        """
        _, device = xinput.query_device(self.display, self.id)
        with scoped_pointer(device, xinput.free_device_info) as device:
            if not device:
                raise InputDeviceNotFoundError(self.id)
            return ensure_unicode_string(device.contents.name)

    def __repr__(self):
        return '<{0}({1}, name={2!r})>'.format(self.__class__.__name__,
                                               self.id, self.name)

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id

    def __hash__(self):
        return hash(self.id)

    def __len__(self):
        """
        Return the amount of all properties defined on this device.
        """
        number_of_properties, property_atoms = xinput.list_properties(
            self.display, self.id)
        with scoped_pointer(property_atoms, xlib.free):
            return number_of_properties

    def _iter_property_atoms(self):
        number_of_properties, property_atoms = xinput.list_properties(
            self.display, self.id)
        with scoped_pointer(property_atoms, xlib.free):
            for i in xrange(number_of_properties):
                yield Atom(self.display, property_atoms[i])

    def __iter__(self):
        """
        Iterate over the names of all properties defined for this device.

        Return a generator yielding the names of all properties of this
        device as unicode strings
        """
        return (a.name for a in self._iter_property_atoms())

    def __contains__(self, name):
        """
        Check, if the given property is defined on this device.

        ``name`` is the property name as string.

        Return ``True``, if the property is defined on this device,
        ``False`` otherwise.
        """
        atom = self.display.intern_atom(name)
        if atom is None:
            return False
        return any(a == atom for a in self._iter_property_atoms())

    def __getitem__(self, name):
        """
        Get the given property.

        Input device properties have multiple items and are of different types.
        This method returns all items in a list, and tries to convert them into
        the appropriate Python property_type.  Consequently, the conversion may
        fail, if the property has an unsupported property_type.  Currently,
        integer and float types are supported, any other property_type raises
        :exc:`PropertyTypeError`.

        ``name`` is the property name as string.

        Return all items of the given property as list, or raise
        :exc:`~exceptions.KeyError`, if the property is not defined on this
        device.  Raise :exc:`UndefinedPropertyError` (which is a subclass of
        :exc:`~exceptions.KeyError`), if the property is not defined on the
        server at all.  Raise :exc:`PropertyTypeError`, if the property has an
        unsupported property_type.
        """
        atom = _get_property_atom(self.display, name)
        property_type, property_format, data = xinput.get_property(
            self.display, self.id, atom)
        property_type = Atom(self.display, property_type)
        if not property_type and property_format == 0:
            raise KeyError(name)
        if property_type == self.display.types.string:
            # string types means to return the string data unchanged
            return [data]
        number_of_items = (len(data) * 8) // property_format
        if property_type in (self.display.types.integer,
                             self.display.types.atom):
            type_code = _TYPE_CODE_MAPPING[property_format]
        elif property_type == self.display.types.float:
            type_code = 'f'
        else:
            raise PropertyTypeError(property_type)
        return _unpack_property_data(type_code, number_of_items, data)

    def __gt__(self, other):
        raise TypeError('InputDevice not orderable')

    def __lt__(self, other):
        raise TypeError('InputDevice not orderable')

    def __le__(self, other):
        raise TypeError('InputDevice not orderable')

    def __ge__(self, other):
        raise TypeError('InputDevice not orderable')

    def _set_raw(self, property, type, format, data):
        atom = _get_property_atom(self.display, property)
        xinput.change_property(self.display, self.id, atom,
                               type, format, data)

    def set_int(self, property, values):
        """
        Set an integral ``property``.

        ``property`` is the property name as string, ``values`` is a list of
        *all* values of the property as integer.

        Raise :exc:`UndefinedPropertyError`, if the given property is not
        defined on the server.
        """
        data = _pack_property_data('L', values)
        self._set_raw(property, self.display.types.integer, 32, data)

    def set_byte(self, property, values):
        """
        Set a ``property``, whose values are single bytes.

        ``property`` is the property name as string, ``values`` is a list of
        *all* values of the property as integer, which must of course all be in
        the range of byte values.

        Raise :exc:`UndefinedPropertyError`, if the given property is not
        defined on the server.
        """
        data = _pack_property_data('B', values)
        self._set_raw(property, self.display.types.integer, 8, data)

    set_bool = set_byte

    def set_float(self, property, values):
        """
        Set a floating point ``property``.

        ``property`` is the property name as string, ``values`` is a list of
        *all* values of the property as float objects, which must all be in the
        range of C float values.

        Raise :exc:`UndefinedPropertyError`, if the given property is not
        defined on the server
        """
        data = _pack_property_data('f', values)
        self._set_raw(property, self.display.types.float, 32, data)