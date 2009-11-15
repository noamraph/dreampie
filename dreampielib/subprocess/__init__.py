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
from repr import repr as safe_repr
try:
    # Executing multiple statements in 'single' mode (print results) is done
    # with the ast module. Python 2.5 doesn't have it, so we use the compiler
    # module, which also seems to work. Jython 2.5 does have the ast module,
    # which is fortunate, because the 'compiler module trick' doesn't work there.
    import ast
except ImportError:
    ast = None
    import compiler
import __future__

if sys.platform == 'win32':
    from msvcrt import get_osfhandle
    from ctypes import byref, c_ulong, windll
    PeekNamedPipe = windll.kernel32.PeekNamedPipe

from dreampielib.common.objectstream import send_object, recv_object

#import rpdb2; rpdb2.start_embedded_debugger('a')

import logging
from logging import debug
#logging.basicConfig(filename='/tmp/dreampie_subp_log', level=logging.DEBUG)

# time interval to process GUI events, in seconds
GUI_SLEEP = 0.1

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

class Subprocess(object):
    def __init__(self, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(('localhost', port))

        # Trick things like pdb into thinking that the namespace we create is
        # the main module
        mainmodule = types.ModuleType('__main__')
        sys.modules['__main__'] = mainmodule
        self.locs = mainmodule.__dict__

        self.gui_handlers = [GtkHandler(), Qt4Handler(), TkHandler()]

        self.gid = 0
        self.flags = PyCF_DONT_IMPLY_DEDENT

        # Run endless loop
        self.loop()

    def loop(self):
        while True:
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
                print >> sys.stderr, "Unknown command: %s" % funcname
                send_object(self.sock, None)

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
    def execute(self, source):
        """
        Get the source code to execute (a unicode string).
        Compile it. If there was a syntax error, return
        (False, (msg, line, col)).
        If compilation was successful, return (True, None), then run the code
        and then send (is_success, exception_string, rem_stdin).
        is_success - True if there was no exception.
        exception_string - description of the exception, or None if is_success.
        rem_stdin - data that was sent into stdin and wasn't consumed.
        """
        filename = '<pyshell#%d>' % self.gid
        self.gid += 1
        lines = source.split("\n")
        linecache.cache[filename] = len(source)+1, None, lines, filename
        try:
            if ast:
                a = compile(source, filename, 'exec', ast.PyCF_ONLY_AST)
                b = ast.Interactive(a.body)
                codeob = compile(b, filename, 'single')
            else:
                # We use compiler.compile instead of plain compile, because
                # compiler.compile does what you'd want when it gets multiple
                # statements, while plain compile complains about a syntax error.
                codeob = compiler.compile(source, filename, 'single')
        except SyntaxError, e:
            yield False, (unicode(e.msg), e.lineno-1, e.offset-1)
            return
        yield True, None
            
        for feature in _features:
            if codeob.co_flags & feature.compiler_flag:
                self.flags |= feature.compiler_flag

        is_success = True
        exception_string = None
        try:
            exec codeob in self.locs
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
            
        # Send back any data left on stdin.
        rem_stdin = []
        if sys.platform == 'linux2':
            while select([sys.stdin], [], [], 0)[0]:
                rem_stdin.append(os.read(sys.stdin.fileno(), 8192))
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
            namespace = self.locs.copy()
            namespace.update(__builtin__.__dict__)
            ids = eval("dir()", namespace) + keyword.kwlist
            ids = map(unicode, ids)
            ids.sort()
            if '__all__' in namespace:
                all_set = set(namespace['__all__'])
            else:
                all_set = None
            public, private = self.split_list(ids, all_set)
        else:
            try:
                entity = eval(expr, self.locs)
                ids = dir(entity)
                ids = map(unicode, ids)
                ids.sort()
                if hasattr(entity, '__all__'):
                    all_set = set(entity.__all__)
                else:
                    all_set = None
                public, private = self.split_list(ids, all_set)
            except Exception, e:
                public = private = []

        return public, private

    @rpc_func
    def complete_filenames(self, str_prefix, text, str_char):
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
            if rename != name:
                continue

            is_dir = os.path.isdir(os.path.join(comp_what, name))

            if not is_dir:
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
    
    @rpc_func
    def get_welcome(self):
        name = 'Python' if not sys.platform.startswith('java') else 'Jython'
        return (u'%s %s on %s\n' % (name, sys.version, sys.platform)
                +u'Type "copyright", "credits" or "license()" for more information.\n')

    @staticmethod
    def _find_constructor(class_ob):
        # Given a class object, return a function object used for the
        # constructor (ie, __init__() ) or None if we can't find one.
        try:
            return class_ob.__init__.im_func
        except AttributeError:
            for base in class_ob.__bases__:
                rc = _find_constructor(base)
                if rc is not None: return rc
        return None

    @rpc_func
    def get_arg_text(self, expr):
        """Get a string describing the arguments for the given object"""
        # This is based on Python's idlelib/CallTips.py, and the work of
        # Beni Cherniavsky.
        try:
            entity = eval(expr, self.locs)
        except Exception, e:
            return None
        arg_text = u""
        arg_offset = 0
        if type(entity) is types.ClassType:
            # Look for the highest __init__ in the class chain.
            fob = self._find_constructor(entity)
            if fob is None:
                fob = lambda: None
            else:
                arg_offset = 1
        elif type(entity) is types.MethodType:
            # bit of a hack for methods - turn it into a function
            # but we drop the "self" param.
            fob = entity.im_func
            arg_offset = 1
        else:
            fob = entity
        # Try and build one for Python defined functions
        if type(fob) in [types.FunctionType, types.LambdaType]:
            try:
                args, varargs, varkw, defaults = inspect.getargspec(fob)
                def formatvalue(obj):
                    return u"=" + safe_repr(obj)
                arg_text = unicode(inspect.formatargspec(
                    args[arg_offset:], varargs, varkw, defaults, formatvalue=formatvalue))
            except Exception:
                pass
        # See if we can use the docstring
        doc = unicode(inspect.getdoc(entity))
        if doc:
            doc = doc.lstrip()
            pos = doc.find("\n")
            if pos < 0 or pos > 70:
                pos = 70
            if arg_text:
                arg_text += "\n"
            arg_text += doc[:pos]
        return arg_text


# Handle GUI events

class GuiHandler(object):
    def handle_events(delay):
        """
        This method gets the time in which to process GUI events, in seconds.
        If the GUI toolkit is loaded, run it for the specified delay and return
        True.
        If it isn't loaded, return False immediately.
        """
        raise NotImplementedError("Abstract method")

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
        self.gtk.main()
        return True

    def gtk_main_quit(self):
        self.gtk.main_quit()
        # Don't call me again
        return False

class Qt4Handler(GuiHandler):
    def __init__(self):
        self.QtCore = None
        self.app = None

    def handle_events(self, delay):
        if self.QtCore is None:
            if 'PyQt4' in sys.modules:
                self.QtCore = sys.modules['PyQt4'].QtCore
            else:
                return False
        QtCore = self.QtCore

        if self.app is None:
            app = QtCore.QCoreApplication.instance()
            if app:
                self.app = app
            else:
                return False

        timer = QtCore.QTimer()
        QtCore.QObject.connect(timer, QtCore.SIGNAL('timeout()'),
                               self.qt4_quit_if_no_modal)
        timer.start(delay*1000)
        self.app.exec_()
        timer.stop()
        QtCore.QObject.disconnect(timer, QtCore.SIGNAL('timeout()'),
                                  self.qt4_quit_if_no_modal)
        return True

    def qt4_quit_if_no_modal(self):
        app = self.app
        if app.__class__.__name__ != 'QApplication' or \
           app.activeModalWidget() is None:
            app.quit()

class TkHandler(GuiHandler):
    def __init__(self):
        self.Tkinter = None

    def handle_events(self, delay):
        # TODO: It's pretty silly to handle all events and then just wait.
        # But I haven't found a better way - if you find one, tell me!
        if self.Tkinter is None:
            if 'Tkinter' in sys.modules:
                self.Tkinter = sys.modules['Tkinter']
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
            while _tkinter.dooneevent(_tkinter.DONT_WAIT):
                pass
        time.sleep(delay)
        return True

def main(port):
    subp = Subprocess(port)
