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

import sys
import os
from os import path
import time
import tempfile
from optparse import OptionParser
import subprocess
import webbrowser
import re
from keyword import iskeyword

import logging
from logging import debug
#logging.basicConfig(format="dreampie: %(message)s", level=logging.DEBUG)

def find_data_dir():
    """
    Find the 'share' directory in which to find files.
    If we are inside the source directory, build subp zips.
    """
    # Scenarios:
    # * Running from the source directory. 'share' is near 'dreampielib'
    # * Running from a distutils installed executable. The scheme is:
    #   prefix/bin/executable
    #   prefix/share/
    # * Running from py2exe. 'share' is near the executable.
    # * Running from /usr/bin/X11/dreampie on Debian. Just check '/usr/share'.
    #
    # So, if we find a 'share' near dreampielib, we build zips and return it.
    # Otherwise, we search for 'share' near the executable. If it doesn't
    # exist, we search for 'share' one level below the executable.
    from os.path import join, dirname, isdir, pardir, abspath

    local_data_dir = join(dirname(__file__), pardir, pardir, 'share')
    if isdir(join(local_data_dir, 'dreampie')):
        # We're in the source path. Build zips if needed, and return the right
        # dir.
        from ..subp_lib import build
        src_dir = join(dirname(__file__), pardir, pardir)
        build_dir = join(local_data_dir, 'dreampie')
        build(src_dir, build_dir)
        return abspath(local_data_dir)
    else:
        alternatives = [
            join(dirname(sys.argv[0]), 'share'), # py2exe
            join(dirname(sys.argv[0]), pardir, 'share'), # distutils
            '/usr/share', # debian
            ]
        for dir in alternatives:
            absdir = abspath(dir)
            if isdir(join(absdir, 'dreampie')):
                return absdir
        else:
            raise OSError("Could not find the 'share' directory")

data_dir = find_data_dir()
gladefile = path.join(data_dir, 'dreampie', 'dreampie.glade')

if sys.platform == 'win32':
    from .load_pygtk import load_pygtk
    load_pygtk(data_dir)

import pygtk
pygtk.require('2.0')
import gobject
import gtk
from gtk import gdk, glade
import pango
import gtksourceview2
from . import gtkexcepthook

try:
    from glib import timeout_add, idle_add
except ImportError:
    # In PyGObject 2.14, it's in gobject.
    from gobject import timeout_add, idle_add

from .. import __version__

from .SimpleGladeApp import SimpleGladeApp
from .keyhandler import (make_keyhandler_decorator, handle_keypress,
                         parse_keypress_event)
from .config import Config
from .config_dialog import ConfigDialog
from .write_command import write_command
from .newline_and_indent import newline_and_indent
from .output import Output
from .folding import Folding
from .selection import Selection
from .status_bar import StatusBar
from .vadj_to_bottom import VAdjToBottom
from .history import History
from .hist_persist import HistPersist
from .autocomplete import Autocomplete
from .call_tips import CallTips
from .autoparen import Autoparen
from .subprocess_handler import SubprocessHandler, StartError
from .beep import beep
from .file_dialogs import save_dialog
from .tags import (OUTPUT, STDIN, STDOUT, STDERR, EXCEPTION, PROMPT, COMMAND,
                   COMMAND_DEFS, COMMAND_SEP, MESSAGE, RESULT_IND, RESULT)
from . import tags

INDENT_WIDTH = 4

# Default line length, by which we set the default window size
LINE_LEN = 80

# Time to wait before autocompleting, to see if the user continues to type
AUTOCOMPLETE_WAIT = 400

# Maybe someday we'll want translations...
_ = lambda s: s

# A decorator for managing sourceview key handlers
sourceview_keyhandlers = {}
sourceview_keyhandler = make_keyhandler_decorator(sourceview_keyhandlers)

def get_widget(name):
    """Create a widget from the glade file."""
    xml = glade.XML(gladefile, name)
    return xml.get_widget(name)

class DreamPie(SimpleGladeApp):
    def __init__(self, pyexec):
        SimpleGladeApp.__init__(self, gladefile, 'window_main')
        self.load_popup_menus()
        self.set_mac_accelerators()
        
        self.config = Config()

        self.window_main.set_icon_from_file(
            path.join(data_dir, 'pixmaps', 'dreampie.png'))

        self.textbuffer = tb = self.textview.get_buffer()
        self.init_textbufferview()
        # Mark where the cursor was when the popup menu was popped
        self.popup_mark = tb.create_mark('popup-mark', tb.get_start_iter(),
                                         left_gravity=True)

        self.init_sourcebufferview()
        
        self.configure()

        self.output = Output(self.textview)
        
        self.folding = Folding(self.textbuffer, LINE_LEN)

        self.selection = Selection(self.textview, self.sourceview,
                                   self.on_is_something_selected_changed)

        self.status_bar = StatusBar(self.sourcebuffer, self.statusbar)

        self.vadj_to_bottom = VAdjToBottom(self.scrolledwindow_textview
                                           .get_vadjustment())

        self.history = History(self.textview, self.sourceview, self.config)

        self.recent_manager = gtk.recent_manager_get_default()
        self.menuitem_recent = [self.menuitem_recent0, self.menuitem_recent1,
                                self.menuitem_recent2, self.menuitem_recent3]
        self.recent_filenames = [None] * len(self.menuitem_recent)
        self.recent_manager.connect('changed', self.on_recent_manager_changed)

        self.histpersist = HistPersist(self.window_main, self.textview,
                                       self.status_bar, self.recent_manager)
        
        self.autocomplete = Autocomplete(self.sourceview,
                                         self.complete_attributes,
                                         self.complete_firstlevels,
                                         self.get_func_args,
                                         self.find_modules,
                                         self.get_module_members,
                                         self.complete_filenames,
                                         INDENT_WIDTH)
        
        # Hack: we connect this signal here, so that it will have lower
        # priority than the key-press event of autocomplete, when active.
        self.sourceview.connect('key-press-event', self.on_sourceview_keypress)

        self.call_tips = CallTips(self.sourceview, self.get_func_doc,
                                  INDENT_WIDTH)
        
        self.autoparen = Autoparen(self.sourcebuffer,
                                   self.is_callable_only,
                                   self.get_expects_str,
                                   self.autoparen_show_call_tip,
                                   INDENT_WIDTH)

        self.subp = SubprocessHandler(
            pyexec, data_dir,
            self.on_stdout_recv, self.on_stderr_recv, self.on_object_recv,
            self.on_subp_terminated)
        try:
            self.subp.start()
        except StartError, e:
            msg = gtk.MessageDialog(
                None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,
                _("Couldn't start subprocess: %s") % e)
            _response = msg.run()
            msg.destroy()
            print >> sys.stderr, e
            sys.exit(1)

        # Is the subprocess executing a command
        self.is_executing = False
        
        # Are we trying to shut down
        self.is_terminating = False

        self.set_window_default_size()
        self.window_main.show_all()
        self.set_is_executing(False)
        self.update_recent()
        
        self.show_welcome()
        self.configure_subp()
        self.run_init_code()

        if self.config.get_bool('show-getting-started'):
            self.show_getting_started_dialog()
            self.config.set_bool('show-getting-started', False)
            self.config.save()
        
    def load_popup_menus(self):
        # Load popup menus from the glade file. Would not have been needed if
        # popup menus could be children of windows.
        xml = glade.XML(gladefile, 'popup_sel_menu')
        xml.signal_autoconnect(self)
        self.popup_sel_menu = xml.get_widget('popup_sel_menu')
        
        xml = glade.XML(gladefile, 'popup_nosel_menu')
        xml.signal_autoconnect(self)
        self.popup_nosel_menu = xml.get_widget('popup_nosel_menu')
        self.fold_unfold_section_menu = xml.get_widget('fold_unfold_section_menu')
        self.copy_section_menu = xml.get_widget('copy_section_menu')
        self.view_section_menu = xml.get_widget('view_section_menu')
        self.save_section_menu = xml.get_widget('save_section_menu')
    
    def set_mac_accelerators(self):
        # Set up accelerators suitable for the Mac.
        # Ctrl-Up and Ctrl-Down are taken by the window manager, so we use
        # Ctrl-PgUp and Ctrl-PgDn.
        # We want it to be easy to switch, so both sets of keys are always
        # active, but only one, most suitable for each platform, is displayed
        # in the menu.
        
        accel_group = gtk.accel_groups_from_object(self.window_main)[0]
        menu_up = self.menuitem_history_up
        UP = gdk.keyval_from_name('Up')
        PGUP = gdk.keyval_from_name('Prior')
        menu_dn = self.menuitem_history_down
        DN = gdk.keyval_from_name('Down')
        PGDN = gdk.keyval_from_name('Next')

        if sys.platform != 'darwin':
            menu_up.add_accelerator('activate', accel_group, PGUP,
                                    gdk.CONTROL_MASK, 0)
            menu_dn.add_accelerator('activate', accel_group, PGDN,
                                    gdk.CONTROL_MASK, 0)
        else:
            menu_up.remove_accelerator(accel_group, UP, gdk.CONTROL_MASK)
            menu_up.add_accelerator('activate', accel_group, PGUP,
                                    gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
            menu_up.add_accelerator('activate', accel_group, UP,
                                    gdk.CONTROL_MASK, 0)
    
            menu_dn.remove_accelerator(accel_group, DN, gdk.CONTROL_MASK)
            menu_dn.add_accelerator('activate', accel_group, PGDN,
                                    gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
            menu_dn.add_accelerator('activate', accel_group, DN,
                                    gdk.CONTROL_MASK, 0)

    def on_cut(self, _widget):
        return self.selection.cut()

    def on_copy(self, _widget):
        return self.selection.copy()

    def on_copy_commands_only(self, _widget):
        return self.selection.copy_commands_only()

    def on_paste(self, _widget):
        return self.selection.paste()

    def on_is_something_selected_changed(self, is_something_selected):
        self.menuitem_cut.props.sensitive = is_something_selected
        self.menuitem_copy.props.sensitive = is_something_selected
        self.menuitem_copy_commands_only.props.sensitive = is_something_selected
        self.menuitem_interrupt.props.sensitive = not is_something_selected

    # Source buffer, Text buffer

    def init_textbufferview(self):
        tv = self.textview
        tb = self.textbuffer

        tv.set_wrap_mode(gtk.WRAP_CHAR)

        tags.add_tags(tb)

        tv.connect('key-press-event', self.on_textview_keypress)
        tv.connect('focus-in-event', self.on_textview_focus_in)

    def set_window_default_size(self):
        tv = self.textview
        context = tv.get_pango_context()
        metrics = context.get_metrics(tv.style.font_desc,
                                      context.get_language())
        # I don't know why I have to add 2, but it works.
        width = pango.PIXELS(metrics.get_approximate_digit_width()*(LINE_LEN+2))
        height = pango.PIXELS(
            (metrics.get_ascent() + metrics.get_descent())*30)
        self.window_main.set_default_size(width, height)

    def init_sourcebufferview(self):
        self.sourcebuffer = sb = gtksourceview2.Buffer()
        self.sourceview = sv = gtksourceview2.View(self.sourcebuffer)

        lm = gtksourceview2.LanguageManager()
        python = lm.get_language('python')
        sb.set_language(python)
        self.scrolledwindow_sourceview.add(self.sourceview)
        sv.connect('focus-in-event', self.on_sourceview_focus_in)
        sv.grab_focus()

    def sb_get_text(self, *args):
        # Unfortunately, PyGTK returns utf-8 encoded byte strings...
        return self.sourcebuffer.get_text(*args).decode('utf8')

    def sv_scroll_cursor_onscreen(self):
        self.sourceview.scroll_mark_onscreen(self.sourcebuffer.get_insert())

    def on_textview_focus_in(self, _widget, _event):
        # Clear the selection of the sourcebuffer
        self.sourcebuffer.move_mark(self.sourcebuffer.get_selection_bound(),
                                    self.sourcebuffer.get_iter_at_mark(
                                        self.sourcebuffer.get_insert()))

    def on_sourceview_focus_in(self, _widget, _event):
        # Clear the selection of the textbuffer
        self.textbuffer.move_mark(self.textbuffer.get_selection_bound(),
                                  self.textbuffer.get_iter_at_mark(
                                        self.textbuffer.get_insert()))

    def write(self, data, *tag_names):
        self.textbuffer.insert_with_tags_by_name(
            self.textbuffer.get_end_iter(), data, *tag_names)

    def write_output(self, data, tag_names, onnewline=False, addbreaks=True):
        """
        Call self.output.write with the given arguments, and autofold if needed.
        """
        it = self.output.write(data, tag_names, onnewline, addbreaks)
        if self.config.get_bool('autofold'):
            self.folding.autofold(it, self.config.get_int('autofold-numlines'))
    
    def set_is_executing(self, is_executing):
        self.is_executing = is_executing
        label = _(u'Execute Code') if not is_executing else _(u'Write Input')
        self.menuitem_execute.child.props.label = label
        self.menuitem_discard_hist.props.sensitive = not is_executing

    @staticmethod
    def replace_gtk_quotes(source):
        # Work around GTK+ bug https://bugzilla.gnome.org/show_bug.cgi?id=610928
        # in order to fix bug #525469 - replace fancy quotes with regular
        # quotes.
        return source.replace(u'\xa8', '"').replace(u'\xb4', "'")
    
    def execute_source(self):
        """Execute the source in the source buffer.
        """
        sb = self.sourcebuffer
        source = self.sb_get_text(sb.get_start_iter(), sb.get_end_iter())
        source = source.rstrip()
        source = self.replace_gtk_quotes(source)
        is_ok, syntax_error_info = self.call_subp(u'execute', source)
        if not is_ok:
            if syntax_error_info:
                msg, lineno, offset = syntax_error_info
                status_msg = _("Syntax error: %s (at line %d col %d)") % (
                    msg, lineno+1, offset+1)
                # Work around a bug: offset may be wrong, which will cause
                # gtk to crash if using sb.get_iter_at_line_offset.
                iter = sb.get_iter_at_line(lineno)
                iter.forward_chars(offset+1)
                sb.place_cursor(iter)
            else:
                # Incomplete
                status_msg = _("Command is incomplete")
                sb.place_cursor(sb.get_end_iter())
            self.status_bar.set_status(status_msg)
            beep()
        else:
            write_command(self.write, source.strip())
            self.output.start_new_section()
            if not self.config.get_bool('leave-code'):
                sb.delete(sb.get_start_iter(), sb.get_end_iter())
            self.vadj_to_bottom.scroll_to_bottom()
            self.set_is_executing(True)

    def send_stdin(self):
        """Send the contents of the sourcebuffer as stdin."""
        sb = self.sourcebuffer
        s = self.sb_get_text(sb.get_start_iter(), sb.get_end_iter())
        if not s.endswith('\n'):
            s += '\n'

        self.write_output(s, [COMMAND, STDIN], addbreaks=False)
        self.write('\r', COMMAND_SEP)
        self.output.start_new_section()
        self.vadj_to_bottom.scroll_to_bottom()

        if not self.config.get_bool('leave-code'):
            sb.delete(sb.get_start_iter(), sb.get_end_iter())

        self.subp.write(s)

    @sourceview_keyhandler('Return', 0)
    def on_sourceview_return(self):
        sb = self.sourcebuffer

        # If we are on the first line, and it doesn't end with a ' ':
        #   * If we are not executing, try to execute (if failed, continue
        #     with normal behavior)
        #   * If we are executing, send the line as stdin.
        insert_iter = sb.get_iter_at_mark(sb.get_insert())
        if (insert_iter.equal(sb.get_end_iter())
            and insert_iter.get_line() == 0
            and insert_iter.get_offset() != 0
            and not self.sb_get_text(sb.get_start_iter(),
                                     insert_iter).endswith(' ')):

            if not self.is_executing:
                source = self.sb_get_text(sb.get_start_iter(),
                                          sb.get_end_iter())
                source = source.rstrip()
                source = self.replace_gtk_quotes(source)
                is_incomplete = self.call_subp(u'is_incomplete', source)
                if not is_incomplete:
                    self.execute_source()
                    return True
            else:
                # is_executing
                self.send_stdin()
                return True
                
        # If we are after too many newlines, the user probably just wanted to
        # execute - notify him.
        # We check if this line is empty and the previous one is.
        show_execution_tip = False
        if insert_iter.equal(sb.get_end_iter()):
            it = sb.get_end_iter()
            # This goes to the beginning of the line, and another line
            # backwards, so we get two lines
            it.backward_lines(1)
            text = self.sb_get_text(it, sb.get_end_iter())
            if not text.strip():
                show_execution_tip = True

        # We didn't execute, so newline-and-indent.
        r = newline_and_indent(self.sourceview, INDENT_WIDTH)

        if show_execution_tip:
            self.status_bar.set_status(_(
                "Tip: To execute your code, use Ctrl+Enter."))
        return r

    @sourceview_keyhandler('Tab', 0)
    def on_sourceview_tab(self):
        sb = self.sourcebuffer
        insert = sb.get_iter_at_mark(sb.get_insert())
        insert_linestart = sb.get_iter_at_line(insert.get_line())
        line = self.sb_get_text(insert_linestart, insert)

        if not line.strip():
            # We are at the beginning of a line, so indent - forward to next
            # "tab stop"
            sb.insert_at_cursor(' ' * (INDENT_WIDTH - len(line) % INDENT_WIDTH))

        else:
            # Completion should come here
            self.autocomplete.show_completions(is_auto=False, complete=True)

        self.sv_scroll_cursor_onscreen()
        return True

    @sourceview_keyhandler('ISO_Left_Tab', 0)
    def on_sourceview_shift_tab(self):
        self.textview.grab_focus()
        return True

    @sourceview_keyhandler('BackSpace', 0)
    def on_sourceview_backspace(self):
        sb = self.sourcebuffer
        insert = sb.get_iter_at_mark(sb.get_insert())
        insert_linestart = sb.get_iter_at_line(insert.get_line())
        line = self.sb_get_text(insert_linestart, insert)

        if line and not line.strip():
            # There are only space before us, so remove spaces up to last
            # "tab stop"
            delete_from = ((len(line) - 1) // INDENT_WIDTH) * INDENT_WIDTH
            it = sb.get_iter_at_line_offset(insert.get_line(), delete_from)
            sb.delete(it, insert)
            self.sv_scroll_cursor_onscreen()
            return True

        return False

    # The following 3 handlers are for characters which may trigger automatic
    # opening of the completion list. (slash and backslash depend on path.sep)
    # We leave the final decision whether to open the list to the autocompleter.
    # We just notify it that the char was inserted and the user waited a while.

    @sourceview_keyhandler('period', 0)
    def on_sourceview_period(self):
        timeout_add(AUTOCOMPLETE_WAIT, self.check_autocomplete, '.')
    @sourceview_keyhandler('slash', 0)
    def on_sourceview_slash(self):
        timeout_add(AUTOCOMPLETE_WAIT, self.check_autocomplete, '/')
    @sourceview_keyhandler('backslash', 0)
    def on_sourceview_backslash(self):
        timeout_add(AUTOCOMPLETE_WAIT, self.check_autocomplete, '\\')

    def check_autocomplete(self, last_char):
        """
        If the last char in the sourcebuffer is last_char, call
        show_completions.
        """
        sb = self.sourcebuffer
        if self.sourceview.is_focus():
            it = sb.get_iter_at_mark(sb.get_insert())
            it2 = it.copy()
            it2.backward_chars(1)
            char = sb.get_text(it2, it)
            if char == last_char:
                self.autocomplete.show_completions(is_auto=True, complete=False)
        # return False so as not to be called repeatedly.
        return False

    @sourceview_keyhandler('parenleft', 0)
    def on_sourceview_parenleft(self):
        idle_add(self.call_tips.show, True)

    def on_sourceview_keypress(self, _widget, event):
        return handle_keypress(self, event, sourceview_keyhandlers)


    # Autoparen
    
    @sourceview_keyhandler('space', 0)
    def on_sourceview_space(self):
        """
        If a space was hit after a callable-only object, add parentheses.
        """
        if self.is_executing:
            return False
        if not self.config.get_bool('autoparen'):
            return False
        
        return self.autoparen.add_parens()

    def is_callable_only(self, expr):
        # This should be called only as a result of on_sourceview_space, which
        # already checks that is_executing==False.
        return self.call_subp(u'is_callable_only', expr)
    
    def get_expects_str(self):
        return set(self.config.get('expects-str-2').split())
    
    def autoparen_show_call_tip(self):
        self.call_tips.show(is_auto=True)


    # History

    def on_textview_keypress(self, _widget, event):
        keyval_name, state = parse_keypress_event(event)
        if (keyval_name, state) == ('Return', 0):
            return self.history.copy_to_sourceview()

    def on_history_up(self, _widget):
        self.history.history_up()

    def on_history_down(self, _widget):
        self.history.history_down()

    # Subprocess

    def show_welcome(self):
        s = self.call_subp(u'get_welcome')
        s += 'DreamPie %s\n' % __version__
        self.write(s, MESSAGE)
        self.output.start_new_section()

    def configure_subp(self):
        config = self.config
        
        if config.get_bool('use-reshist'):
            reshist_size = config.get_int('reshist-size')
        else:
            reshist_size = 0
        self.call_subp(u'set_reshist_size', reshist_size)
        self.menuitem_clear_reshist.props.sensitive = (reshist_size > 0)
        
        self.call_subp(u'set_pprint', config.get_bool('pprint'))
        
        self.call_subp(u'set_matplotlib_ia',
                       config.get_bool('matplotlib-ia-switch'),
                       config.get_bool('matplotlib-ia-warn'))
        
    def run_init_code(self):
        """
        Runs the init code.
        This will result in the code being run and a '>>>' printed afterwards.
        If there's no init code, will just print '>>>'.
        """
        init_code = unicode(eval(self.config.get('init-code')))
        if init_code:
            is_ok, syntax_error_info = self.call_subp(u'execute', init_code)
            if not is_ok:
                msg, lineno, offset = syntax_error_info
                warning = _(
                    "Could not run initialization code because of a syntax "
                    "error:\n"
                    "%s at line %d col %d.") % (msg, lineno+1, offset+1)
                msg = gtk.MessageDialog(self.window_main, gtk.DIALOG_MODAL,
                                        gtk.MESSAGE_WARNING, gtk.BUTTONS_CLOSE,
                                        warning)
                _response = msg.run()
                msg.destroy()
            else:
                self.set_is_executing(True)
        if not self.is_executing:
            self.write('>>> ', COMMAND, PROMPT)

    def on_subp_terminated(self):
        if self.is_terminating:
            return
        # This may raise an exception if subprocess couldn't be started,
        # but hopefully if it was started once it will be started again.
        self.subp.start()
        self.set_is_executing(False)
        self.write('\n')
        self.write(
            '==================== New Session ====================\n',
            MESSAGE)
        self.output.start_new_section()
        self.configure_subp()
        self.run_init_code()

    def on_restart_subprocess(self, _widget):
        self.subp.kill()

    def on_stdout_recv(self, data):
        self.write_output(data, STDOUT)

    def on_stderr_recv(self, data):
        self.write_output(data, STDERR)

    def call_subp(self, funcname, *args):
        self.subp.send_object((funcname, args))
        return self.subp.recv_object()

    def on_object_recv(self, obj):
        assert self.is_executing

        is_success, val_no, val_str, exception_string, rem_stdin = obj

        if not is_success:
            self.write_output(exception_string, EXCEPTION, onnewline=True)
        else:
            if val_str is not None:
                if val_no is not None:
                    self.write_output('%d: ' % val_no, RESULT_IND,
                                      onnewline=True)
                self.write_output(val_str+'\n', RESULT)
        self.write('>>> ', COMMAND, PROMPT)
        self.set_is_executing(False)
        self.handle_rem_stdin(rem_stdin)

    def handle_rem_stdin(self, rem_stdin):
        """
        Add the stdin text that was not processed to the source buffer.
        Remove it from the text buffer (we check that the STDIN text is
        consistent with rem_stdin - otherwise we give up)
        """
        if not rem_stdin:
            return

        self.sourcebuffer.insert(self.sourcebuffer.get_start_iter(), rem_stdin)
        self.sv_scroll_cursor_onscreen()

        tb = self.textbuffer
        stdin = tb.get_tag_table().lookup(STDIN)
        it = tb.get_end_iter()
        if not it.ends_tag(stdin):
            it.backward_to_tag_toggle(stdin)
        while True:
            it2 = it.copy()
            it2.backward_to_tag_toggle(stdin)
            cur_stdin = tb.get_slice(it2, it, True)
            min_len = min(len(cur_stdin), len(rem_stdin))
            assert min_len > 0
            if cur_stdin[-min_len:] != rem_stdin[-min_len:]:
                debug("rem_stdin doesn't match what's in textview")
                break
            it2.forward_chars(len(cur_stdin)-min_len)
            tb.delete(it2, it)
            rem_stdin = rem_stdin[:-min_len]
            if not rem_stdin:
                break
            else:
                it = it2
                # if rem_stdin is left, it2 must be at the beginning of the
                # stdin region.
                it2.backward_to_tag_toggle(stdin)
                assert it2.ends_tag(stdin)

    def on_execute_command(self, _widget):
        if self.is_executing:
            self.send_stdin()
        elif self.sourcebuffer.get_char_count() == 0:
            beep()
        else:
            self.execute_source()
        return True

    def on_interrupt(self, _widget):
        if self.is_executing:
            self.subp.interrupt()
        else:
            self.status_bar.set_status(
                _("A command isn't being executed currently"))
            beep()

    # History persistence
    
    def on_save_history(self, _widget):
        self.histpersist.save()
    
    def on_save_history_as(self, _widget):
        self.histpersist.save_as()
    
    def on_load_history(self, _widget):
        self.histpersist.load()
    
    # Recent history files
    
    def on_recent_manager_changed(self, _recent_manager):
        self.update_recent()
    
    def update_recent(self):
        """Update the menu and self.recent_filenames"""
        rman = self.recent_manager
        recent_items = [it for it in rman.get_items()
                        if it.has_application('dreampie')
                        and it.get_uri().startswith('file://')]
        recent_items.sort(key=lambda it: it.get_application_info('dreampie')[2],
                          reverse=True)
        self.menuitem_recentsep.props.visible = (len(recent_items) > 0)
        for i, menuitem in enumerate(self.menuitem_recent):
            if i < len(recent_items):
                it = recent_items[i]
                fn = it.get_uri()[len('file://'):]
                menuitem.props.visible = True
                menuitem.props.label = "_%d %s" % (i, fn)
                self.recent_filenames[i] = fn
            else:
                menuitem.props.visible = False
                self.recent_filenames[i] = None
    
    def on_menuitem_recent(self, widget):
        num = self.menuitem_recent.index(widget)
        fn = self.recent_filenames[num]
        self.histpersist.load_filename(fn)
    
    # Discard history
    
    def discard_hist_before_tag(self, tag):
        """
        Discard history before the given tag. If tag == COMMAND, this discards
        all history, and if tag == MESSAGE, this discards previous sessions.
        """
        tb = self.textbuffer
        
        tag = tb.get_tag_table().lookup(tag)
        it = tb.get_end_iter()
        it.backward_to_tag_toggle(tag)
        if not it.begins_tag(tag):
            it.backward_to_tag_toggle(tag)
        tb.delete(tb.get_start_iter(), it)

    def on_discard_history(self, _widget):
        xml = glade.XML(gladefile, 'discard_hist_dialog')
        d = xml.get_widget('discard_hist_dialog')
        d.set_transient_for(self.window_main)
        d.set_default_response(gtk.RESPONSE_OK)

        previous_rad = xml.get_widget('previous_rad')
        all_rad = xml.get_widget('all_rad')
        previous_rad.set_group(all_rad)
        previous_rad.props.active = True
        
        r = d.run()
        d.destroy()
        
        if r == gtk.RESPONSE_OK:
            tb = self.textbuffer
            if previous_rad.props.active:
                self.discard_hist_before_tag(MESSAGE)
            else:
                self.discard_hist_before_tag(COMMAND)
                tb.insert_with_tags_by_name(
                    tb.get_start_iter(),
                    '================= History Discarded =================\n',
                    MESSAGE)
            self.status_bar.set_status(_('History discarded.'))

    # Folding
    
    def on_section_menu_activate(self, widget):
        """
        Called when the used clicked a section-related item in a popup menu.
        """
        tb = self.textbuffer
        it = tb.get_iter_at_mark(self.popup_mark)
        r = self.folding.get_section_status(it)
        if r is None:
            # May happen if something was changed in the textbuffer between
            # popup and activation
            return
        typ, is_folded, start_it = r
        
        if widget is self.fold_unfold_section_menu:
            # Fold/Unfold
            if is_folded is None:
                # No point in folding.
                beep()
            elif not is_folded:
                self.folding.fold(typ, start_it)
            else:
                self.folding.unfold(typ, start_it)
        else:
            if typ == COMMAND:
                text = self.history.iter_get_command(start_it)
            else:
                end_it = start_it.copy()
                end_it.forward_to_tag_toggle(self.folding.get_tag(typ))
                text = tb.get_text(start_it, end_it).decode('utf8')
            if sys.platform == 'win32':
                text = text.replace('\n', '\r\n')
            if widget is self.copy_section_menu:
                # Copy
                self.selection.clipboard.set_text(text)
            elif widget is self.view_section_menu:
                # View
                fd, fn = tempfile.mkstemp()
                os.write(fd, text)
                os.close(fd)
                viewer = eval(self.config.get('viewer'))
                self.spawn_and_forget('%s %s' % (viewer, fn))
            elif widget is self.save_section_menu:
                # Save
                def func(filename):
                    f = open(filename, 'wb')
                    f.write(text)
                    f.close()
                save_dialog(func, _("Choose where to save the section"),
                            self.main_widget, _("All Files"), "*", None)
            else:
                assert False, "Unexpected widget"
            
    def spawn_and_forget(self, argv):
        """
        Start a process and forget about it.
        """
        if sys.platform == 'linux2':
            # We use a trick so as not to create zombie processes: we fork,
            # and let the fork spawn the process (actually another fork). The
            # (first) fork immediately exists, so the process we spawned is
            # made the child of process number 1.
            pid = os.fork()
            if pid == 0:
                _p = subprocess.Popen(argv, shell=True)
                os._exit(0)
            else:
                os.waitpid(pid, 0)
        else:
            _p = subprocess.Popen(argv, shell=True)
    
    def on_double_click(self, event):
        """If we are on a folded section, unfold it and return True, to
        avoid event propagation."""
        tv = self.textview

        if tv.get_window(gtk.TEXT_WINDOW_TEXT) is not event.window:
            # Probably a click on the border or something
            return
        x, y = tv.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
                                          int(event.x), int(event.y))
        it = tv.get_iter_at_location(x, y)
        r = self.folding.get_section_status(it)
        if r is not None:
            typ, is_folded, start_it = r
            if is_folded:
                self.folding.unfold(typ, start_it)
                return True
    
    def on_fold_last(self, _widget):
        self.folding.fold_last()
    
    def on_unfold_last(self, _widget):
        self.folding.unfold_last()

    # Other events

    def on_show_completions(self, _widget):
        self.autocomplete.show_completions(is_auto=False, complete=False)

    def complete_attributes(self, expr):
        if self.is_executing:
            return None
        return self.call_subp(u'complete_attributes', expr)

    def complete_firstlevels(self):
        if self.is_executing:
            return None
        return self.call_subp(u'complete_firstlevels')
    
    def get_func_args(self, expr):
        if self.is_executing:
            return None
        return self.call_subp(u'get_func_args', expr)
    
    def find_modules(self, expr):
        if self.is_executing:
            return None
        return self.call_subp(u'find_modules', expr)
    
    def get_module_members(self, expr):
        if self.is_executing:
            return None
        return self.call_subp(u'get_module_members', expr)
    
    def complete_filenames(self, str_prefix, text, str_char, add_quote):
        if self.is_executing:
            return None
        return self.call_subp(u'complete_filenames', str_prefix, text, str_char,
                              add_quote)

    def on_show_calltip(self, _widget):
        self.call_tips.show(is_auto=False)

    def get_func_doc(self, expr):
        if self.is_executing:
            return None
        return self.call_subp(u'get_func_doc', expr)

    def configure(self):
        """
        Apply configuration. Called on initialization and after configuration
        was changed by the configuration dialog.
        """
        config = self.config
        tv = self.textview; tb = self.textbuffer
        sv = self.sourceview; sb = self.sourcebuffer
        
        font_name = config.get('font')
        font = pango.FontDescription(font_name)
        tv.modify_font(font)
        sv.modify_font(font)

        cur_theme = self.config.get('current-theme')
        tags.apply_theme_text(tv, tb, tags.get_theme(self.config, cur_theme))
        tags.apply_theme_source(sb, tags.get_theme(self.config, cur_theme))

        self.set_window_default_size()
        
        command_defs = self.textbuffer.get_tag_table().lookup(COMMAND_DEFS)
        command_defs.props.invisible = config.get_bool('hide-defs')

    def on_preferences(self, _widget):
        cd = ConfigDialog(self.config, gladefile, self.window_main)
        r = cd.run()
        if r == gtk.RESPONSE_OK:
            self.configure()
            self.configure_subp()
        cd.destroy()

    def on_clear_reshist(self, _widget):
        self.call_subp(u'clear_reshist')
        self.status_bar.set_status(_("Result history cleared."))

    def on_close(self, _widget, _event):
        self.quit()
        return True

    def on_quit(self, _widget):
        self.quit()

    def quit(self):
        if (self.textbuffer.get_modified()
            and self.config.get_bool('ask-on-quit')):
            xml = glade.XML(gladefile, 'quit_dialog')
            d = xml.get_widget('quit_dialog')
            dontask_check = xml.get_widget('dontask_check')
            d.set_transient_for(self.window_main)
            d.set_default_response(1)
            quit = (d.run() == 1)
            if quit and dontask_check.props.active:
                self.config.set_bool('ask-on-quit', False)
                self.config.save()
            d.destroy()
        else:
            quit = True
        if quit:
            self.is_terminating = True
            self.window_main.destroy()
            self.subp.kill()
            gtk.main_quit()

    def on_about(self, _widget):
        d = get_widget('about_dialog')
        d.set_transient_for(self.window_main)
        d.set_version(__version__)
        d.set_logo(gdk.pixbuf_new_from_file(
            path.join(data_dir, 'pixmaps', 'dreampie.png')))
        d.run()
        d.destroy()
    
    def on_report_bug(self, _widget):
        webbrowser.open('https://bugs.launchpad.net/dreampie/+filebug')
    
    def on_homepage(self, _widget):
        webbrowser.open('http://dreampie.sourceforge.net/')
    
    def on_getting_started(self, _widget):
        self.show_getting_started_dialog()
    
    def show_getting_started_dialog(self):
        d = get_widget('getting_started_dialog')
        d.set_transient_for(self.window_main)
        d.run()
        d.destroy()
    
    def on_textview_button_press_event(self, _widget, event):
        if event.button == 3:
            self.show_popup_menu(event)
            return True
        
        if event.type == gdk._2BUTTON_PRESS:
            return self.on_double_click(event)
    
    def show_popup_menu(self, event):
        tv = self.textview
        tb = self.textbuffer
        
        if tb.get_has_selection():
            self.popup_sel_menu.popup(None, None, None, event.button,
                                      event.get_time())
        else:
            if tv.get_window(gtk.TEXT_WINDOW_TEXT) is not event.window:
                # Probably a click on the border or something
                return
            x, y = tv.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
                                              int(event.x), int(event.y))
            it = tv.get_iter_at_location(x, y)
            r = self.folding.get_section_status(it)
            if r is not None:
                typ, is_folded, _start_it = r
                if typ == OUTPUT:
                    typ_s = _('Output Section')
                else:
                    typ_s = _('Code Section')
                self.fold_unfold_section_menu.props.visible = (
                    is_folded is not None)
                self.fold_unfold_section_menu.child.props.label = (
                    _('Unfold %s') if is_folded else _('Fold %s')) % typ_s
                self.copy_section_menu.child.props.label = _('Copy %s') % typ_s
                self.view_section_menu.child.props.label = _('View %s') % typ_s
                self.save_section_menu.child.props.label = _('Save %s') % typ_s
                self.view_section_menu.props.visible = \
                    bool(eval(self.config.get('viewer')))
                
                tb.move_mark(self.popup_mark, it)
                self.popup_nosel_menu.popup(None, None, None, event.button,
                                            event.get_time())
            else:
                beep()

def main():
    usage = "%prog [options] [python-executable]"
    version = 'DreamPie %s' % __version__
    parser = OptionParser(usage=usage, version=version)
    if sys.platform == 'win32':
        parser.add_option("--hide-console-window", action="store_true",
                          dest="hide_console",
                          help="Hide the console window")

    opts, args = parser.parse_args()
    
    if len(args) > 1:
        parser.error("Can accept at most one argument")
    if len(args) == 1:
        pyexec = args[0]
    elif 'dreampie' in sys.executable.lower():
        # We are under py2exe.
        msg = gtk.MessageDialog(
            None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,
            _("DreamPie must be given the file name of a Python interpreter. "
              "Please create a shortcut to something like '%s "
              "--hide-console-window c:\\python26\\python.exe'.")
            % os.path.abspath(sys.argv[0]))
        _response = msg.run()
        msg.destroy()
        sys.exit(1)
    else:
        pyexec = sys.executable
        
    
    if sys.platform == 'win32' and opts.hide_console:
        from .hide_console_window import hide_console_window
        hide_console_window()

    gtk.widget_set_default_direction(gtk.TEXT_DIR_LTR)
    _dp = DreamPie(pyexec)
    gtk.main()
