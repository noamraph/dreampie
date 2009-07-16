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
# along with Foobar.  If not, see <http://www.gnu.org/licenses/>.

"""
Send objects over a socket by marshalling them.
"""

__all__ = ['send_object', 'recv_object']

import marshal
import struct

def send_object(sock, obj):
    """Send an object over a socket"""
    s = marshal.dumps(obj)
    msg = struct.pack('<l', len(s)) + s
    sock.sendall(msg)

def recv_object(sock):
    """Receive an object over a socket"""
    length_str = ''
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
    s = ''.join(parts)
    obj = marshal.loads(s)
    return obj
