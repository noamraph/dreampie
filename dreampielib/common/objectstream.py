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
