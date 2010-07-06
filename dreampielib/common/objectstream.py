# Copyright 2009 Noam Yorav-Raphael
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
Send objects over a socket by brining them.
"""

__all__ = ['send_object', 'recv_object']

import sys
py3k = (sys.version_info[0] == 3)
import struct

# This was "from . import brine", but a bug in 2to3 in Python 2.6.5
# converted it to "from .. import brine", so I changed that.
from ..common import brine

if not py3k:
    empty_bytes = ''
else:
    empty_bytes = bytes()

def send_object(sock, obj):
    """Send an object over a socket"""
    s = brine.dump(obj)
    msg = struct.pack('<l', len(s)) + s
    sock.sendall(msg)

def recv_object(sock):
    """Receive an object over a socket"""
    length_str = empty_bytes
    while len(length_str) < 4:
        r = sock.recv(4 - len(length_str))
        if not r:
            raise IOError("Socket closed unexpectedly")
        length_str += r
    length, = struct.unpack('<i', length_str)
    parts = []
    len_received = 0
    while len_received < length:
        r = sock.recv(length - len_received)
        if not r:
            raise IOError("Socket closed unexpectedly")
        parts.append(r)
        len_received += len(r)
    s = empty_bytes.join(parts)
    obj = brine.load(s)
    return obj
