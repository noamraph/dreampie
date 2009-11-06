#!/usr/bin/env python

# Interact with the subprocess without a big GUI program

import sys
import os
from select import select
import socket
from subprocess import Popen, PIPE
import random
import time

from dreampielib.common.objectstream import send_object, recv_object

def debug(s):
    print >> sys.stderr, s

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print >> sys.stderr, "Usage: %s executable" % sys.argv[0]
        sys.exit(1)
    executable = sys.argv[1:]
    
    # Find a socket to listen to
    ports = range(10000, 10100)
    random.shuffle(ports)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for port in ports:
        debug("Trying to listen on port %d..." % port)
        try:
            s.bind(('localhost', port))
        except socket.error:
            debug("Failed.")
            pass
        else:
            debug("Ok.")
            break
    else:
        raise IOError("Couldn't find a port to bind to")
    # Now the socket is bound to port.

    debug("Spawning subprocess")
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    popen = Popen(executable + [str(port)],
                  stdin=PIPE, stdout=PIPE, #stderr=PIPE,
                  close_fds=True, env=env)
    debug("Waiting for an answer")
    s.listen(1)
    sock, addr = s.accept()
    debug("Connected to addr %r!" % (addr,))
    s.close()

    # Start the play
    while True:
        time.sleep(0.01)

        # Check if exited
        rc = popen.poll()
        if rc is not None:
            print 'Process terminated with rc %r' % rc
            break

        # Read from stdout, stderr, and socket
        #ready, _, _ = select([sys.stdin, popen.stdout, popen.stderr, sock], [], [], 0)
        ready, _, _ = select([sys.stdin, popen.stdout, sock], [], [], 0)

        if sys.stdin in ready:
            line = sys.stdin.readline()
            if not line:
                break
            obj = eval(line)
            send_object(sock, obj)

        if popen.stdout in ready:
            r = []
            while True:
                r.append(os.read(popen.stdout.fileno(), 8192))
                if not select([popen.stdout], [], [], 0)[0]:
                    break
            r = ''.join(r)
            print 'stdout: %r' % r
                
        if popen.stderr in ready:
            r = []
            while True:
                r.append(os.read(popen.stderr.fileno(), 8192))
                if not select([popen.stderr], [], [], 0)[0]:
                    break
            r = ''.join(r)
            print 'stderr: %r' % r
        
        if sock in ready:
            obj = recv_object(sock)
            print 'obj: %r' % (obj,)

if __name__ == '__main__':
    main()
