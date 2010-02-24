# This file is based on brine.py from RPyC.
# See http://rpyc.wikidot.com/
# and http://sebulbasvn.googlecode.com/svn/tags/rpyc/3.0.6/core/brine.py
# Modified by Noam Yorav-Raphael for DreamPie use.

# Copyright (c) 2005-2009
# Tomer Filiba (tomerfiliba@gmail.com)
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# Copyright 2010 Noam Yorav-Raphael
#
# This file is part of DreamPie.
# 
# DreamPie is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# DreamPie is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with DreamPie.  If not, see <http://www.gnu.org/licenses/>.

"""
brine - a simple, fast and secure object serializer,
optimized for small integers [-48..160), suitable for Python 2/3k communication.
the following types are supported: int (in the unsigned long range), bool,
unicode (In Py2) / str (In Py3), float, slice, complex, tuple(of simple types),
list(of simple types), frozenset(of simple types)
as well as the following singletons: None, NotImplemented, Ellipsis
"""
import sys
py3k = (sys.version_info[0] == 3)
if not py3k:
    from cStringIO import StringIO
else:
    from io import BytesIO
from struct import Struct

if not py3k:
    def b(n):
        return chr(n)
    empty_bytes = ''
else:
    def b(n):
        return bytes([n])
    empty_bytes = bytes()

# singletons
TAG_NONE = b(0x00)
TAG_EMPTY_STR = b(0x01)
TAG_EMPTY_TUPLE = b(0x02)
TAG_TRUE = b(0x03)
TAG_FALSE = b(0x04)
TAG_NOT_IMPLEMENTED = b(0x05)
TAG_ELLIPSIS = b(0x06)
# types
#TAG_UNICODE = b(0x08) # Removed - STR is unicode.
#TAG_LONG = b(0x09) # Removed
TAG_STR1 = b(0x0a)
TAG_STR2 = b(0x0b)
TAG_STR3 = b(0x0c)
TAG_STR4 = b(0x0d)
TAG_STR_L1 = b(0x0e)
TAG_STR_L4 = b(0x0f)
TAG_TUP1 = b(0x10)
TAG_TUP2 = b(0x11)
TAG_TUP3 = b(0x12)
TAG_TUP4 = b(0x13)
TAG_TUP_L1 = b(0x14)
TAG_TUP_L4 = b(0x15)
TAG_INT_L1 = b(0x16)
TAG_INT_L4 = b(0x17)
TAG_FLOAT = b(0x18)
TAG_SLICE = b(0x19)
TAG_FSET = b(0x1a)
TAG_COMPLEX = b(0x1b)

# List
TAG_EMPTY_LIST = b(0x1c)
TAG_LIST1 = b(0x1d)
TAG_LIST_L1 = b(0x1e)
TAG_LIST_L4 = b(0x1f)

IMM_INTS = dict((i, b(i + 0x50)) for i in range(-0x30, 0xa0))

I1 = Struct("!B")
I4 = Struct("!L")
F8 = Struct("!d")
C16 = Struct("!dd")

_dump_registry = {}
_load_registry = {}
IMM_INTS_LOADER = dict((v, k) for k, v in IMM_INTS.iteritems())

def register(coll, key):
    def deco(func):
        coll[key] = func
        return func
    return deco

#===============================================================================
# dumping
#===============================================================================
@register(_dump_registry, type(None))
def _dump_none(_obj, stream):
    stream.append(TAG_NONE)

@register(_dump_registry, type(NotImplemented))
def _dump_notimplemeted(_obj, stream):
    stream.append(TAG_NOT_IMPLEMENTED)

@register(_dump_registry, type(Ellipsis))
def _dump_ellipsis(_obj, stream):
    stream.append(TAG_ELLIPSIS)

@register(_dump_registry, bool)
def _dump_bool(obj, stream):
    if obj:
        stream.append(TAG_TRUE)
    else:
        stream.append(TAG_FALSE)

@register(_dump_registry, slice)
def _dump_slice(obj, stream):
    stream.append(TAG_SLICE)
    _dump((obj.start, obj.stop, obj.step), stream)

@register(_dump_registry, frozenset)
def _dump_frozenset(obj, stream):
    stream.append(TAG_FSET)
    _dump(tuple(obj), stream)

@register(_dump_registry, int)
def _dump_int(obj, stream):
    if obj in IMM_INTS:
        stream.append(IMM_INTS[obj])
    else:
        obj = str(obj)
        l = len(obj)
        if l < 256:
            stream.append(TAG_INT_L1 + I1.pack(l) + obj)
        else:
            stream.append(TAG_INT_L4 + I4.pack(l) + obj)

#@register(_dump_registry, long)
#def _dump_long(obj, stream):
#    stream.append(TAG_LONG)
#    _dump_int(obj, stream)

@register(_dump_registry, unicode)
def _dump_str(obj, stream):
    obj = obj.encode('utf8')
    l = len(obj)
    if l == 0:
        stream.append(TAG_EMPTY_STR)
    elif l == 1:
        stream.append(TAG_STR1 + obj)
    elif l == 2:
        stream.append(TAG_STR2 + obj)
    elif l == 3:
        stream.append(TAG_STR3 + obj)
    elif l == 4:
        stream.append(TAG_STR4 + obj)
    elif l < 256:
        stream.append(TAG_STR_L1 + I1.pack(l) + obj)
    else:
        stream.append(TAG_STR_L4 + I4.pack(l) + obj)

@register(_dump_registry, float)
def _dump_float(obj, stream):
    stream.append(TAG_FLOAT + F8.pack(obj))

@register(_dump_registry, complex)
def _dump_complex(obj, stream):
    stream.append(TAG_COMPLEX + C16.pack(obj.real, obj.imag))

#@register(_dump_registry, unicode)
#def _dump_unicode(obj, stream):
#    stream.append(TAG_UNICODE)
#    _dump_str(obj.encode("utf8"), stream)

@register(_dump_registry, tuple)
def _dump_tuple(obj, stream):
    l = len(obj)
    if l == 0:
        stream.append(TAG_EMPTY_TUPLE)
    elif l == 1:
        stream.append(TAG_TUP1)
    elif l == 2:
        stream.append(TAG_TUP2)
    elif l == 3:
        stream.append(TAG_TUP3)
    elif l == 4:
        stream.append(TAG_TUP4)
    elif l < 256:
        stream.append(TAG_TUP_L1 + I1.pack(l))
    else:
        stream.append(TAG_TUP_L4 + I4.pack(l))
    for item in obj:
        _dump(item, stream)

@register(_dump_registry, list)
def _dump_list(obj, stream):
    l = len(obj)
    if l == 0:
        stream.append(TAG_EMPTY_LIST)
    elif l == 1:
        stream.append(TAG_LIST1)
    elif l < 256:
        stream.append(TAG_LIST_L1 + I1.pack(l))
    else:
        stream.append(TAG_LIST_L4 + I4.pack(l))
    for item in obj:
        _dump(item, stream)

def _undumpable(obj, stream):
    raise TypeError("cannot dump %r" % (obj,))

def _dump(obj, stream):
    _dump_registry.get(type(obj), _undumpable)(obj, stream)

#===============================================================================
# loading
#===============================================================================
@register(_load_registry, TAG_NONE)
def _load_none(_stream):
    return None
@register(_load_registry, TAG_NOT_IMPLEMENTED)
def _load_nonimp(_stream):
    return NotImplemented
@register(_load_registry, TAG_ELLIPSIS)
def _load_elipsis(_stream):
    return Ellipsis
@register(_load_registry, TAG_TRUE)
def _load_true(_stream):
    return True
@register(_load_registry, TAG_FALSE)
def _load_false(_stream):
    return False
@register(_load_registry, TAG_EMPTY_TUPLE)
def _load_empty_tuple(_stream):
    return ()
@register(_load_registry, TAG_EMPTY_LIST)
def _load_empty_list(_stream):
    return []
@register(_load_registry, TAG_EMPTY_STR)
def _load_empty_str(_stream):
    return u""
#@register(_load_registry, TAG_UNICODE)
#def _load_unicode(stream):
#    obj = _load(stream)
#    return obj.decode("utf-8")
#@register(_load_registry, TAG_LONG)
#def _load_long(stream):
#    obj = _load(stream)
#    return long(obj)

@register(_load_registry, TAG_FLOAT)
def _load_float(stream):
    return F8.unpack(stream.read(8))[0]
@register(_load_registry, TAG_COMPLEX)
def _load_complex(stream):
    real, imag = C16.unpack(stream.read(16))
    return complex(real, imag)

@register(_load_registry, TAG_STR1)
def _load_str1(stream):
    return stream.read(1).decode('utf8')
@register(_load_registry, TAG_STR2)
def _load_str2(stream):
    return stream.read(2).decode('utf8')
@register(_load_registry, TAG_STR3)
def _load_str3(stream):
    return stream.read(3).decode('utf8')
@register(_load_registry, TAG_STR4)
def _load_str4(stream):
    return stream.read(4).decode('utf8')
@register(_load_registry, TAG_STR_L1)
def _load_str_l1(stream):
    l, = I1.unpack(stream.read(1))
    return stream.read(l).decode('utf8')
@register(_load_registry, TAG_STR_L4)
def _load_str_l4(stream):
    l, = I4.unpack(stream.read(4))
    return stream.read(l).decode('utf8')

@register(_load_registry, TAG_TUP1)
def _load_tup1(stream):
    return (_load(stream),)
@register(_load_registry, TAG_TUP2)
def _load_tup2(stream):
    return (_load(stream), _load(stream))
@register(_load_registry, TAG_TUP3)
def _load_tup3(stream):
    return (_load(stream), _load(stream), _load(stream))
@register(_load_registry, TAG_TUP4)
def _load_tup4(stream):
    return (_load(stream), _load(stream), _load(stream), _load(stream))
@register(_load_registry, TAG_TUP_L1)
def _load_tup_l1(stream):
    l, = I1.unpack(stream.read(1))
    return tuple(_load(stream) for i in range(l))
@register(_load_registry, TAG_TUP_L4)
def _load_tup_l4(stream):
    l, = I4.unpack(stream.read(4))
    return tuple(_load(stream) for i in xrange(l))

@register(_load_registry, TAG_LIST1)
def _load_list1(stream):
    return [_load(stream)]
@register(_load_registry, TAG_LIST_L1)
def _load_list_l1(stream):
    l, = I1.unpack(stream.read(1))
    return list(_load(stream) for i in range(l))
@register(_load_registry, TAG_LIST_L4)
def _load_list_l4(stream):
    l, = I4.unpack(stream.read(4))
    return list(_load(stream) for i in xrange(l))


@register(_load_registry, TAG_SLICE)
def _load_slice(stream):
    start, stop, step = _load(stream)
    return slice(start, stop, step)
@register(_load_registry, TAG_FSET)
def _load_frozenset(stream):
    return frozenset(_load(stream))

@register(_load_registry, TAG_INT_L1)
def _load_int_l1(stream):
    l, = I1.unpack(stream.read(1))
    return int(stream.read(l))
@register(_load_registry, TAG_INT_L4)
def _load_int_l4(stream):
    l, = I4.unpack(stream.read(4))
    return int(stream.read(l))

def _load(stream):
    tag = stream.read(1)
    if tag in IMM_INTS_LOADER:
        return IMM_INTS_LOADER[tag]
    return _load_registry.get(tag)(stream)

#===============================================================================
# API
#===============================================================================
def dump(obj):
    """dumps the given object to a byte-string representation"""
    stream = []
    _dump(obj, stream)
    return empty_bytes.join(stream)

def load(data):
    """loads the given byte-string representation to an object"""
    if not py3k:
        stream = StringIO(data)
    else:
        stream = BytesIO(data)
    return _load(stream)


simple_types = frozenset([type(None), int, long, bool, str, float, unicode, 
    slice, complex, type(NotImplemented), type(Ellipsis)])
def dumpable(obj):
    """indicates whether the object is dumpable by brine"""
    if type(obj) in simple_types:
        return True
    if type(obj) in (tuple, list, frozenset):
        return all(dumpable(item) for item in obj)
    return False


if __name__ == "__main__":
    x = (u"he", 7, u"llo", 8, (), 900, None, True, Ellipsis, 18.2, 18.2j + 13, 
        slice(1,2,3), frozenset([5,6,7]), [8,9,10], NotImplemented)
    assert dumpable(x)
    y = dump(x)
    z = load(y)
    assert x == z
    








