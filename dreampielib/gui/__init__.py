# -*- coding: utf-8 -*-
import sys
import os
import time
import tempfile

import logging
from logging import debug
logging.basicConfig(format="dreampie: %(message)s", level=logging.DEBUG)

import pygtk
pygtk.require('2.0')
import gobject
import gtk
from gtk import gdk
import pango
import gtksourceview2

from .SimpleGladeApp import SimpleGladeApp
from .write_command import write_command
from .newline_and_indent import newline_and_indent

from .selection import Selection
from .status_bar import StatusBar
from .vadj_to_bottom import VAdjToBottom
from .history import History
from .subp import Subprocess

# Tags and colors

from .tags import STDIN, STDOUT, STDERR, EXCEPTION, PROMPT, COMMAND, MESSAGE

from .tags import KEYWORD, BUILTIN, STRING, NUMBER, COMMENT

colors = {
    STDIN: 'white',
    STDOUT: '#bcffff',
    STDERR: '#ff8080',
    EXCEPTION: '#ff8080',
    PROMPT: '#e400b6',
    COMMAND: 'white',
    MESSAGE: 'yellow',

    KEYWORD: '#ff7700',
    BUILTIN: '#efcfcf',
    STRING: '#00e400',
    NUMBER: '#aeacff',
    COMMENT: '#c9a3a0',
    }

INDENT_WIDTH = 4

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
        gladefile = os.path.join(os.path.dirname(__file__),
                                 'dreampie.glade')
        SimpleGladeApp.__init__(self, gladefile)

        self.window_main.set_icon_from_file(
            os.path.join(os.path.dirname(__file__), 'dreampie.svg'))

        self.init_textbufferview()

        self.init_sourcebufferview()

        self.selection = Selection(self.textview, self.sourceview,
                                   self.on_is_something_selected_changed)

        self.status_bar = StatusBar(self.sourcebuffer, self.statusbar)

        self.vadj_to_bottom = VAdjToBottom(self.scrolledwindow_textview
                                           .get_vadjustment())

        self.history = History(self.textview, self.sourceview)

        self.subp = Subprocess(
            executable,
            self.on_stdout_recv, self.on_stderr_recv, self.on_object_recv,
            self.on_subp_restarted)
        # Is the subprocess executing a command
        self.is_executing = False

        self.show_welcome()

        self.set_window_default_size()
        self.window_main.show_all()


    # Selection

    def on_cut(self, widget):
        return self.selection.on_cut(widget)

    def on_copy(self, widget):
        return self.selection.on_copy(widget)

    def on_paste(self, widget):
        return self.selection.on_paste(widget)

    def on_is_something_selected_changed(self, is_something_selected):
        self.menuitem_copy.props.sensitive = is_something_selected
        self.menuitem_interrupt.props.sensitive = not is_something_selected

    # Source buffer, Text buffer

    def init_textbufferview(self):
        tv = self.textview
        self.textbuffer = tb = tv.get_buffer()

        tv.modify_base(0, gdk.color_parse('black'))
        tv.modify_text(0, gdk.color_parse('white'))
        tv.modify_font(pango.FontDescription('courier new,monospace'))

        # We have to add the tags in a specific order, so that the priority
        # of the syntax tags will be higher.
        for tag in (STDOUT, STDERR, EXCEPTION, COMMAND, PROMPT, STDIN, MESSAGE,
                    KEYWORD, BUILTIN, STRING, NUMBER, COMMENT):
            tb.create_tag(tag, foreground=colors[tag])

        tv.connect('key-press-event', self.on_textview_keypress)
        tv.connect('focus-in-event', self.on_textview_focus_in)

    def set_window_default_size(self):
        tv = self.textview
        context = tv.get_pango_context()
        metrics = context.get_metrics(tv.style.font_desc,
                                      context.get_language())
        width = pango.PIXELS(metrics.get_approximate_digit_width()*81)
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
            make_style_scheme(default_style_scheme_spec))
        self.sourceview.modify_font(
            pango.FontDescription('courier new,monospace'))
        self.scrolledwindow_sourceview.add(self.sourceview)
        self.sourceview.connect('key-press-event', self.on_sourceview_keypress)
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
        self.subp.send_object(('exec', source))
        is_ok, syntax_error_info = self.subp.recv_object()
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
                self.status_bar.set_status(status_msg)
                gdk.beep()
        else:
            write_command(self.write, source.strip())
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
            gdk.beep()

        self.sv_scroll_cursor_onscreen()
        return True

    @sourceview_keyhandler('ISO_Left_Tab', gdk.SHIFT_MASK)
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

    def on_sourceview_keypress(self, widget, event):
        keyval_name = gdk.keyval_name(event.keyval)
        try:
            func = sourceview_keyhandlers[keyval_name, event.state]
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
        s = 'Python %s on %s\n' % (sys.version, sys.platform)
        s +='Type "copyright", "credits" or "license()" for more information.\n'
        s += 'DreamPie 0.1\n'
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
        self.write(data, STDOUT)

    def on_stderr_recv(self, data):
        self.write(data, STDERR)

    def on_object_recv(self, object):
        assert self.is_executing

        is_ok, exc_info, rem_stdin = object

        if not is_ok:
            self.write(exc_info, EXCEPTION)
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
            gdk.beep()
        else:
            self.execute_source(True)
        return True

    def on_interrupt(self, widget):
        if self.is_executing:
            self.subp.interrupt()
        else:
            self.status_bar.set_status(
                _("A command isn't being executed currently"))
            gdk.beep()

    # Other events

    def on_close(self, widget, event):
        gtk.main_quit()

    def on_about(self, widget):
        w = gtk.AboutDialog()
        w.set_name('DreamPie')
        w.set_version('0.1')
        w.set_comments(_("The interactive Python shell you've always dreamed "
                         "about!"))
        w.set_copyright(_('Copyright © 2008 Noam Raphael'))
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
        w.set_authors([_('Noam Raphael <noamraph@gmail.com>')])
        w.set_logo(gdk.pixbuf_new_from_file(
            os.path.join(os.path.dirname(__file__), 'dreampie.svg')))
        w.run()
        w.destroy()


            

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
