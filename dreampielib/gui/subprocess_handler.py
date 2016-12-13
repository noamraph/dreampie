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

__all__ = ['SubprocessHandler']

import sys
import os
import time
if sys.platform != 'win32':
    import signal
else:
    import ctypes
from .subprocess_interact import Popen, PIPE
from select import select
import socket
import random
from logging import debug

import gobject

from ..common.objectstream import send_object, recv_object

_ = lambda s: s

START_TIMEOUT = 30 # seconds

class StartError(IOError):
    """Error when starting subprocess"""
    pass

class StartTerminatedError(StartError):
    """Start subprocess failed because process terminated."""
    def __init__(self, rc, output):
        self.rc = rc
        self.output = output
    def __str__(self):
        r = _("Subprocess terminated with return code %d.") % self.rc
        if self.output:
            r += _("\nSubprocess wrote:\n%s") % self.output
        return r

class StartTimeoutError(StartError):
    """Start subprocess failed because timeout elapsed."""
    def __init__(self, timeout, output):
        self.timeout = timeout
        self.output = output
    def __str__(self):
        r = _("Subprocess didn't call back in %s seconds. "
              "This may be caused by a firewall program blocking the "
              "communication between the main process and the subproces."
              ) % self.timeout
        if self.output:
            r += _("\nSubprocess wrote:\n%s") % self.output
        return r

class SubprocessHandler(object):
    """
    Manage interaction with the subprocess.
    The communication, besides stdout, stderr and stdin, goes like this:
    You can call a function, and get a return value.
    (This sends over the tuple with the function name and parameters,
    and waits for the next object, which is the return value.)
    You can also get objects asyncronically.
    (This happens when not waiting for a function's return value.)
    """

    def __init__(self, pyexec, data_dir,
                 on_stdout_recv, on_stderr_recv, on_object_recv,
                 on_subp_terminated):
        self._pyexec = pyexec
        self._data_dir = data_dir
        self._on_stdout_recv = on_stdout_recv
        self._on_stderr_recv = on_stderr_recv
        self._on_object_recv = on_object_recv
        self._on_subp_terminated = on_subp_terminated
        
        self._sock = None
        # self._popen is None when there's no subprocess
        self._popen = None
        self._last_kill_time = 0
        
        # I know that polling isn't the best way, but on Windows you have
        # no choice, and it allows us to do it all by ourselves, not use
        # gobject's functionality.
        gobject.timeout_add(10, self._manage_subp)
        
    def start(self):
        if self._popen is not None:
            raise ValueError("Subprocess is already living")
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
        env['PYTHONIOENCODING'] = 'UTF-8'
        script = os.path.join(self._data_dir, 'subp_main.py')
        # The -S switch causes the subprocess to not automatically import
        # site.py. This is done so that the subprocess will be able to call
        # sys.setdefaultencoding('UTF-8') before importing site, and this is
        # needed because Python 2.5 ignores the PYTHONIOENCODING variable.
        # Hopefully it won't cause problems.
        popen = Popen([self._pyexec, '-S', script, str(port)],
                       stdin=PIPE, stdout=PIPE, stderr=PIPE,
                       env=env)
        #debug("Waiting for the subprocess to connect")
        s.listen(1)
        # We wait for the client to connect, but we also poll stdout and stderr,
        # and if it writes something then we report an error.
        s.settimeout(0.1)
        start_time = time.time()
        while True:
            try:
                self._sock, _addr = s.accept()
            except socket.timeout:
                pass
            else:
                break
            
            rc = popen.poll()
            if rc is not None:
                out = (popen.recv() or '') + (popen.recv_err() or '')
                raise StartTerminatedError(rc, out)
            
            if time.time() - start_time > START_TIMEOUT:
                out = (popen.recv() or '') + (popen.recv_err() or '')
                raise StartTimeoutError(START_TIMEOUT, out)
        self._sock.setblocking(True)
            
        #debug("Connected to addr %r." % (addr,))
        s.close()
        self._popen = popen

    def _manage_subp(self):
        popen = self._popen
        if popen is None:
            # Just continue looping - there's no subprocess.
            return True

        # Check if exited
        rc = popen.poll()
        if rc is not None:
            if time.time() - self._last_kill_time > 10:
                debug("Process terminated unexpectedly with rc %r" % rc)
            self._sock.close()
            self._sock = None
            self._popen = None
            self._on_subp_terminated()
            return True

        # Read from stdout
        r = popen.recv()
        if r:
            self._on_stdout_recv(r.decode('utf8', 'replace'))

        # Read from stderr
        r = popen.recv_err()
        if r:
            self._on_stderr_recv(r.decode('utf8', 'replace'))
        
        # Read from socket
        if self.wait_for_object(0):
            try:
                obj = recv_object(self._sock)
            except IOError:
                # Could happen when subprocess exits. See bug #525358.
                # We give the subprocess a second. If it shuts down, we ignore
                # the exception, since on the next round we will handle that.
                # Otherwise, the exception remains unexplained so we re-raise.
                time.sleep(1)
                if popen.poll() is None:
                    raise
            else:
                self._on_object_recv(obj)

        return True

    def send_object(self, obj):
        """Send an object to the subprocess"""
        if self._popen is None:
            raise ValueError("Subprocess not living")
        send_object(self._sock, obj)

    def wait_for_object(self, timeout_s):
        """
        Wait for timeout_s seconds or until the socket is ready for reading.
        Return True if an object was received, and False if the timeout expired.
        """
        return len(select([self._sock], [], [], timeout_s)[0]) > 0
    
    def recv_object(self):
        """Wait for an object from the subprocess and return it"""
        if self._popen is None:
            raise ValueError("Subprocess not living")
        return recv_object(self._sock)

    def write(self, data):
        """Write data to stdin"""
        if self._popen is None:
            raise ValueError("Subprocess not living")
        self._popen.stdin.write(data.encode('utf8'))

    def kill(self):
        """Kill the subprocess.
        If the event loop continues, will start another one."""
        if self._popen is None:
            raise ValueError("Subprocess not living")
        if sys.platform != 'win32':
            # Send SIGTERM, and if the process didn't terminate within 1 second,
            # send SIGKILL.
            os.kill(self._popen.pid, signal.SIGTERM)
            killtime = time.time()
            while True:
                rc = self._popen.poll()
                if rc is not None:
                    break
                if time.time() - killtime > 1:
                    os.kill(self._popen.pid, signal.SIGKILL)
                    break
                time.sleep(0.1)
        else:
            kernel32 = ctypes.windll.kernel32
            PROCESS_TERMINATE = 1
            handle = kernel32.OpenProcess(PROCESS_TERMINATE, False,
                                          self._popen.pid)
            kernel32.TerminateProcess(handle, -1)
            kernel32.CloseHandle(handle)
        self._last_kill_time = time.time()

    def interrupt(self):
        if self._popen is None:
            raise ValueError("Subprocess not living")
        if sys.platform != 'win32':
            pid = self._popen.pid
            if os.getpgid(pid) == pid:
                # If the subprocess managed to become a process group leader,
                # send the signal to the entire group (this is what happens
                # in terminals)
                os.killpg(pid, signal.SIGINT)
            else:
                os.kill(pid, signal.SIGINT)
        else:
            kernel32 = ctypes.windll.kernel32
            CTRL_C_EVENT = 0
            try:
                kernel32.GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)
                time.sleep(10)
            except KeyboardInterrupt:
                # This also sends us a KeyboardInterrupt. It should
                # happen in time.sleep.
                pass

