import sys
import os
import socket
from select import select
import codeop
from StringIO import StringIO
import linecache
import traceback
import types
import keyword
import __builtin__

from ..common.objectstream import send_object, recv_object
from .split_to_singles import split_to_singles

# import rpdb2; rpdb2.start_embedded_debugger('a')

import logging
from logging import debug
logging.basicConfig(filename='/tmp/dreampie_subp_log', level=logging.DEBUG)

rpc_funcs = set()
# A decorator which adds the function name to rpc_funcs
def rpc_func(func):
    rpc_funcs.add(func.func_name)
    return func

class Subprocess(object):
    def __init__(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', port))

        # Trick things like pdb into thinking that the namespace we create is
        # the main module
        mainmodule = types.ModuleType('__name__')
        sys.modules['__main__'] = mainmodule
        self.locs = mainmodule.__dict__

        self.compile = codeop.CommandCompiler()
        self.gid = 0

        while True:
            funcname, args = recv_object(sock)
            if funcname in rpc_funcs:
                func = getattr(self, funcname)
                r = func(*args)
                if isinstance(r, types.GeneratorType):
                    for obj in r:
                        send_object(sock, obj)
                else:
                    send_object(sock, r)
            else:
                raise ValueError("Unknown command: %s" % funcname)

    @rpc_func
    def execute(self, source):
        split_source = split_to_singles(source)
        # This added newline is because sometimes the CommandCompiler wants
        # more if there isn't a newline at the end
        split_source[-1] += '\n'
        line_count = 0
        # Compile to check for syntax errors
        for src in split_source:
            try:
                c = compile(src, '<pyshell>', 'single')
            except SyntaxError, e:
                yield False, (e.msg, e.lineno-1+line_count, e.offset-1)
                return
            else:
                if c is None:
                    yield False, None
                    return
                else:
                    line_count += src.count('\n')

        # If compilation was successfull...
        yield True, None
        is_success = True
        exception_string = None
        for src in split_source:
            # We compile again, so as not to put into linecache code
            # which had no effect
            filename = '<pyshell#%d>' % self.gid
            self.gid += 1
            lines = src.split("\n")
            linecache.cache[filename] = len(src)+1, None, lines, filename
            c = compile(src, filename, 'single')
            try:
                exec c in self.locs
            except (Exception, KeyboardInterrupt), e:
                sys.stdout.flush()
                linecache.checkcache()
                efile = StringIO()
                typ, val, tb = excinfo = sys.exc_info()
                sys.last_type, sys.last_value, sys.last_traceback = excinfo
                tbe = traceback.extract_tb(tb)
                my_filename = sys._getframe().f_code.co_filename
                if tbe[-1][0] != my_filename:
                    # If the last entry is from this file, don't remove
                    # anything. Otherwise, remove lines before the current
                    # frame.
                    for i in xrange(len(tbe)-2, -1, -1):
                        if tbe[i][0] == my_filename:
                            tbe = tbe[i+1:]
                            break
                print>>efile, 'Traceback (most recent call last):'
                traceback.print_list(tbe, file=efile)
                lines = traceback.format_exception_only(typ, val)
                for line in lines:
                    print>>efile, line,
                is_success = False
                exception_string = efile.getvalue()
                break
            
        # Send back any data left on stdin.
        rem_stdin = []
        while select([sys.stdin], [], [], 0)[0]:
            rem_stdin.append(os.read(sys.stdin.fileno(), 8192))
        rem_stdin = ''.join(rem_stdin)

        yield is_success, exception_string, rem_stdin


    @staticmethod
    def split_list(L, public_set):
        """
        split L into two lists: public and private, according to public_set,
        which should be a set of names or None. If it's None, split according
        to whether the first char is '_'.
        """
        public = []
        private = []
        if public_set is not None:
            for x in L:
                if x in public_set:
                    public.append(x)
                else:
                    private.append(x)
        else:
            for x in L:
                if not x.startswith('_'):
                    public.append(x)
                else:
                    private.append(x)
        return public, private

    @rpc_func
    def complete_attributes(self, expr):
        """
        Evaluate expr in the namespace, and return its attributes as two
        sorted lists - public and private.
        public - completions that are thought to be relevant.
        private - completions that are not so.
        If expr == '', return first-level completions.
        """
        if expr == '':
            try:
                namespace = self.locs.copy()
                namespace.update(__builtin__.__dict__)
                ids = eval("dir()", namespace) + keyword.kwlist
                ids.sort()
                if '__all__' in namespace:
                    all_set = set(namespace['__all__'])
                else:
                    all_set = None
                public, private = self.split_list(ids, all_set)
            except Exception, e:
                public = private = []
                import traceback
                traceback.print_exc()
        else:
            try:
                entity = eval(expr, self.locs)
                ids = dir(entity)
                ids.sort()
                if hasattr(entity, '__all__'):
                    all_set = set(entity.__all__)
                else:
                    all_set = None
                public, private = self.split_list(ids, all_set)
            except Exception, e:
                public = private = []

        return public, private


def main(port):
    subp = Subprocess(port)
