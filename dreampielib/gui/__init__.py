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
from gtk import gdk
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
from .config import Config
from .write_command import write_command
from .newline_and_indent import newline_and_indent
from .output import Output
from .selection import Selection
from .status_bar import StatusBar
from .vadj_to_bottom import VAdjToBottom
from .history import History
from .autocomplete import Autocomplete
from .call_tips import CallTips
from .subprocess_handler import SubprocessHandler
from .beep import beep

# Tags and colors

from .tags import STDIN, STDOUT, STDERR, EXCEPTION, PROMPT, COMMAND, MESSAGE

from .tags import KEYWORD, BUILTIN, STRING, NUMBER, COMMENT

INDENT_WIDTH = 4

# Default line length, by which we set the default window size
LINE_LEN = 80

# Time to wait before autocompleting, to see if the user continues to type
AUTOCOMPLETE_WAIT = 400

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
    def __init__(self, pyexec):
        gladefile = os.path.join(data_dir, 'dreampie', 'dreampie.glade')
        SimpleGladeApp.__init__(self, gladefile)

        self.config = Config()

        self.window_main.set_icon_from_file(
            os.path.join(data_dir, 'pixmaps', 'dreampie.png'))

        self.init_textbufferview()

        self.init_sourcebufferview()

        self.output = Output(self.textview)

        self.selection = Selection(self.textview, self.sourceview,
                                   self.on_is_something_selected_changed)

        self.status_bar = StatusBar(self.sourcebuffer, self.statusbar)

        self.vadj_to_bottom = VAdjToBottom(self.scrolledwindow_textview
                                           .get_vadjustment())

        self.history = History(self.textview, self.sourceview)

        self.autocomplete = Autocomplete(self.sourceview,
                                         self.complete_attributes,
                                         self.subp_abspath,
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

        self.show_welcome()

        self.set_window_default_size()
        self.window_main.show_all()
        
        if self.config.get('show-getting-started') in ('True', 'true', '1'):
            self.getting_started_dialog.run()
            self.getting_started_dialog.hide()
            self.config.set('show-getting-started', 'False')


    # Colors

    def get_fg_color(self, name):
        return self.config.get('%s-fg' % name, section='Colors')

    def get_bg_color(self, name):
        return self.config.get('%s-bg' % name, section='Colors')

    def get_style_scheme_spec(self):
        mapping = {
            'text': 'text',
            
            'def:keyword': KEYWORD,
            'def:preprocessor': KEYWORD,

            'def:builtin': BUILTIN,
            'def:special-constant': BUILTIN,
            'def:type': BUILTIN,

            'def:string': STRING,
            'def:number': NUMBER,
            'def:comment': COMMENT,

            'bracket-match': 'bracket-match',
            }

        res = {}
        for key, value in mapping.iteritems():
            res[key] = dict(foreground=self.get_fg_color(value),
                            background=self.get_bg_color(value))
        return res


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

        tv.modify_base(0, gdk.color_parse(self.get_bg_color('text')))
        tv.modify_text(0, gdk.color_parse(self.get_fg_color('text')))
        tv.modify_font(pango.FontDescription(self.config.get('font')))

        # We have to add the tags in a specific order, so that the priority
        # of the syntax tags will be higher.
        for tag in (STDOUT, STDERR, EXCEPTION, COMMAND, PROMPT, STDIN, MESSAGE,
                    KEYWORD, BUILTIN, STRING, NUMBER, COMMENT):
            tb.create_tag(tag, foreground=self.get_fg_color(tag),
                          background=self.get_bg_color(tag))

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
        self.sourcebuffer = gtksourceview2.Buffer()
        self.sourceview = gtksourceview2.View(self.sourcebuffer)

        lm = gtksourceview2.LanguageManager()
        python = lm.get_language('python')
        self.sourcebuffer.set_language(python)
        self.sourcebuffer.set_style_scheme(
            make_style_scheme(self.get_style_scheme_spec()))
        self.sourceview.modify_font(
            pango.FontDescription(self.config.get('font')))
        self.scrolledwindow_sourceview.add(self.sourceview)
        self.sourceview.connect('focus-in-event', self.on_sourceview_focus_in)
        self.sourceview.grab_focus()

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
            self.output.set_mark(tb.get_end_iter())
            sb.delete(sb.get_start_iter(), sb.get_end_iter())
            self.vadj_to_bottom.scroll_to_bottom()
            self.is_executing = True
            self.menuitem_execute.props.visible = False
            self.menuitem_stdin.props.visible = True
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
        self.output.set_mark(self.textbuffer.get_end_iter())
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
        r = gdk.keymap_get_default().translate_keyboard_state(
            event.hardware_keycode, event.state, event.group)
        if r is None:
            # This seems to be the case when pressing CapsLock on win32
            return
        keyval, group, level, consumed_mods = r
        state = event.state & ~consumed_mods
        keyval_name = gdk.keyval_name(keyval)
        try:
            func = sourceview_keyhandlers[keyval_name, state]
        except KeyError:
            pass
        else:
            return func(self)

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

        self.write('>>> ', COMMAND, PROMPT)

    def on_subp_restarted(self):
        self.write(
            '\n==================== New Session ====================\n',
            MESSAGE)
        self.write('>>> ', COMMAND, PROMPT)

    def on_restart_subprocess(self, widget):
        self.subp.kill()

    def on_stdout_recv(self, data):
        self.output.write(data, STDOUT)

    def on_stderr_recv(self, data):
        self.output.write(data, STDERR)

    def call_subp(self, funcname, *args):
        self.subp.send_object((funcname, args))
        return self.subp.recv_object()

    def on_object_recv(self, object):
        assert self.is_executing

        is_ok, exc_info, rem_stdin = object

        if not is_ok:
            self.write(exc_info, EXCEPTION)
        if self.textbuffer.get_end_iter().get_line_offset() != 0:
            self.write('\n')
        self.write('>>> ', COMMAND, PROMPT)
        self.is_executing = False
        self.menuitem_execute.props.visible = True
        self.menuitem_stdin.props.visible = False
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

    # Other events

    def on_show_completions(self, widget):
        self.autocomplete.show_completions(is_auto=False, complete=False)

    def complete_attributes(self, expr):
        if self.is_executing:
            return None
        return self.call_subp(u'complete_attributes', expr)

    def subp_abspath(self, path):
        if self.is_executing:
            return None
        return self.call_subp(u'abspath', path)

    def on_show_calltip(self, widget):
        self.call_tips.show(is_auto=False)

    def get_arg_text(self, expr):
        if self.is_executing:
            return None
        return self.call_subp(u'get_arg_text', expr)

    def on_choose_font(self, widget):
        fontsel = gtk.FontSelectionDialog(_("Choose DreamPie font"))
        fontsel.set_font_name(self.config.get('font'))
        response = fontsel.run()
        font_name = fontsel.get_font_name()
        fontsel.destroy()
        if response == gtk.RESPONSE_OK:
            self.config.set('font', font_name)
            font = pango.FontDescription(font_name)
            self.textview.modify_font(font)
            self.sourceview.modify_font(font)
            self.set_window_default_size()

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
        w = gtk.AboutDialog()
        w.set_name('DreamPie')
        w.set_version(__version__)
        w.set_comments(_("The interactive Python shell you've always dreamed "
                         "about!"))
        w.set_copyright(_('Copyright 2008,2009 Noam Yorav-Raphael'))
        w.set_license(
            "DreamPie is free software; you can redistribute it and/or modify "
            "it under the terms of the GNU General Public License as published "
            "by the Free Software Foundation; either version 3 of the License, "
            "or (at your option) any later version.\n\n"
            "DreamPie is distributed in the hope that it will be useful, but "
            "WITHOUT ANY WARRANTY; without even the implied warranty of "
            "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU "
            "General Public License for more details.\n\n"
            "You should have received a copy of the GNU General Public License "
            "along with DreamPie; if not, write to the Free Software "
            "Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  "
            "02110-1301 USA"
            )
        w.set_wrap_license(True)
        w.set_authors([_('Noam Yorav-Raphael <noamraph@gmail.com>')])
        w.set_logo(gdk.pixbuf_new_from_file(
            os.path.join(data_dir, 'pixmaps', 'dreampie.png')))
        w.run()
        w.destroy()
    
    def on_getting_started(self, widget):
        self.getting_started_dialog.run()
        self.getting_started_dialog.hide()


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
