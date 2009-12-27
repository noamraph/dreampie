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
import os
from os import path
import time
import tempfile
from optparse import OptionParser

import logging
from logging import debug
#logging.basicConfig(format="dreampie: %(message)s", level=logging.DEBUG)

def find_data_dir():
    # If there's a "share" directory near the "dreampielib" directory, use it.
    # Otherwise, use sys.prefix
    from os.path import join, dirname, isdir, pardir, abspath
    
    local_data_dir = join(dirname(__file__), pardir, pardir, 'share')
    if isdir(local_data_dir):
        return abspath(local_data_dir)
    else:
        return abspath(join(sys.prefix, 'share'))

data_dir = find_data_dir()

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
from .keyhandler import make_keyhandler_decorator, handle_keypress
from .config import Config
from .config_dialog import ConfigDialog
from .write_command import write_command
from .newline_and_indent import newline_and_indent
from .output import Output
from .selection import Selection
from .status_bar import StatusBar
from .vadj_to_bottom import VAdjToBottom
from .history import History
from .hist_persist import HistPersist
from .autocomplete import Autocomplete
from .call_tips import CallTips
from .subprocess_handler import SubprocessHandler
from .beep import beep
from .tags import (STDIN, STDOUT, STDERR, EXCEPTION, PROMPT, COMMAND,
                   COMMAND_DEFS, MESSAGE, RESULT_IND, RESULT)
import tags

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

class DreamPie(SimpleGladeApp):
    def __init__(self, pyexec):
        self.gladefile = path.join(data_dir, 'dreampie', 'dreampie.glade')
        SimpleGladeApp.__init__(self, self.gladefile, 'window_main')

        self.config = Config()

        self.window_main.set_icon_from_file(
            path.join(data_dir, 'pixmaps', 'dreampie.png'))

        self.init_textbufferview()

        self.init_sourcebufferview()
        
        self.configure()

        self.output = Output(self.textview)

        self.selection = Selection(self.textview, self.sourceview,
                                   self.on_is_something_selected_changed)

        self.status_bar = StatusBar(self.sourcebuffer, self.statusbar)

        self.vadj_to_bottom = VAdjToBottom(self.scrolledwindow_textview
                                           .get_vadjustment())

        self.history = History(self.textview, self.sourceview, self.config)

        self.histpersist = HistPersist(self.window_main, self.textview,
                                       self.status_bar)

        self.autocomplete = Autocomplete(self.sourceview,
                                         self.complete_attributes,
                                         self.complete_filenames,
                                         INDENT_WIDTH)
        
        # Hack: we connect this signal here, so that it will have lower
        # priority than the key-press event of autocomplete, when active.
        self.sourceview.connect('key-press-event', self.on_sourceview_keypress)

        self.call_tips = CallTips(self.sourceview, self.get_arg_text,
                                  INDENT_WIDTH)

        self.subp = SubprocessHandler(
            pyexec, data_dir,
            self.on_stdout_recv, self.on_stderr_recv, self.on_object_recv,
            self.on_subp_restarted)

        # Is the subprocess executing a command
        self.is_executing = False

        self.set_window_default_size()
        self.window_main.show_all()
        self.set_is_executing(False)
        
        self.show_welcome()
        self.configure_subp()
        self.run_init_code()

        if self.config.get_bool('show-getting-started'):
            self.show_getting_started_dialog()
            self.config.set_bool('show-getting-started', False)
            self.config.save()


    # Selection

    def on_cut(self, widget):
        return self.selection.cut()

    def on_copy(self, widget):
        return self.selection.copy()

    def on_copy_commands_only(self, widget):
        return self.selection.copy_commands_only()

    def on_paste(self, widget):
        return self.selection.paste()

    def on_is_something_selected_changed(self, is_something_selected):
        self.menuitem_cut.props.sensitive = is_something_selected
        self.menuitem_copy.props.sensitive = is_something_selected
        self.menuitem_copy_commands_only.props.sensitive = is_something_selected
        self.menuitem_interrupt.props.sensitive = not is_something_selected

    # Source buffer, Text buffer

    def init_textbufferview(self):
        tv = self.textview
        self.textbuffer = tb = tv.get_buffer()

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

    def on_textview_focus_in(self, widget, event):
        # Clear the selection of the sourcebuffer
        self.sourcebuffer.move_mark(self.sourcebuffer.get_selection_bound(),
                                    self.sourcebuffer.get_iter_at_mark(
                                        self.sourcebuffer.get_insert()))

    def on_sourceview_focus_in(self, widget, event):
        # Clear the selection of the textbuffer
        self.textbuffer.move_mark(self.textbuffer.get_selection_bound(),
                                  self.textbuffer.get_iter_at_mark(
                                        self.textbuffer.get_insert()))

    def write(self, data, *tag_names):
        self.textbuffer.insert_with_tags_by_name(
            self.textbuffer.get_end_iter(), data, *tag_names)

    def set_is_executing(self, is_executing):
        self.is_executing = is_executing
        self.menuitem_execute.props.visible = not is_executing
        self.menuitem_execute.props.sensitive = not is_executing
        self.menuitem_stdin.props.visible = is_executing
        self.menuitem_stdin.props.sensitive = is_executing
        self.menuitem_discard_hist.props.sensitive = not is_executing

    def execute_source(self, warn):
        """Execute the source in the source buffer.
        Return True if successful (No syntax error).
        If warn is True, show the syntax error in the status bar.
        """
        sb = self.sourcebuffer
        tb = self.textbuffer
        source = self.sb_get_text(sb.get_start_iter(), sb.get_end_iter())
        source = source.rstrip()
        is_ok, syntax_error_info = self.call_subp(u'execute', source)
        if not is_ok:
            if warn:
                if syntax_error_info:
                    msg, lineno, offset = syntax_error_info
                    status_msg = _("Syntax error: %s (at line %d col %d)") % (
                        msg, lineno+1, offset+1)
                    # Work around a bug: offset may be wrong, which will cause
                    # gtk to crash if using sb.get_iter_at_line_offset.
                    iter = sb.get_iter_at_line(lineno)
                    iter.forward_chars(offset)
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
        return is_ok

    def send_stdin(self):
        """Send the contents of the sourcebuffer as stdin."""
        sb = self.sourcebuffer
        s = self.sb_get_text(sb.get_start_iter(), sb.get_end_iter())
        if not s.endswith('\n'):
            s += '\n'
        self.write(s[:-1], COMMAND, STDIN)
        # We don't tag the last newline with COMMAND, so that history search
        # will separate different STDIN commands. We do tag it with STDIN
        # so that it will be deleted if the stdin isn't processed - see
        # handle_rem_stdin().
        self.write('\n', STDIN)
        self.vadj_to_bottom.scroll_to_bottom()
        self.subp.write(s)
        self.output.start_new_section()
        sb.delete(sb.get_start_iter(), sb.get_end_iter())

    @sourceview_keyhandler('Return', 0)
    def on_sourceview_return(self):
        sb = self.sourcebuffer

        # If we are on the first line, and it doesn't end with a ' ':
        #   * If we are not executing, try to execute (if failed, continue
        #     with normal behaviour)
        #   * If we are executing, send the line as stdin.
        insert_iter = sb.get_iter_at_mark(sb.get_insert())
        if (insert_iter.equal(sb.get_end_iter())
            and insert_iter.get_line() == 0
            and insert_iter.get_offset() != 0
            and not self.sb_get_text(sb.get_start_iter(),
                                     insert_iter).endswith(' ')):

            if not self.is_executing:
                is_ok = self.execute_source(warn=False)
                if is_ok:
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

    def on_sourceview_keypress(self, widget, event):
        return handle_keypress(self, event, sourceview_keyhandlers)

    # History

    def on_textview_keypress(self, widget, event):
        keyval_name = gdk.keyval_name(event.keyval)
        if keyval_name == 'Return' and event.state == 0:
            return self.history.copy_to_sourceview()

    def on_history_up(self, widget):
        self.history.history_up()

    def on_history_down(self, widget):
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
                response = msg.run()
                msg.destroy()
            else:
                self.is_executing = True
                self.menuitem_execute.props.visible = False
                self.menuitem_stdin.props.visible = True
        if not self.is_executing:
            self.write('>>> ', COMMAND, PROMPT)

    def on_subp_restarted(self):
        self.set_is_executing(False)
        self.write('\n')
        self.write(
            '==================== New Session ====================\n',
            MESSAGE)
        self.output.start_new_section()
        self.configure_subp()
        self.run_init_code()

    def on_restart_subprocess(self, widget):
        self.subp.kill()

    def on_stdout_recv(self, data):
        self.output.write(data, STDOUT)

    def on_stderr_recv(self, data):
        self.output.write(data, STDERR)

    def call_subp(self, funcname, *args):
        self.subp.send_object((funcname, args))
        return self.subp.recv_object()

    def on_object_recv(self, obj):
        assert self.is_executing

        is_success, val_no, val_str, exception_string, rem_stdin = obj

        if not is_success:
            self.output.write(exception_string, EXCEPTION, onnewline=True)
        else:
            if val_str is not None:
                if val_no is not None:
                    self.output.write('%d: ' % val_no, RESULT_IND,
                                      onnewline=True)
                self.output.write(val_str+'\n', RESULT)
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

    def on_execute_command(self, widget):
        if self.is_executing:
            self.send_stdin()
        elif self.sourcebuffer.get_char_count() == 0:
            beep()
        else:
            self.execute_source(True)
        return True

    def on_interrupt(self, widget):
        if self.is_executing:
            self.subp.interrupt()
        else:
            self.status_bar.set_status(
                _("A command isn't being executed currently"))
            beep()

    # History persistence
    
    def on_save_history(self, widget):
        self.histpersist.save()
    
    def on_save_history_as(self, widget):
        self.histpersist.save_as()
    
    def on_load_history(self, widget):
        self.histpersist.load()
    
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

    def on_discard_history(self, widget):
        xml = glade.XML(self.gladefile, 'discard_hist_dialog')
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

    # Other events

    def on_show_completions(self, widget):
        self.autocomplete.show_completions(is_auto=False, complete=False)

    def complete_attributes(self, expr):
        if self.is_executing:
            return None
        return self.call_subp(u'complete_attributes', expr)

    def complete_filenames(self, str_prefix, text, str_char):
        if self.is_executing:
            return None
        return self.call_subp(u'complete_filenames', str_prefix, text, str_char)

    def on_show_calltip(self, widget):
        self.call_tips.show(is_auto=False)

    def get_arg_text(self, expr):
        if self.is_executing:
            return None
        return self.call_subp(u'get_arg_text', expr)

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

    def on_preferences(self, widget):
        cd = ConfigDialog(self.config, self.gladefile, self.window_main)
        r = cd.run()
        if r == gtk.RESPONSE_OK:
            self.configure()
            self.configure_subp()
        cd.destroy()

    def on_clear_reshist(self, widget):
        self.call_subp(u'clear_reshist')
        self.status_bar.set_status(_("Result history cleared."))

    def on_close(self, widget, event):
        self.quit()
        return True

    def on_quit(self, widget):
        self.quit()

    def quit(self):
        msg = gtk.MessageDialog(self.window_main, gtk.DIALOG_MODAL,
                                gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
                                _("Are you sure you want to quit?"))
        response = msg.run()
        msg.destroy()
        if response == gtk.RESPONSE_YES:
            self.window_main.destroy()
            self.subp.kill()
            gtk.main_quit()

    def on_about(self, widget):
        xml = glade.XML(self.gladefile, 'about_dialog')
        d = xml.get_widget('about_dialog')
        d.set_transient_for(self.window_main)
        d.set_version(__version__)
        d.set_logo(gdk.pixbuf_new_from_file(
            path.join(data_dir, 'pixmaps', 'dreampie.png')))
        d.run()
        d.destroy()
    
    def on_getting_started(self, widget):
        self.show_getting_started_dialog()
    
    def show_getting_started_dialog(self):
        xml = glade.XML(self.gladefile, 'getting_started_dialog')
        d = xml.get_widget('getting_started_dialog')
        d.set_transient_for(self.window_main)
        d.run()
        d.destroy()


def main():
    usage = "%prog [options] [python-executable]"
    version = 'DreamPie %s' % __version__
    parser = OptionParser(usage=usage, version=version)
    if sys.platform == 'win32':
        parser.add_option("--dont-hide-console-window", action="store_true",
                          dest="dont_hide_console",
                          help="Don't hide the console window")

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
              "Please create a shortcut to something like 'dreampie.exe "
              "c:\\python26\\python.exe'."))
        response = msg.run()
        msg.destroy()
        sys.exit(1)
    else:
        pyexec = sys.executable
        
    
    if sys.platform == 'win32' and not opts.dont_hide_console:
        from .hide_console_window import hide_console_window
        hide_console_window()

    gtk.widget_set_default_direction(gtk.TEXT_DIR_LTR)
    dp = DreamPie(pyexec)
    gtk.main()
