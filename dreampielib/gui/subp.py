__all__ = ['Subprocess']

import sys
import os
import time
import signal
from .subprocess_interact import Popen, PIPE
from select import select
import socket
import random
from logging import debug

import gobject

from ..common.objectstream import send_object, recv_object

class Subprocess(object):
    """
    Manage interaction with the subprocess.
    The communication, besides stdout, stderr and stdin, goes like this:
    You can call a function, and get a return value.
    (This sends over the tuple with the function name and parameters,
    and waits for the next object, which is the return value.)
    You can also get objects asyncronically.
    (This happens when not waiting for a function's return value.)
    
    Currently, this class doesn't support living without a living subprocess.
    This means that if the subprocess dies and can't be restarted, or if
    the subprocess can't be started on the first place, you get a fatal error.
    """

    def __init__(self, executable,
                 on_stdout_recv, on_stderr_recv, on_object_recv,
                 on_subp_restarted):
        self._executable = executable
        self._on_stdout_recv = on_stdout_recv
        self._on_stderr_recv = on_stderr_recv
        self._on_object_recv = on_object_recv
        self._on_subp_restarted = on_subp_restarted
        
        self._sock = None
        self._popen = None
        self._start()

        # I know that polling isn't the best way, but on Windows you have
        # no choice, and it allows us to do it all by ourselves, not use
        # gobject's functionality.
        gobject.timeout_add(10, self._manage_subp)
        
    def _start(self):
        # Find a socket to listen to
        ports = range(10000, 10100)
        random.shuffle(ports)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for port in ports:
            #debug("Trying to listen on port %d..." % port)
            try:
                s.bind(('localhost', port))
            except socket.error:
                #debug("Failed.")
                pass
            else:
                #debug("Ok.")
                break
        else:
            raise IOError("Couldn't find a port to bind to")
        # Now the socket is bound to port.

        #debug("Spawning subprocess")
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        if sys.stdout.encoding:
            env['PYTHONIOENCODING'] = sys.stdout.encoding
        popen = Popen([sys.executable,
                       self._executable, 'subprocess', str(port)],
                       stdin=PIPE, stdout=PIPE, stderr=PIPE,
                       env=env)
        #debug("Waiting for the subprocess to connect")
        s.listen(1)
        self._sock, addr = s.accept()
        #debug("Connected to addr %r." % (addr,))
        s.close()
        self._popen = popen

    def _manage_subp(self):
        popen = self._popen
        if popen is None:
            # Just continue looping, waiting for better times.
            return True

        # Check if exited
        rc = popen.poll()
        if rc is not None:
            debug("Process terminated with rc %r" % rc)
            self._sock.close()
            self._sock = None
            self._popen = None
            self._start()
            # Now, supposedly, we have a new, running process.
            self._on_subp_restarted()
            return True

        # Read from stdout
        r = popen.recv()
        if r is None:
            raise IOError("Error on receiving stdout from subprocess")
        if r:
            self._on_stdout_recv(r)

        # Read from stderr
        r = popen.recv_err()
        if r is None:
            raise IOError("Error on receiving stderr from subprocess")
        if r:
            self._on_stderr_recv(r)
        
        # Read from socket
        if select([self._sock], [], [], 0)[0]:
            obj = recv_object(self._sock)
            self._on_object_recv(obj)

        return True

    def send_object(self, obj):
        """Send an object to the subprocess"""
        send_object(self._sock, obj)

    def recv_object(self):
        """Wait for an object from the subprocess and return it"""
        return recv_object(self._sock)

    def write(self, data):
        """Write data to stdin"""
        self._popen.stdin.write(data)

    def kill(self):
        # Send SIGABRT, and if the process didn't terminate within 1 second,
        # send SIGKILL.
        # The subprocess will hopefully restart, if you continue with the event
        # loop.
        os.kill(self._popen.pid, signal.SIGABRT)
        killtime = time.time()
        while True:
            rc = self._popen.poll()
            if rc is not None:
                break
            if time.time() - killtime > 1:
                os.kill(self._popen.pid, signal.SIGKILL)
                break
            time.sleep(0.1)

    def interrupt(self):
        os.kill(self._popen.pid, signal.SIGINT)
