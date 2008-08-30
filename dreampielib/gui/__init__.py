# -*- coding: utf-8 -*-
import sys
import os
import signal
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
from . import PyParse

# Tags and colors

STDOUT = 'stdout'; STDERR = 'stderr'; EXCEPTION = 'exception'
PROMPT = 'prompt'; FIRST_PROMPT = 'first_prompt'; COMMAND = 'command'
STDIN = 'stdin'

KEYWORD = 'keyword'; BUILTIN = 'builtin'; STRING = 'string'
NUMBER = 'number'; COMMENT = 'comment'

colors = {
    STDOUT: '#bcffff',
    STDERR: 'red',
    EXCEPTION: 'red',
    PROMPT: '#e400b6',
    COMMAND: 'white',
    STDIN: 'white',

    KEYWORD: '#ff7700',
    BUILTIN: '#efcfcf',
    STRING: '#00e400',
    NUMBER: '#aeacff',
    COMMENT: '#c9a3a0',
    }

INDENT_WIDTH = 4

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

        self.init_textbufferview()

        self.init_sourcebufferview()

        self.init_selection()

        self.init_status()

        self.init_inputentry()

        self.init_vadj()

        self.init_history()

        self.is_connected = False
        self.sock = self.popen = None
        # Is the subprocess executing a command
        self.is_executing = False
        self.start_subp()

        self.window_main.show_all()
        # For some reason this works only after showing the window
        self.update_menuitem_switch_input()

    # Selection

    def init_selection(self):
        self.primary_selection = gtk.Clipboard(selection=gdk.SELECTION_PRIMARY)
        self.primary_selection.connect('owner-change',
                                       self.on_selection_changed)
        self.clipboard = gtk.Clipboard()

    def on_selection_changed(self, clipboard, event):
        is_something_selected = (self.textbuffer.get_has_selection()
                                 or self.sourcebuffer.get_has_selection())
        self.menuitem_copy.props.sensitive = is_something_selected
        self.menuitem_interrupt.props.sensitive = not is_something_selected

    def on_cut(self, widget):
        if self.sourcebuffer.get_has_selection():
            self.sourcebuffer.cut_clipboard(self.clipboard, True)
        else:
            gdk.beep()

    def on_copy(self, widget):
        if self.textbuffer.get_has_selection():
            self.textbuffer.copy_clipboard(self.clipboard)
        elif self.sourcebuffer.get_has_selection():
            self.sourcebuffer.copy_clipboard(self.clipboard)
        else:
            gdk.beep()

    def on_paste(self, widget):
        if self.sourceview.is_focus():
            self.sourcebuffer.paste_clipboard(self.clipboard, None, True)
        else:
            gdk.beep()

    # Status Bar

    def init_status(self):
        # id of a message displayed in the status bar to be removed when
        # the contents of the source buffer is changed
        self.sourcebuffer_status_id = None
        self.sourcebuffer_changed_handler_id = None

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

    # Input Entry

    def init_inputentry(self):
        self.inputentry = gtk.Entry()
        self.inputentry.connect('key-press-event',
                                self.on_inputentry_keypress)
        self.inputentry.show()
        self.is_inputentry_displayed = False
        
    def on_inputentry_keypress(self, widget, event):
        keyval_name = gdk.keyval_name(event.keyval)
        if keyval_name == 'Return':
            s = self.inputentry.get_text()+'\n'
            self.write(s, STDIN)
            self.popen.stdin.write(s)
            self.inputentry.set_text('')
            return True
        
    def show_inputentry(self):
        if not self.is_inputentry_displayed:
            self.vpaned_main.remove(self.scrolledwindow_sourceview)
            self.vpaned_main.add2(self.inputentry)
            self.is_inputentry_displayed = True

    def hide_inputentry(self):
        if self.is_inputentry_displayed:
            self.vpaned_main.remove(self.inputentry)
            self.vpaned_main.add2(self.scrolledwindow_sourceview)
            self.is_inputentry_displayed = False

    def on_show_inputentry(self, widget):
        assert self.is_executing
        self.show_inputentry()
        self.update_menuitem_switch_input()
        self.inputentry.grab_focus()

    def on_hide_inputentry(self, widget):
        assert self.is_executing
        self.hide_inputentry()
        self.update_menuitem_switch_input()
        self.sourceview.grab_focus()

    def update_menuitem_switch_input(self):
        if not self.is_inputentry_displayed:
            self.menuitem_show_inputentry.props.visible = True
            self.menuitem_hide_inputentry.props.visible = False
        else:
            self.menuitem_show_inputentry.props.visible = False
            self.menuitem_hide_inputentry.props.visible = True
            
        if self.is_executing:
            self.menuitem_show_inputentry.set_sensitive(True)
            self.menuitem_hide_inputentry.set_sensitive(True)
        else:
            self.menuitem_show_inputentry.set_sensitive(False)
            self.menuitem_hide_inputentry.set_sensitive(False)

    # Vertical adjustment

    def init_vadj(self):
        self.vadj = self.scrolledwindow_textview.get_vadjustment()
        # These make sure that the textview vadjustment automatically
        # scrolls if it shows the bottom
        self.vadj.connect('changed', self.on_vadj_changed)
        self.vadj.connect('value-changed', self.on_vadj_value_changed)
        self.vadj_was_at_bottom = self.vadj_is_at_bottom()
        self.vadj_scroll_to_bottom()

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

    # Source buffer, Text buffer

    def init_textbufferview(self):
        self.textbuffer = self.textview.get_buffer()

        self.textview.modify_base(0, gdk.color_parse('black'))
        self.textview.modify_text(0, gdk.color_parse('white'))
        self.textview.modify_font(
            pango.FontDescription('courier new,monospace'))

        # We have to add the tags in a specific order, so that the priority
        # of the syntax tags will be higher.
        for tag in (STDOUT, STDERR, EXCEPTION, PROMPT, COMMAND, STDIN,
                    KEYWORD, BUILTIN, STRING, NUMBER, COMMENT):
            self.textbuffer.create_tag(tag, foreground=colors[tag])
        self.textbuffer.create_tag(FIRST_PROMPT, foreground=colors[PROMPT])

        self.textview.connect('key-press-event', self.on_textview_keypress)
        self.textview.connect('focus-in-event', self.on_textview_focus_in)

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
            self.update_menuitem_switch_input()
        return is_ok

    @sourceview_keyhandler('Return', 0)
    def on_sourceview_return(self):
        sb = self.sourcebuffer

        # Possibly execute, if we are on the first line and everything
        # works ok.
        if not self.is_executing:
            insert_iter = sb.get_iter_at_mark(sb.get_insert())
            if (insert_iter.equal(sb.get_end_iter())
                and insert_iter.get_line() == 0
                and insert_iter.get_offset() != 0
                and not sb.get_text(sb.get_start_iter(),
                                    insert_iter).endswith(' ')):
                is_ok = self.execute_source(False)
                if is_ok:
                    return True
                
        # We didn't execute, so newline-and-indent.
        # This is based on newline_and_indent_event(),
        # from idlelib/EditorWindow.py
        sb.begin_user_action()
        insert_mark = sb.get_insert()
        insert = lambda: sb.get_iter_at_mark(insert_mark)
        try:
            sb.delete_selection(True, True)
            line = sb.get_text(sb.get_iter_at_line(insert().get_line()),
                               insert())
            i, n = 0, len(line)
            while i < n and line[i] in " \t":
                i = i+1
            if i == n:
                # the cursor is in or at leading indentation in a continuation
                # line; just copy the indentation
                sb.insert_at_cursor('\n'+line)
                self.sourceview.scroll_mark_onscreen(sb.get_insert())
                return True
            indent = line[:i]
            # strip whitespace before insert point
            i = 0
            while line and line[-1] in " \t":
                line = line[:-1]
                i = i+1
            if i:
                sb.delete(sb.get_iter_at_line_offset(insert().get_line(),
                                                     len(line)),
                          insert())
            # strip whitespace after insert point
            it = insert(); it.forward_to_line_end()
            after_insert = sb.get_text(insert(), it)
            i = 0
            while i < len(after_insert) and after_insert[i] in " \t":
                i += 1
            if i > 0:
                it = insert(); it.forward_chars(i)
                sb.delete(insert(), it)
            # start new line
            sb.insert_at_cursor('\n')
            self.sourceview.scroll_mark_onscreen(sb.get_insert())
            # scroll to see the beginning of the line
            self.scrolledwindow_sourceview.get_hadjustment().set_value(0)

            # adjust indentation for continuations and block
            # open/close first need to find the last stmt
            y = PyParse.Parser(INDENT_WIDTH, INDENT_WIDTH)
            y.set_str(sb.get_text(sb.get_start_iter(), insert()))
            c = y.get_continuation_type()
            if c != PyParse.C_NONE:
                # The current stmt hasn't ended yet.
                if c == PyParse.C_STRING_FIRST_LINE:
                    # after the first line of a string; do not indent at all
                    pass
                elif c == PyParse.C_STRING_NEXT_LINES:
                    # inside a string which started before this line;
                    # just mimic the current indent
                    sb.insert_at_cursor(indent)
                elif c == PyParse.C_BRACKET:
                    # line up with the first (if any) element of the
                    # last open bracket structure; else indent one
                    # level beyond the indent of the line with the
                    # last open bracket
                    sb.insert_at_cursor(' ' * y.compute_bracket_indent())
                elif c == PyParse.C_BACKSLASH:
                    # if more than one line in this stmt already, just
                    # mimic the current indent; else if initial line
                    # has a start on an assignment stmt, indent to
                    # beyond leftmost =; else to beyond first chunk of
                    # non-whitespace on initial line
                    if y.get_num_lines_in_stmt() > 1:
                        sb.insert_at_cursor(indent)
                    else:
                        sb.insert_at_cursor(' ' * y.compute_backslash_indent())
                else:
                    assert False, "bogus continuation type %r" % (c,)
                return True

            # This line starts a brand new stmt; indent relative to
            # indentation of initial line of closest preceding
            # interesting stmt.
            indent = len(y.get_base_indent_string())
            if y.is_block_opener():
                indent = (indent // INDENT_WIDTH + 1) * INDENT_WIDTH
            elif y.is_block_closer():
                indent = max(((indent - 1) // INDENT_WIDTH) * INDENT_WIDTH, 0)
            sb.insert_at_cursor(' ' * indent)
            return True
        finally:
            sb.end_user_action()

    @sourceview_keyhandler('Tab', 0)
    def on_sourceview_tab(self):
        sb = self.sourcebuffer
        insert = sb.get_iter_at_mark(sb.get_insert())
        insert_linestart = sb.get_iter_at_line(insert.get_line())
        line = sb.get_text(insert_linestart, insert)

        if not line.strip():
            # We are at the beginning of a line, so indent - forward to next
            # "tab stop"
            sb.insert_at_cursor(' ' * (INDENT_WIDTH - len(line) % INDENT_WIDTH))

        else:
            # Completion should come here
            gdk.beep()

        self.sourceview.scroll_mark_onscreen(sb.get_insert())
        return True

    @sourceview_keyhandler('BackSpace', 0)
    def on_sourceview_backspace(self):
        sb = self.sourcebuffer
        insert = sb.get_iter_at_mark(sb.get_insert())
        insert_linestart = sb.get_iter_at_line(insert.get_line())
        line = sb.get_text(insert_linestart, insert)

        if line and not line.strip():
            # There are only space before us, so remove spaces up to last
            # "tab stop"
            delete_from = ((len(line) - 1) // INDENT_WIDTH) * INDENT_WIDTH
            it = sb.get_iter_at_line_offset(insert.get_line(), delete_from)
            sb.delete(it, insert)
            self.sourceview.scroll_mark_onscreen(sb.get_insert())
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

    def init_history(self):
        tb = self.textbuffer

        self.hist_prefix = None
        self.hist_sourcebuffer_changed_id = None
        self.hist_mark = tb.create_mark('history', tb.get_end_iter(), False)

        self.ihist_prefix = None
        self.ihist_inputentry_changed_id = None
        self.ihist_mark = tb.create_mark('ihistory', tb.get_end_iter(), False)

    def iter_backward_to_tag(self, it, tag):
        """Move the textiter backward to a beginning of a tag.
        return True if there was one.
        """
        tb = self.textbuffer
        r = it.backward_to_tag_toggle(tag)
        if r and it.ends_tag(tag):
            r = it.backward_to_tag_toggle(tag)
        return r

    def iter_forward_to_tag(self, it, tag):
        """Move the textiter forward to a beginning of a tag.
        return True if there was one.
        """
        tb = self.textbuffer
        r = it.forward_to_tag_toggle(tag)
        if r and it.ends_tag(tag):
            r = it.forward_to_tag_toggle(tag)
        if it.equal(tb.get_end_iter()):
            r = False
        return r

    def iter_get_command(self, it, only_first_line=False):
        """Get a textiter placed at the beginning of a first_prompt.
        Return the command at that prompt.
        """
        tb = self.textbuffer
        first_prompt = tb.get_tag_table().lookup(FIRST_PROMPT)
        command = tb.get_tag_table().lookup(COMMAND)
        it_next_1st = it.copy()
        self.iter_forward_to_tag(it_next_1st, first_prompt)
        it = it.copy()
        s = ''
        r = it.forward_to_tag_toggle(command)
        if not r:
            # We are at the last prompt
            return ''
        assert it.begins_tag(command)
        while it.compare(it_next_1st) < 0:
            it2 = it.copy()
            it2.forward_to_tag_toggle(command)
            s += tb.get_text(it, it2)
            if only_first_line:
                break
            it = it2
            it.forward_to_tag_toggle(command)
        return s

    def on_textview_return(self):
        # Copy the current command to the sourceview
        tb = self.textbuffer
        first_prompt = tb.get_tag_table().lookup(FIRST_PROMPT)
        it = tb.get_iter_at_mark(tb.get_insert())
        if not it.begins_tag(first_prompt):
            self.iter_backward_to_tag(it, first_prompt)
        s = self.iter_get_command(it)
        if not s:
            gdk.beep()
            return True
        self.sourcebuffer.set_text(s)
        self.sourceview.grab_focus()
        return True

    def on_textview_keypress(self, widget, event):
        keyval_name = gdk.keyval_name(event.keyval)
        if keyval_name == 'Return' and event.state == 0:
            return self.on_textview_return()

    def on_history_sb_changed(self, widget):
        self.hist_prefix = None
        self.sourcebuffer.disconnect(self.hist_sourcebuffer_changed_id)
        self.hist_sourcebuffer_changed_id = None

    def on_ihistory_ie_changed(self, widget):
        self.ihist_prefix = None
        self.inputentry.disconnect(self.ihist_inputentry_changed_id)
        self.ihist_inputentry_changed_id = None

    def on_history_up(self, widget):
        if self.textview.is_focus():
            tb = self.textbuffer
            first_prompt = tb.get_tag_table().lookup(FIRST_PROMPT)
            insert = tb.get_insert()
            it = tb.get_iter_at_mark(insert)
            r = self.iter_backward_to_tag(it, first_prompt)
            if r:
                self.textbuffer.place_cursor(it)
                self.textview.scroll_mark_onscreen(insert)
            else:
                gdk.beep()

        elif self.sourceview.is_focus():
            tb = self.textbuffer
            sb = self.sourcebuffer
            first_prompt = tb.get_tag_table().lookup(FIRST_PROMPT)
            if self.hist_prefix is None:
                # Don't allow prefixes of more than one line
                if sb.get_end_iter().get_line() != 0:
                    gdk.beep()
                    return
                self.hist_prefix = sb.get_text(sb.get_start_iter(),
                                               sb.get_end_iter())
                tb.move_mark(self.hist_mark, tb.get_end_iter())
            it = tb.get_iter_at_mark(self.hist_mark)
            while True:
                r = self.iter_backward_to_tag(it, first_prompt)
                if not r:
                    gdk.beep()
                    break
                first_line = self.iter_get_command(it, only_first_line=True)
                if first_line and first_line.startswith(self.hist_prefix):
                    command = self.iter_get_command(it)
                    if self.hist_sourcebuffer_changed_id is not None:
                        # There is no callback if we haven't changed the text
                        # yet.
                        sb.disconnect(self.hist_sourcebuffer_changed_id)
                    sb.set_text(command)
                    sb.place_cursor(sb.get_end_iter())
                    self.hist_sourcebuffer_changed_id = (
                        sb.connect('changed', self.on_history_sb_changed))
                    tb.move_mark(self.hist_mark, it)
                    break

        elif self.inputentry.is_focus():
            tb = self.textbuffer
            stdin = tb.get_tag_table().lookup(STDIN)
            ie = self.inputentry
            if self.ihist_prefix is None:
                self.ihist_prefix = ie.get_text()
                tb.move_mark(self.ihist_mark, tb.get_end_iter())
            it = tb.get_iter_at_mark(self.ihist_mark)
            while True:
                r = self.iter_backward_to_tag(it, stdin)
                if not r:
                    gdk.beep()
                    break
                command = self.iter_get_stdin(it)
                # XXX
                first_line = self.iter_get_command(it, only_first_line=True)
                if first_line and first_line.startswith(self.hist_prefix):
                    command = self.iter_get_command(it)
                    if self.hist_sourcebuffer_changed_id is not None:
                        # There is no callback if we haven't changed the text
                        # yet.
                        sb.disconnect(self.hist_sourcebuffer_changed_id)
                    sb.set_text(command)
                    sb.place_cursor(sb.get_end_iter())
                    self.hist_sourcebuffer_changed_id = (
                        sb.connect('changed', self.on_history_sb_changed))
                    tb.move_mark(self.hist_mark, it)
                    break
            

        else:
            gdk.beep()

    def on_history_down(self, widget):
        if self.textview.is_focus():
            tb = self.textbuffer
            first_prompt = tb.get_tag_table().lookup(FIRST_PROMPT)
            insert = tb.get_insert()
            it = tb.get_iter_at_mark(insert)
            r = self.iter_forward_to_tag(it, first_prompt)
            if r:
                self.textbuffer.place_cursor(it)
                self.textview.scroll_mark_onscreen(insert)
            else:
                gdk.beep()

        elif self.sourceview.is_focus():
            tb = self.textbuffer
            first_prompt = tb.get_tag_table().lookup(FIRST_PROMPT)
            sb = self.sourcebuffer
            if self.hist_prefix is None:
                gdk.beep()
                return
            it = tb.get_iter_at_mark(self.hist_mark)
            if it.equal(tb.get_end_iter()):
                gdk.beep()
                return
            while True:
                r = self.iter_forward_to_tag(it, first_prompt)
                if not r:
                    # Write the prefix in the source buffer
                    sb.disconnect(self.hist_sourcebuffer_changed_id)
                    sb.set_text(self.hist_prefix)
                    sb.place_cursor(sb.get_end_iter())
                    self.hist_sourcebuffer_changed_id = (
                        sb.connect('changed', self.on_history_sb_changed))
                    tb.move_mark(self.hist_mark, tb.get_end_iter())
                    break
                first_line = self.iter_get_command(it, only_first_line=True)
                if first_line and first_line.startswith(self.hist_prefix):
                    command = self.iter_get_command(it)
                    sb.disconnect(self.hist_sourcebuffer_changed_id)
                    sb.set_text(command)
                    sb.place_cursor(sb.get_end_iter())
                    self.hist_sourcebuffer_changed_id = (
                        sb.connect('changed', self.on_history_sb_changed))
                    tb.move_mark(self.hist_mark, it)
                    break
        else:
            gdk.beep()

    # Subprocess

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

        self.write('>>> ', FIRST_PROMPT)

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
            self.write('Exception: %s\n' % str(exc_info), EXCEPTION)
            
        self.write('>>> ', FIRST_PROMPT)
        self.is_executing = False
        had_focus = self.inputentry.is_focus()
        self.hide_inputentry()
        if had_focus:
            self.sourceview.grab_focus()
        self.update_menuitem_switch_input()

    def on_execute_command(self, widget):
        if self.is_executing:
            self.set_sourcebuffer_status(
                _('Another command is currently being executed.'))
            gdk.beep()
        elif self.sourcebuffer.get_char_count() == 0:
            gdk.beep()
        else:
            self.execute_source(True)
        return True

    def on_interrupt(self, widget):
        if self.is_executing:
            os.kill(self.popen.pid, signal.SIGINT)
        else:
            self.set_sourcebuffer_status(
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
