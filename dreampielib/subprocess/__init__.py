import sys
import socket
import codeop

from ..common.objectstream import send_object, recv_object
from .split_to_singles import split_to_singles

# import rpdb2; rpdb2.start_embedded_debugger('a')

debug_f = open('/tmp/dreampie_subp_debug', 'a', 0)
def debug(s):
    print >> debug_f, s

def main(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', port))

    compile = codeop.CommandCompiler()
    locs = {}

    while True:
        source = recv_object(sock)
        split_source = split_to_singles(source)
        # This added newline is because sometimes the CommandCompiler wants
        # more if there isn't a newline at the end
        split_source[-1] += '\n'
        debug(repr(split_source))
        split_code = []
        line_count = 0
        for src in split_source:
            try:
                c = compile(src, '<pyshell>', 'single')
            except SyntaxError, e:
                send_object(sock, (False, (e.msg,
                                           e.lineno-1+line_count, e.offset-1)))
                break
            else:
                if c is None:
                    send_object(sock, (False, None))
                    break
                else:
                    split_code.append(c)
                    line_count += src.count('\n')
        else:
            send_object(sock, (True, None))
            try:
                for c in split_code:
                    exec c in locs
            except (Exception, KeyboardInterrupt), e:
                send_object(sock, (False, str(e)))
            else:
                send_object(sock, (True, None))
