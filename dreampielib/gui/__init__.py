import sys
import os
import tempfile
from subprocess import Popen, PIPE
from select import select
import socket
import random

import pygtk
pygtk.require('2.0')
import gobject
import gtk
from gtk import gdk
import pango
import gtksourceview2

from .SimpleGladeApp import SimpleGladeApp
from ..common.objectstream import send_object, recv_object
from .write_command import write_command

# Tags and colors

STDOUT = 'stdout'; STDERR = 'stderr'; PROMPT = 'prompt'
COMMAND = 'command'; STDIN = 'stdin'

KEYWORD = 'keyword'; BUILTIN = 'builtin'; STRING = 'string'
NUMBER = 'number'; COMMENT = 'comment'

colors = {
    STDOUT: '#bcffff',
    STDERR: 'red',
    PROMPT: '#e400b6',
    COMMAND: 'white',
    STDIN: 'white',

    KEYWORD: '#ff7700',
    BUILTIN: '#efcfcf',
    STRING: '#00e400',
    NUMBER: '#aeacff',
    COMMENT: '#c9a3a0',
    }

def debug(s):
    print >> sys.stderr, s

# Maybe someday we'll want translations...
_ = lambda s: s

# A decorator for managing sourceview key handlers
# This decorates some methods of DreamPie.
sourceview_keyhandlers = {}
def sourceview_keyhandler(keyval, state):
    def decorator(func):
        sourceview_keyhandlers[keyval, state] = func
        return func
    return decorator

class DreamPie(SimpleGladeApp):
    def __init__(self, executable):
        self.executable = executable
        
        gladefile = os.path.join(os.path.dirname(__file__),
                                 'dreampie.glade')
        SimpleGladeApp.__init__(self, gladefile)

        self.window_main.set_icon_from_file(
            os.path.join(os.path.dirname(__file__), 'dreampie.svg'))

        self.textbuffer = self.textview.get_buffer()
        self.vadj = self.scrolledwindow_textview.get_vadjustment()
        self.init_textbufferview()

        self.sourcebuffer = gtksourceview2.Buffer()
        self.sourceview = gtksourceview2.View(self.sourcebuffer)
        self.init_sourcebufferview()

        # id of a message displayed in the status bar to be removed when
        # the contents of the source buffer is changed
        self.sourcebuffer_status_id = None
        self.sourcebuffer_changed_handler_id = None

        self.entry_input = gtk.Entry()
        self.entry_input.show()

        # These make sure that the textview vadjustment automatically
        # scrolls if it shows the bottom
        self.vadj.connect('changed', self.on_vadj_changed)
        self.vadj.connect('value-changed', self.on_vadj_value_changed)
        self.vadj_was_at_bottom = self.vadj_is_at_bottom()
        self.vadj_scroll_to_bottom()

        self.is_connected = False
        self.sock = self.popen = None

        # Is the subprocess executing a command
        self.is_executing = False
        self.start_subp()

        self.window_main.show_all()

    def init_textbufferview(self):
        self.textview.modify_base(0, gdk.color_parse('black'))
        self.textview.modify_text(0, gdk.color_parse('white'))
        self.textview.modify_font(
            pango.FontDescription('courier new,monospace'))

        # We have to add the tags in a specific order, so that the priority
        # of the syntax tags will be higher.
        for tag in (STDOUT, STDERR, PROMPT, COMMAND, STDIN,
                    KEYWORD, BUILTIN, STRING, NUMBER, COMMENT):
            self.textbuffer.create_tag(tag, foreground=colors[tag])

    def init_sourcebufferview(self):
        lm = gtksourceview2.LanguageManager()
        python = lm.get_language('python')
        self.sourcebuffer.set_language(python)
        self.sourcebuffer.set_style_scheme(
            make_style_scheme(default_style_scheme_spec))
        self.sourceview.modify_font(
            pango.FontDescription('courier new,monospace'))
        self.scrolledwindow_sourceview.add(self.sourceview)
        self.sourceview.connect('key-press-event', self.on_sourceview_keypress)

    def on_close(self, widget, event):
        gtk.main_quit()

    def set_sourcebuffer_status(self, message):
        """Set a message in the status bar to be removed when the contents
        of the source buffer is changed"""
        if self.sourcebuffer_status_id is not None:
            self.statusbar.remove(0, self.sourcebuffer_status_id)
            self.sourcebuffer.disconnect(self.sourcebuffer_changed_handler_id)
        self.sourcebuffer_status_id = self.statusbar.push(0, message)
        self.sourcebuffer_changed_handler_id = \
            self.sourcebuffer.connect('changed', self.clear_sourcebuffer_status)

    def clear_sourcebuffer_status(self, widget):
        self.statusbar.remove(0, self.sourcebuffer_status_id)
        self.sourcebuffer_status_id = None
        self.sourcebuffer.disconnect(self.sourcebuffer_changed_handler_id)
        self.sourcebuffer_changed_handler_id = None

    def vadj_is_at_bottom(self):
        return self.vadj.value == self.vadj.upper - self.vadj.page_size

    def vadj_scroll_to_bottom(self):
        self.vadj.set_value(self.vadj.upper - self.vadj.page_size)

    def on_vadj_changed(self, widget):
        if self.vadj_was_at_bottom and not self.vadj_is_at_bottom():
            self.vadj_scroll_to_bottom()
        self.vadj_was_at_bottom = self.vadj_is_at_bottom()

    def on_vadj_value_changed(self, widget):
        self.vadj_was_at_bottom = self.vadj_is_at_bottom()

    def write(self, data, *tag_names):
        self.textbuffer.insert_with_tags_by_name(
            self.textbuffer.get_end_iter(), data, *tag_names)

    def execute_source(self, warn):
        """Execute the source in the source buffer.
        Return True if successful (No syntax error).
        If warn is True, show the syntax error in the status bar.
        """
        sb = self.sourcebuffer
        tb = self.textbuffer
        source = sb.get_text(sb.get_start_iter(), sb.get_end_iter())
        send_object(self.sock, source)
        is_ok, syntax_error_info = recv_object(self.sock)
        if not is_ok:
            if warn:
                if syntax_error_info:
                    msg, lineno, offset = syntax_error_info
                    status_msg = _("Syntax error: %s (at line %d col %d)") % (
                        msg, lineno+1, offset+1)
                    iter = sb.get_iter_at_line_offset(lineno, offset)
                    sb.place_cursor(iter)
                else:
                    # Incomplete
                    status_msg = _("Command is incomplete")
                    sb.place_cursor(sb.get_end_iter())
                self.set_sourcebuffer_status(status_msg)
                gdk.beep()
        else:
            write_command(self.write, source.strip())
            sb.delete(sb.get_start_iter(), sb.get_end_iter())
            self.vadj_scroll_to_bottom()
            self.is_executing = True
        return is_ok

    @sourceview_keyhandler('Return', 0)
    def on_sourceview_return(self):
        if self.is_executing:
            return
        sb = self.sourcebuffer
        insert_iter = sb.get_iter_at_mark(sb.get_insert())
        if (insert_iter.get_line() == 0
            and insert_iter.ends_line()
            and sb.get_text(sb.get_start_iter(), insert_iter)[-1] != ' '):
            return self.execute_source(False)

    @sourceview_keyhandler('Return', gdk.CONTROL_MASK)
    def on_sourceview_ctrl_return(self):
        if self.is_executing:
            self.set_sourcebuffer_status(
                _('Another command is currently being executed.'))
            gdk.beep()
        else:
            self.execute_source(True)
        return True

    def on_sourceview_keypress(self, widget, event):
        keyval_name = gdk.keyval_name(event.keyval)
        try:
            func = sourceview_keyhandlers[keyval_name, event.state]
        except KeyError:
            pass
        else:
            return func(self)

##    def on_about(self, widget):
##        global is_entry
##        if not is_entry:
##            self.vpaned_main.remove(self.scrolledwindow_sourceview)
##            self.vpaned_main.add2(self.entry_input)
##            is_entry = True
##        else:
##            self.vpaned_main.remove(self.entry_input)
##            self.vpaned_main.add2(self.scrolledwindow_sourceview)
##            is_entry = False
##
    def start_subp(self):
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
        self.popen = popen = Popen([self.executable, 'subprocess', str(port)],
                                    stdin=PIPE, stdout=PIPE, stderr=PIPE,
                                    close_fds=True, env=env)
        debug("Waiting for an answer")
        s.listen(1)
        self.sock, addr = s.accept()
        debug("Connected to addr %r." % (addr,))
        s.close()

        self.write('>>> ', PROMPT)

        # I know that polling isn't the best way, but on Windows you have
        # no choice, and it allows us to do it all by ourselves, not use
        # gobject's functionality.
        gobject.timeout_add(10, self.manage_subp)

    def manage_subp(self):
        popen = self.popen

        # Check if exited
        rc = popen.poll()
        if rc is not None:
            print 'Process terminated with rc %r' % rc
            return False

        # Read from stdout, stderr, and socket
        ready, _, _ = select([popen.stdout, popen.stderr, self.sock], [], [], 0)

        if popen.stdout in ready:
            r = []
            while True:
                r.append(os.read(popen.stdout.fileno(), 8192))
                if not select([popen.stdout], [], [], 0)[0]:
                    break
            r = ''.join(r)
            self.on_stdout_recv(r)
                
        if popen.stderr in ready:
            r = []
            while True:
                r.append(os.read(popen.stderr.fileno(), 8192))
                if not select([popen.stderr], [], [], 0)[0]:
                    break
            r = ''.join(r)
            self.on_stderr_recv(r)
        
        if self.sock in ready:
            obj = recv_object(self.sock)
            self.on_object_recv(obj)

        return True

    def on_stdout_recv(self, data):
        self.write(data, STDOUT)

    def on_stderr_recv(self, data):
        self.write(data, STDERR)

    def on_object_recv(self, object):
        assert self.is_executing

        is_ok, exc_info = object
        if not is_ok:
            self.write('Exception: %s\n' % str(exc_info), STDERR)
            
        self.write('>>> ', PROMPT)
        self.is_executing = False

def make_style_scheme(spec):
    # Quite stupidly, there's no way to create a SourceStyleScheme without
    # reading a file from a search path. So this function creates a file in
    # a directory, to get you your style scheme.
    #
    # spec should be a dict of dicts, mapping style names to (attribute, value)
    # pairs. Color values will be converted using gdk.color_parse().
    # Boolean values will be handled correctly.
    dir = tempfile.mkdtemp()
    filename = os.path.join(dir, 'scheme.xml')
    f = open(filename, 'w')
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<style-scheme id="scheme" _name="Scheme" version="1.0">\n')
    for name, attributes in spec.iteritems():
        f.write('<style name="%s" ' % name)
        for attname, attvalue in attributes.iteritems():
            if attname in ('foreground', 'background'):
                attvalue = gdk.color_parse(attvalue).to_string()
            elif attname in ('italic', 'bold', 'underline', 'strikethrough'):
                attvalue = 'true' if attvalue else 'false'
            f.write('%s="%s" ' % (attname, attvalue))
        f.write('/>\n')
    f.write('</style-scheme>\n')
    f.close()

    ssm = gtksourceview2.StyleSchemeManager()
    ssm.set_search_path([dir])
    scheme = ssm.get_scheme('scheme')

    os.remove(filename)
    os.rmdir(dir)

    return scheme

default_style_scheme_spec = {
    'text': dict(background='black', foreground='white'),
    
    'def:keyword': dict(foreground=colors[KEYWORD]),
    'def:preprocessor': dict(foreground=colors[KEYWORD]),

    'def:builtin': dict(foreground=colors[BUILTIN]),
    'def:special-constant': dict(foreground=colors[BUILTIN]),
    'def:type': dict(foreground=colors[BUILTIN]),

    'def:string': dict(foreground=colors[STRING]),
    'def:number': dict(foreground=colors[NUMBER]),
    'def:comment': dict(foreground=colors[COMMENT]),

    'bracket-match': dict(foreground='white', background='darkblue'),
    }

        

def main(executable):
    gtk.widget_set_default_direction(gtk.TEXT_DIR_LTR)
    dp = DreamPie(executable)
    gtk.main()
