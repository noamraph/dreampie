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

from __future__ import with_statement
import sys
py3k = (sys.version_info[0] == 3)
import os
import time
import socket
from select import select
from StringIO import StringIO
import linecache
import traceback
import types
import keyword
import __builtin__
import inspect
import pydoc
import pprint
import codeop
import signal
from contextlib import contextmanager
from itertools import chain
try:
    # Executing multiple statements in 'single' mode (print results) is done
    # with the ast module. Python 2.5 doesn't have it, so we use the compiler
    # module, which also seems to work. Jython 2.5 does have the ast module,
    # which is fortunate, because the 'compiler module trick' doesn't work there.
    import ast
except ImportError:
    ast = None
else:
    # IronPython 2.7.1 has the ast module, but can't compile from an AST.
    # If that's the case, the ast module doesn't interest us.
    try:
        compile(compile('a', 'fn', 'exec', ast.PyCF_ONLY_AST), 'fn', 'exec')
    except TypeError:
        ast = None
if ast is None:
    from .split_to_singles import split_to_singles
import __future__

if sys.platform == 'win32':
    from msvcrt import get_osfhandle #@UnresolvedImport
    from ctypes import byref, c_ulong, windll
    PeekNamedPipe = windll.kernel32.PeekNamedPipe #@UndefinedVariable

from .trunc_traceback import trunc_traceback
from .find_modules import find_modules
# We don't use relative import because of a Jython 2.5.1 bug.
from dreampielib.common.objectstream import send_object, recv_object

#import rpdb2; rpdb2.start_embedded_debugger('a')

import logging
from logging import debug
#logging.basicConfig(filename='/tmp/dreampie_subp_log', level=logging.DEBUG)

# time interval to process GUI events, in seconds
GUI_SLEEP = 0.1

# Maximum result string length to transmit
MAX_RES_STR_LEN = 1000000

rpc_funcs = set()
# A decorator which adds the function name to rpc_funcs
def rpc_func(func):
    rpc_funcs.add(func.func_name)
    return func

# Taken from codeop.py
PyCF_DONT_IMPLY_DEDENT = 0x200
_features = [getattr(__future__, fname)
             for fname in __future__.all_feature_names]

case_insen_filenames = (os.path.normcase('A') == 'a')

def unicodify(s):
    """Fault-tolerant conversion to unicode"""
    return s if isinstance(s, unicode) else s.decode('utf8', 'replace')

class PlainTextDoc(pydoc.TextDoc):
    """pydoc.TextDoc returns strange bold text, so we disable it."""
    def bold(self, text):
        return text
textdoc = PlainTextDoc()

# A mapping from id of types to boolean: is the type callable only.
# We use ids instead of weakrefs because old classes aren't weakrefable,
# and because we don't want to rely on weakref. This will fail if a type
# was deleted and another was created at the same memory address, but this
# seems unlikely.
is_callable_cache = {}
# magic methods for objects with defined operators
operator_methods = ['__%s__' % s for s in
                    'add sub mul div floordiv truediv mod divmod pow lshift '
                    'rshift and xor or'.split()]

quit_msg = """\
Press Ctrl-Q or close the window if you want to quit DreamPie.
Press Ctrl-F6 if you want to restart the subprocess."""
class Quit(object):
    def __repr__(self):
        return quit_msg
    def __call__(self):
        raise RuntimeError(quit_msg)

_simple_types = (
    bool, int, float, complex, type(None), slice,
    long, # 2to3 replaces long with int, so this is fine
    )
_string_types = (
    bytes if py3k else str, # 2to3 can't replace str with bytes
    unicode, # 2to3 replaces unicode with str, so this is fine
    )
def is_key_reprable(obj, max_depth=2):
    """
    Check whether an object (which is a dict key) simple enough
    to be used in the completion list.
    This checks that it's of simple types, and has some arbitrary limits.
    """
    if type(obj) in _simple_types:
        return True
    elif type(obj) in _string_types:
        return len(obj) < 1000
    elif type(obj) in (tuple, frozenset):
        if max_depth <= 0 or len(obj) > 5:
            return False
        else:
            return all(is_key_reprable(x, max_depth-1) for x in obj)
    else:
        return False

# SIGINT masking

def can_mask_sigint():
    return sys.platform in ('linux2', 'win32')

def unmask_sigint():
    # We want to mask ctrl-c events when not running user code, to allow
    # the main process to send a SIGINT anytime, in order to allow it to
    # break GUI code executed when idle.
    # If we can't mask ctrl-c events, the main process will only send
    # SIGINT when executing user code (it uses the get_subprocess_info
    # method to know that.)
    # Also, on win32 we may get unwanted ctrl-c events if the user is
    # running a subprocess. Since all processes in the same "console group"
    # get the event, the subprocess may get it before us and exit. Then we 
    # get out of the try-except block, and only later we get the ctrl-c.
    if sys.platform == 'linux2':
        signal.signal(signal.SIGINT, signal.default_int_handler)
    elif sys.platform == 'win32':
        windll.kernel32.SetConsoleCtrlHandler(None, False) #@UndefinedVariable
    else:
        pass

def mask_sigint():
    if sys.platform == 'linux2':
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    elif sys.platform == 'win32':
        windll.kernel32.SetConsoleCtrlHandler(None, True) #@UndefinedVariable
    else:
        pass

class Subprocess(object):
    def __init__(self, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(('localhost', port))

        # Mask SIGINT/Ctrl-C
        mask_sigint()
        
        # Become a process group leader
        if sys.platform != 'win32':
            os.setpgrp()
        
        # Make sys.displayhook change self.last_res
        self.last_res = None
        sys.displayhook = self.displayhook

        # Trick things like pdb into thinking that the namespace we create is
        # the main module
        mainmodule = types.ModuleType('__main__')
        sys.modules['__main__'] = mainmodule
        self.locs = mainmodule.__dict__
        
        # Add '' to sys.path, to be like the regular Python interpreter
        sys.path.insert(0, '')
        
        # Set sys.argv to [''], to be like the regular Python interpreter
        # (Otherwise multiprocessing on win32 starts running subp_main.py)
        sys.argv = ['']

        # Adjust exit and quit objects
        __builtin__.exit = __builtin__.quit = Quit()
        
        self.gui_handlers = [GtkHandler(), GIHandler(), Qt4Handler(), TkHandler()]
        self.idle_paused = False

        self.gid = 0
        self.flags = 0
        
        # Config
        self.is_pprint = False
        self.is_matplotlib_ia_switch = False
        self.is_matplotlib_ia_warn = False
        self.reshist_size = 0
        
        # Did we already handle matplotlib in non-interactive mode?
        self.matplotlib_ia_handled = False
        
        # The result history index of the next value to enter the history
        self.reshist_counter = 0

        # Run endless loop
        self.loop()

    def loop(self):
        while True:
            if not self.idle_paused:
                self.handle_gui_events(self.sock)
            funcname, args = recv_object(self.sock)
            if funcname in rpc_funcs:
                func = getattr(self, funcname)
                try:
                    r = func(*args)
                    if isinstance(r, types.GeneratorType):
                        for obj in r:
                            send_object(self.sock, obj)
                    else:
                        send_object(self.sock, r)
                except Exception:
                    # This may help in debugging exceptions.
                    traceback.print_exc()
                    send_object(self.sock, None)
            else:
                # aid in debug
                sys.stderr.write("Unknown command: %s\n" % funcname)
                send_object(self.sock, None)

    def displayhook(self, res):
        if res is not None:
            self.last_res = res

    def handle_gui_events(self, sock):
        """
        Handle GUI events until there's something to read from sock.
        If there's no graphic toolkit, just return.
        """
        sock.setblocking(False)
        try:
            while not select([sock], [], [], 0)[0]:
                executed = False
                for handler in self.gui_handlers:
                    cur_executed = handler.handle_events(GUI_SLEEP)
                    executed = executed or cur_executed
                if not executed:
                    break
        finally:
            sock.setblocking(True)

    @rpc_func
    def is_incomplete(self, source):
        """
        Get a string of code. Return True if it's incomplete and False
        otherwise (if it's complete or if there's a syntax error.)
        This is used to run single-line statements without need for
        ctrl+enter.
        """
        try:
            r = codeop.compile_command(source)
        except (SyntaxError, OverflowError, ValueError):
            return False
        return (r is None)
    
    @staticmethod
    def update_features(cur_flags, co_flags):
        """
        Get an int with current __future__ flags, return it updated with
        co_flags from a code object.
        """
        for feature in _features:
            if co_flags & feature.compiler_flag:
                cur_flags |= feature.compiler_flag
        return cur_flags
    
    def compile_ast(self, source):
        """
        Compile source into a list of code objects, updating linecache, self.gid
        and self.flags.
        Return True, codeob on success.
        Return False, reason on syntax error.
        This version uses the ast module available in Python 2.6 and Jython 2.5.
        This version always returns a list with one item.
        """
        filename = '<pyshell#%d>' % self.gid
        try:
            a = compile(source, filename, 'exec',
                        ast.PyCF_ONLY_AST | self.flags)
            b = ast.Interactive(a.body)
            codeob = compile(b, filename, 'single', self.flags)
        except SyntaxError, e:
            # Sometimes lineno or offset are not defined. Zero them in that case.
            lineno = e.lineno if e.lineno is not None else 1
            offset = e.offset if e.offset is not None else 1
            return False, (unicode(e.msg), lineno-1, offset-1)
        except ValueError, e:
            # Compiling "\x%" raises a ValueError
            return False, (unicode(e), 0, 0)
            
        # Update gid, linecache, flags
        self.gid += 1
        lines = [x+'\n' for x in source.split("\n")]
        linecache.cache[filename] = len(source)+1, None, lines, filename
        self.flags = self.update_features(self.flags, codeob.co_flags)
        
        return True, [codeob]
    
    def compile_no_ast(self, source):
        """
        This function does the same thing as compile_ast, but it works without
        the ast module.
        """
        split_source = split_to_singles(source)
        # This added newline is because sometimes the CommandCompiler wants
        # more if there isn't a newline at the end
        split_source[-1] += '\n'
        line_count = 0
        # Compile to check for syntax errors
        cur_flags = self.flags
        for src in split_source:
            try:
                c = compile(src, '<pyshell>', 'single', cur_flags)
            except SyntaxError, e:
                # Sometimes lineno or offset are not defined. Zero them in that
                # case.
                lineno = e.lineno if e.lineno is not None else 1
                offset = e.offset if e.offset is not None else 1
                msg = unicodify(e.msg)
                return False, (msg, lineno-1+line_count, offset-1)
            except ValueError, e:
                # Compiling "\x%" raises a ValueError
                return False, (unicode(e), 0, 0)
            else:
                if c is None:
                    return False, None
                    return
                else:
                    line_count += src.count('\n')
                    cur_flags = self.update_features(cur_flags, c.co_flags)

        # If compilation was successful...
        codeobs = []
        for src in split_source:
            # We compile again, so as not to put into linecache code
            # which had no effect
            filename = '<pyshell#%d>' % self.gid
            self.gid += 1
            lines = [x+'\n' for x in src.split("\n")]
            linecache.cache[filename] = len(src)+1, None, lines, filename
            codeob = compile(src, filename, 'single', self.flags)
            self.flags = self.update_features(self.flags, codeob.co_flags)
            codeobs.append(codeob)
        
        return True, codeobs
    
    @staticmethod
    def safe_pformat(obj):
        """
        Use pprint to format an object.
        In case of an exception, warn and use regular repr instead.
        """
        try:
            return unicode(pprint.pformat(obj))
        except:
            from warnings import warn
            warn('pprint raised an exception, using repr instead. '
                 'To reproduce, run: "from pprint import pprint; pprint(_)"')
            return unicode(repr(obj))
    
    @rpc_func
    def execute(self, source):
        """
        Get the source code to execute (a unicode string).
        Compile it. If there was a syntax error, return
        (False, (msg, line, col)).
        If compilation was successful, return (True, None), then run the code
        and then send (is_success, res_no, res_str, exception_string, rem_stdin).
        is_success - True if there was no exception.
        res_no - number of the result in the history count, or None if there
                 was no result or there's no history.
        res_str - a string representation of the result.
        exception_string - description of the exception, or None if is_success.
        rem_stdin - data that was sent into stdin and wasn't consumed.
        """
        # pause_idle was called before execute, disable it.
        self.idle_paused = False
        
        if ast:
            success, r = self.compile_ast(source)
        else:
            success, r = self.compile_no_ast(source)
        if not success:
            yield False, r
            return
        else:
            yield True, None
        codeobs = r
            
        self.last_res = None
        try:
            unmask_sigint()
            try:
                # Execute
                for codeob in codeobs:
                    exec codeob in self.locs
                # Work around http://bugs.python.org/issue8213 - stdout buffered
                # in Python 3.
                if not sys.stdout.closed:
                    sys.stdout.flush()
                if not sys.stderr.closed:
                    sys.stderr.flush()
                # Convert the result to a string. This is here because exceptions
                # may be raised here.
                if self.last_res is not None:
                    if self.is_pprint:
                        res_str = self.safe_pformat(self.last_res)
                    else:
                        res_str = unicode(repr(self.last_res))
                    if len(res_str) > MAX_RES_STR_LEN:
                        res_str = (res_str[:MAX_RES_STR_LEN]
                                   +'\n[%d chars truncated]' % (
                                        len(res_str)-MAX_RES_STR_LEN))
                else:
                    res_str = None
            finally:
                mask_sigint()
        except:
            if not sys.stdout.closed:
                sys.stdout.flush()
            excinfo = sys.exc_info()
            sys.last_type, sys.last_value, sys.last_traceback = excinfo
            exception_string = trunc_traceback(excinfo, __file__)
            is_success = False
            res_no = None
            res_str = None
        else:
            is_success = True
            exception_string = None
            if self.last_res is not None:
                res_no = self.store_in_reshist(self.last_res)
            else:
                res_no = None
        # Discard the reference to the result
        self.last_res = None
            
        # Send back any data left on stdin.
        rem_stdin = []
        if sys.platform == 'linux2':
            while select([sys.stdin], [], [], 0)[0]:
                r = os.read(sys.stdin.fileno(), 8192)
                if not r:
                    # File may be in error state
                    break
                rem_stdin.append(unicodify(r))
        elif sys.platform == 'win32':
            fd = sys.stdin.fileno()
            handle = get_osfhandle(fd)
            avail = c_ulong(0)
            PeekNamedPipe(handle, None, 0, None, byref(avail), None)
            nAvail = avail.value
            if nAvail > 0:
                rem_stdin.append(os.read(fd, nAvail))
        else:
            # I don't know how to do this in Jython.
            pass

        rem_stdin = u''.join(rem_stdin)
        
        # Check if matplotlib in non-interactive mode was imported
        self.check_matplotlib_ia()

        yield is_success, res_no, res_str, exception_string, rem_stdin

    @rpc_func
    def pause_idle(self):
        """
        before 'execute' is called, 'pause_idle' is called to check if we don't
        do any idle jobs right now. It is followed by either 'execute' or
        'resume_idle'.
        """
        self.idle_paused = True
    
    @rpc_func
    def resume_idle(self):
        self.idle_paused = False
    
    @rpc_func
    def set_pprint(self, is_pprint):
        self.is_pprint = is_pprint
    
    @rpc_func
    def set_matplotlib_ia(self, is_switch, is_warn):
        self.is_matplotlib_ia_switch = is_switch
        self.is_matplotlib_ia_warn = is_warn

    @rpc_func
    def set_reshist_size(self, new_reshist_size):
        if new_reshist_size < self.reshist_size:
            for i in range(self.reshist_counter-self.reshist_size,
                           self.reshist_counter-new_reshist_size):
                self.locs.pop('_%d' % i, None)
        self.reshist_size = new_reshist_size
    
    @rpc_func
    def clear_reshist(self):
        for i in range(self.reshist_counter-self.reshist_size, self.reshist_counter):
            self.locs.pop('_%d' % i, None)

    def store_in_reshist(self, res):
        """
        Get a result value to store in the result history.
        Store it, and return the result's index.
        If the result isn't stored, return None.
        """
        if res is None:
            return None
            
        if '__' in self.locs:
            self.locs['___'] = self.locs['__']
        if '_' in self.locs:
            self.locs['__'] = self.locs['_']
        self.locs['_'] = res
        
        if self.reshist_size == 0:
            return None
        res_index = self.reshist_counter
        self.locs['_%d' % res_index] = res
        del_index = self.reshist_counter - self.reshist_size
        if del_index >= 0:
            self.locs.pop('_%d' % del_index, None)
        self.reshist_counter += 1
        return res_index
    
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
        """
        try:
            entity = eval(expr, self.locs)
            ids = dir(entity)
            ids = map(unicodify, ids)
            ids.sort()
            if (isinstance(entity, types.ModuleType)
                and hasattr(entity, '__all__')):
                all_set = set(entity.__all__)
            else:
                all_set = None
            public, private = self.split_list(ids, all_set)
        except Exception:
            public = private = []

        return public, private

    @rpc_func
    def complete_firstlevels(self):
        """
        Get (public, private) names (globals, builtins, keywords).
        """
        namespace = self.locs.copy()
        namespace.update(__builtin__.__dict__)
        ids = eval("dir()", namespace) + keyword.kwlist
        ids = map(unicodify, ids)
        ids.sort()
        if '__all__' in namespace:
            all_set = set(namespace['__all__'])
        else:
            all_set = None
        public, private = self.split_list(ids, all_set)
        
        return public, private
        
    @rpc_func
    def get_func_args(self, expr):
        """Return the argument names of the function (a list of strings)"""
        try:
            obj = eval(expr, self.locs)
        except Exception:
            return None
        try:
            if not py3k:
                args = inspect.getargspec(obj)[0]
            else:
                args = inspect.getfullargspec(obj).args #@UndefinedVariable
        except TypeError:
            return None
        # There may be nested args, so we filter them
        return [unicodify(s) for s in args
                if isinstance(s, basestring)]

    @staticmethod
    def dict_key_repr(x):
        """
        repr() used for dict keys.
        Replaced unicode strings like u'hello' with regular strings, if possible.
        """
        if py3k or type(x) != unicode:
            return repr(x)
        else:
            try:
                x.decode('ascii')
            except UnicodeDecodeError:
                return repr(x)
            else:
                return repr(str(x))
    
    @rpc_func
    def complete_dict_keys(self, expr):
        """
        Return the reprs of the dict's keys (a list of strings)
        Returns only those which have a simple-enough repr.
        """
        try:
            obj = eval(expr, self.locs)
        except Exception:
            return None
        if not isinstance(obj, dict) or len(obj) > 1000:
            return None
        return sorted(unicodify(self.dict_key_repr(x)) for x in obj if is_key_reprable(x))
        

    @rpc_func
    def find_modules(self, package):
        if package:
            package = package.split('.')
        else:
            package = []
        return [unicodify(s) for s in find_modules(package)]
    
    @rpc_func
    def get_module_members(self, mod_name):
        try:
            mod = sys.modules[mod_name]
        except KeyError:
            return None
        if hasattr(mod, '__all__'):
            all_set = set(mod.__all__)
        else:
            all_set = None
        ids = [unicodify(x) for x in mod.__dict__.iterkeys()]
        return self.split_list(ids, all_set)
    
    @rpc_func
    def complete_filenames(self, str_prefix, text, str_char, add_quote):
        is_raw = 'r' in str_prefix.lower()
        is_unicode = 'u' in str_prefix.lower()
        try:
            # We add a space because a backslash can't be the last
            # char of a raw string literal
            comp_what = eval(str_prefix
                             + text
                             + ' '
                             + str_char)[:-1]
        except SyntaxError:
            return
        if comp_what == '':
            comp_what = '.'
        if comp_what.startswith('//'):
            # This may be an XPath expression. Calling listdir on win32 will
            # interpret this as UNC and search the network, which may take
            # a long time or even stall. You can still use r'\\...' if you
            # want completion from UNC paths.
            return

        try:
            dirlist = os.listdir(comp_what)
        except OSError:
            return
        if case_insen_filenames:
            dirlist.sort(key=lambda s: s.lower())
        else:
            dirlist.sort()
        public = []
        private = []
        for name in dirlist:
            orig_name = name
            if not py3k:
                if is_unicode and isinstance(name, str):
                    # A filename which can't be unicode
                    continue
                if not is_unicode:
                    # We need a unicode string as the code. From what I see,
                    # Python evaluates unicode characters in byte strings as utf-8.
                    try:
                        name = name.decode('utf8')
                    except UnicodeDecodeError:
                        continue
            # skip troublesome names
            try:
                rename = eval(str_prefix + name + str_char)
            except (SyntaxError, UnicodeDecodeError):
                continue
            if rename != orig_name:
                continue

            is_dir = os.path.isdir(os.path.join(comp_what, orig_name))

            if not is_dir:
                if add_quote:
                    name += str_char
            else:
                if '/' in text or os.path.sep == '/':
                    # Prefer forward slash
                    name += '/'
                else:
                    if not is_raw:
                        name += '\\\\'
                    else:
                        name += '\\'

            if name.startswith('.'):
                private.append(name)
            else:
                public.append(name)
        
        return public, private, case_insen_filenames
    
    @staticmethod
    def get_welcome():
        if 'IronPython' in sys.version:
            first_line = sys.version[sys.version.find('(')+1:sys.version.rfind(')')]
        else:
            if sys.platform.startswith('java'):
                name = 'Jython'
            else:
                name = 'Python'
            first_line = u'%s %s on %s' % (name, sys.version, sys.platform)
        return (first_line+'\n'
                +u'Type "copyright", "credits" or "license()" for more information.\n')

    @rpc_func
    def get_subprocess_info(self):
        return (self.get_welcome(), can_mask_sigint())
        
    @classmethod
    def _find_constructor(cls, class_ob):
        # Given a class object, return a function object used for the
        # constructor (ie, __init__() ) or None if we can't find one.
        try:
            return class_ob.__init__.im_func
        except AttributeError:
            for base in class_ob.__bases__:
                rc = cls._find_constructor(base)
                if rc is not None: return rc
        return None

    @rpc_func
    def get_func_doc(self, expr):
        """Get a string describing the arguments for the given object"""
        try:
            obj = eval(expr, self.locs)
        except Exception:
            return None
        if isinstance(obj, (types.BuiltinFunctionType,
                            types.BuiltinMethodType)):
            # These don't have source code, and using pydoc will only
            # add something like "execfile(...)" before the doc.
            doc = inspect.getdoc(obj)
            if doc is None:
                return None
            return unicodify(doc)
        
        # for decorated functions: try to get the original function from
        # func.__module__ and func.__name__
        try:
            modname = obj.__module__
        except AttributeError:
            pass
        else:
            try:
                mod = sys.modules[modname]
            except KeyError:
                pass
            else:
                try:
                    obj = getattr(mod, obj.__name__)
                except AttributeError:
                    pass
        
        # Check if obj.__doc__ is not in the code (was added after definition).
        # If so, return pydoc's documentation.
        # This test is CPython-specific. Another approach would be to look for
        # the string in the source code.
        co_consts = getattr(getattr(obj, 'func_code', None), 'co_consts', None)
        __doc__ = getattr(obj, '__doc__', None)
        if co_consts is not None and __doc__ is not None:
            if __doc__ not in co_consts:
                # Return pydoc's documentation
                return unicodify(textdoc.document(obj).strip())
        
        try:
            source = inspect.getsource(obj)
        except (TypeError, IOError):
            # If can't get the source, return pydoc's documentation
            return unicodify(textdoc.document(obj).strip())
        else:
            # If we can get the source, return it.
            
            # cleandoc removes extra indentation.
            # We add a newline because it ignores indentation of first line...
            # The next line is for Python 2.5 compatibility.
            cleandoc = getattr(inspect, 'cleandoc', lambda s: s)
            return unicodify(cleandoc('\n'+source))
    
    @rpc_func
    def is_callable_only(self, what):
        """
        Checks whether an object is callable, and doesn't expect operators
        (so there's no point in typing space after its name, unless to add
        parens).
        Also checks whether obj.__expects_str__ is True, which means that
        the expected argument is a string so quotes will be added.
        Returns (is_callable_only, expects_str)
        """
        try:
            obj = eval(what, self.locs)
        except Exception:
            return False, False
        typ = type(obj)
        
        expects_str = bool(getattr(obj, '__expects_str__', False))
        
        # Check cache
        try:
            return is_callable_cache[id(typ)], expects_str
        except KeyError:
            pass
        
        r = (callable(obj)
             and not any(hasattr(obj, att) for att in operator_methods))
        
        is_callable_cache[id(typ)] = r
        return r, expects_str
    
    def check_matplotlib_ia(self):
        """Check if matplotlib is in non-interactive mode, and handle it."""
        if not self.is_matplotlib_ia_warn and not self.is_matplotlib_ia_switch:
            return
        if self.matplotlib_ia_handled:
            return
        if 'matplotlib' not in sys.modules:
            return
        self.matplotlib_ia_handled = True
        # From here we do this only once.
        matplotlib = sys.modules['matplotlib']
        if not hasattr(matplotlib, 'is_interactive'):
            return
        if matplotlib.is_interactive():
            return
        if self.is_matplotlib_ia_switch:
            if not hasattr(matplotlib, 'interactive'):
                return
            matplotlib.interactive(True)
        else:
            sys.stderr.write(
                "Warning: matplotlib in non-interactive mode detected.\n"
                "This means that plots will appear only after you run show().\n"
                "Use Edit->Preferences->Shell to automatically switch to interactive mode \n"
                "or to suppress this warning.\n")


# Handle GUI events

class GuiHandler(object):
    def handle_events(self, delay):
        """
        This method gets the time in which to process GUI events, in seconds.
        If the GUI toolkit is loaded, run it for the specified delay and return
        True.
        If it isn't loaded, return False immediately.
        """
        raise NotImplementedError("Abstract method")

@contextmanager
def user_code():
    """
    Run user code, unmasking SIGINT, and catching exceptions.
    """
    try:
        unmask_sigint()
        yield
    except:
        sys.excepthook(*sys.exc_info())
    finally:
        mask_sigint()


class GtkHandler(GuiHandler):
    def __init__(self):
        self.gtk = None
        self.timeout_add = None

    def handle_events(self, delay):
        if self.gtk is None:
            if 'gtk' in sys.modules:
                self.gtk = sys.modules['gtk']
                try:
                    from glib import timeout_add
                except ImportError:
                    from gobject import timeout_add
                self.timeout_add = timeout_add
            else:
                return False
        self.timeout_add(int(delay * 1000), self.gtk_main_quit)
        with user_code():
            self.gtk.main()
            
        return True

    def gtk_main_quit(self):
        self.gtk.main_quit()
        # Don't call me again
        return False

class GIHandler(GuiHandler):
    def __init__(self):
        self.gobject = None
        self.timeout_add = None

    def handle_events(self, delay):
        if self.gobject is None:
            if  'gi.repository.GObject' in sys.modules:
                self.gobject = sys.modules[ 'gi.repository.GObject']
                from gi.repository.GLib import timeout_add
                self.timeout_add = timeout_add
            else:
                return False
        mainloop = self.gobject.MainLoop()
        self.timeout_add(int(delay * 1000), mainloop.quit)
        with user_code():
            mainloop.run()
            
        return True

    def gtk_main_quit(self):
        self.gtk.main_quit()
        # Don't call me again
        return False

class Qt4Handler(GuiHandler):
    def __init__(self):
        self.QtCore = None

    def handle_events(self, delay):
        if self.QtCore is None:
            if 'PyQt4' in sys.modules:
                self.QtCore = sys.modules['PyQt4'].QtCore
            elif 'PyQt5' in sys.modules:
                self.QtCore = sys.modules['PyQt5'].QtCore
            elif 'PySide' in sys.modules:
                self.QtCore = sys.modules['PySide'].QtCore
            else:
                return False
        QtCore = self.QtCore

        app = QtCore.QCoreApplication.instance()
        if app is None:
            return False

        # We create a new QCoreApplication to avoid quitting if modal dialogs
        # are active. This approach was taken from IPython. See:
        # https://github.com/ipython/ipython/blob/master/IPython/lib/inputhookqt4.py
        app.processEvents(QtCore.QEventLoop.AllEvents, delay*1000)
        timer = QtCore.QTimer()
        event_loop = QtCore.QEventLoop()
        timer.timeout.connect(event_loop.quit)
        timer.start(delay*1000)
        event_loop.exec_()
        timer.stop()        
        return True

class TkHandler(GuiHandler):
    def __init__(self):
        self.Tkinter = None

    def handle_events(self, delay):
        # TODO: It's pretty silly to handle all events and then just wait.
        # But I haven't found a better way - if you find one, tell me!
        if self.Tkinter is None:
            if 'Tkinter' in sys.modules:
                self.Tkinter = sys.modules['Tkinter']
            if 'tkinter' in sys.modules:
                self.Tkinter = sys.modules['tkinter']
            else:
                return False
        Tkinter = self.Tkinter

        # Handling Tk events is done only if there is an active tkapp object.
        # It is created by Tkinter.Tk.__init__, which sets
        # Tkinter._default_root to itself, when Tkinter._support_default_root
        # is True (the default). Here we check whether Tkinter._default_root
        # is something before we handle Tk events.
        if Tkinter._default_root:
            _tkinter = Tkinter._tkinter
            with user_code():
                if hasattr(_tkinter, 'dooneevent'):
                    while _tkinter.dooneevent(_tkinter.DONT_WAIT):
                        pass
                else:
                    while Tkinter._default_root.tk.dooneevent(_tkinter.DONT_WAIT):
                        pass
        time.sleep(delay)
        return True

def main(port):
    _subp = Subprocess(port)
