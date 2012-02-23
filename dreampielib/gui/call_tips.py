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

__all__ = ['CallTips']

import gtk

try:
    from glib import idle_add
except ImportError:
    from gobject import idle_add

from .hyper_parser import HyperParser
from .call_tip_window import CallTipWindow
from .common import beep, get_text

class CallTips(object):
    def __init__(self, sourceview, sv_changed, window_main, get_func_doc,
                 INDENT_WIDTH):
        self.sourceview = sourceview
        self.sourcebuffer = sb = sourceview.get_buffer()
        sv_changed.append(self.on_sv_changed)
        self.window_main = window_main
        self.get_func_doc = get_func_doc
        self.INDENT_WIDTH = INDENT_WIDTH

        self.ctwindow = CallTipWindow(sourceview, sv_changed)

        self.start_mark = sb.create_mark(None, sb.get_start_iter(),
                                         left_gravity=True)
        self.end_mark = sb.create_mark(None, sb.get_start_iter(),
                                       left_gravity=False)

        self.is_shown = False

        # A list with (widget, handler) pairs, to be filled with self.connect()
        self.signals = []

    def on_sv_changed(self, new_sv):
        sb = self.sourcebuffer
        self.hide()
        sb.delete_mark(self.start_mark)
        sb.delete_mark(self.end_mark)
        
        self.sourceview = new_sv
        self.sourcebuffer = sb = new_sv.get_buffer()
        self.start_mark = sb.create_mark(None, sb.get_start_iter(),
                                         left_gravity=True)
        self.end_mark = sb.create_mark(None, sb.get_start_iter(),
                                       left_gravity=False)
        
    def connect(self, widget, *args):
        handler = widget.connect(*args)
        self.signals.append((widget, handler))

    def disconnect_all(self):
        for widget, handler in self.signals:
            widget.disconnect(handler)
        self.signals[:] = []

    def show(self, is_auto):
        sb = self.sourcebuffer
        text = get_text(sb, sb.get_start_iter(), sb.get_end_iter())
        index = sb.get_iter_at_mark(sb.get_insert()).get_offset()
        hp = HyperParser(text, index, self.INDENT_WIDTH)

        # This is used to write "return and_maybe_beep()".
        def and_maybe_beep():
            if not is_auto:
                beep()
            return None

        opener, closer = hp.get_surrounding_brackets('(')
        if not opener:
            return and_maybe_beep()
        if not closer:
            closer = len(text)
        hp.set_index(opener)
        expr = hp.get_expression()
        if not expr or (is_auto and expr.find('(') != -1):
            return and_maybe_beep()
        arg_text = self.get_func_doc(expr)

        if not arg_text:
            return and_maybe_beep()

        sb.move_mark(self.start_mark, sb.get_iter_at_offset(opener+1))
        sb.move_mark(self.end_mark, sb.get_iter_at_offset(closer))

        self.hide()

        x, y = self.get_position()
        self.ctwindow.show(arg_text, x, y)

        self.connect(sb, 'mark-set', self.on_mark_set)
        self.connect(sb, 'insert-text', self.on_insert_text)
        self.connect(sb, 'delete-range', self.on_delete_range)
        self.connect(self.sourceview, 'focus-out-event', self.on_focus_out)
        self.connect(self.window_main, 'configure-event', self.on_configure)

        self.is_shown = True

    def get_position(self):
        sv = self.sourceview
        sb = self.sourcebuffer

        insert_iter = sb.get_iter_at_mark(sb.get_insert())
        start_iter = sb.get_iter_at_mark(self.start_mark)
        start_iter.backward_chars(1)

        if insert_iter.get_line() == start_iter.get_line():
            it = start_iter
        else:
            it = insert_iter.copy()
            it.set_line_index(0)
        rect = sv.get_iter_location(it)
        x, y = rect.x, rect.y + rect.height
        x, y = sv.buffer_to_window_coords(gtk.TEXT_WINDOW_WIDGET, x, y)
        y = max(y, 0)
        sv_x, sv_y = sv.get_window(gtk.TEXT_WINDOW_WIDGET).get_origin()
        x += sv_x; y += sv_y

        return x, y
    
    def place_window(self):
        if not self.is_shown:
            # Was called as a callback, and window was already closed.
            return False
            
        x, y = self.get_position()
        self.ctwindow.move_perhaps(x, y)

        # Called by idle_add, don't call again.
        return False

    def on_mark_set(self, sb, it, mark):
        if mark is sb.get_insert():
            if (it.compare(sb.get_iter_at_mark(self.start_mark)) < 0
                or it.compare(sb.get_iter_at_mark(self.end_mark)) > 0):
                self.hide()
            else:
                idle_add(self.place_window)

    def on_insert_text(self, sb, it, text, _length):
        if ('(' in text
            or ')' in text
            or it.compare(sb.get_iter_at_mark(self.start_mark)) < 0
            or it.compare(sb.get_iter_at_mark(self.end_mark)) > 0):
            self.hide()
        else:
            idle_add(self.place_window)

    def on_delete_range(self, sb, start, end):
        text = get_text(sb, start, end)
        if ('(' in text
            or ')' in text
            or start.compare(sb.get_iter_at_mark(self.start_mark)) < 0
            or end.compare(sb.get_iter_at_mark(self.end_mark)) > 0):
            self.hide()
        else:
            idle_add(self.place_window)

    def on_focus_out(self, _widget, _event):
        self.hide()
    
    def on_configure(self, _widget, _event):
        self.hide()

    def hide(self):
        if not self.is_shown:
            return
        
        self.disconnect_all()
        self.ctwindow.hide()
        self.is_shown = False

