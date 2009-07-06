__all__ = ['CallTips']

from logging import debug

import gtk
from gtk import gdk

try:
    from glib import idle_add
except ImportError:
    from gobject import idle_add

from .hyper_parser import HyperParser

class CallTips(object):
    def __init__(self, sourceview, call_subp, INDENT_WIDTH):
        self.sourceview = sourceview
        self.sourcebuffer = sb = sourceview.get_buffer()
        self.call_subp = call_subp
        self.INDENT_WIDTH = INDENT_WIDTH

        self.label = None
        self.window = None

        self.start_mark = sb.create_mark(None, sb.get_start_iter(),
                                         left_gravity=True)
        self.end_mark = sb.create_mark(None, sb.get_start_iter(),
                                       left_gravity=False)

        self.is_shown = False

        # A list with (widget, handler) pairs, to be filled with self.connect()
        self.signals = []

    def connect(self, widget, *args):
        handler = widget.connect(*args)
        self.signals.append((widget, handler))

    def disconnect_all(self):
        for widget, handler in self.signals:
            widget.disconnect(handler)
        self.signals[:] = []

    def show(self, is_auto):
        sb = self.sourcebuffer
        text = sb.get_slice(sb.get_start_iter(),
                            sb.get_end_iter()).decode('utf8')
        index = sb.get_iter_at_mark(sb.get_insert()).get_offset()
        hp = HyperParser(text, index, self.INDENT_WIDTH)

        # This is used to write "return and_maybe_beep()".
        def and_maybe_beep():
            if not is_auto:
                gdk.beep()
            return None

        if not hp.is_in_code():
            return and_maybe_beep()

        sur_parens = hp.get_surrounding_brackets('(')
        if not sur_parens:
            return and_maybe_beep()
        opener, closer = sur_parens
        if not closer:
            closer = len(text)
        hp.set_index(opener)
        expr = hp.get_expression()
        if not expr or (is_auto and expr.find('(') != -1):
            return and_maybe_beep()
        arg_text = self.call_subp('get_arg_text', expr)

        if not arg_text:
            return and_maybe_beep()

        sb.move_mark(self.start_mark, sb.get_iter_at_offset(opener+1))
        sb.move_mark(self.end_mark, sb.get_iter_at_offset(closer))

        self.hide()

        self.label = gtk.Label(arg_text)
        self.label.props.xpad = 2
        self.label.props.ypad = 2
        self.window = gtk.Window(gtk.WINDOW_POPUP)
        self.window.modify_bg(0, gtk.gdk.Color('#ffffe0'))
        self.window.add(self.label)
        self.place_window()

        self.connect(sb, 'mark-set', self.on_mark_set)
        self.connect(sb, 'insert-text', self.on_insert_text)
        self.connect(sb, 'delete-range', self.on_delete_range)
        self.connect(self.sourceview, 'key-press-event', self.on_keypress)
        self.connect(self.sourceview, 'focus-out-event', self.on_focus_out)

        self.window.show_all()
        self.is_shown = True

    def place_window(self):
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
        self.window.move(x, y)

        # If called by idle_add, don't call again.
        return False

    def on_mark_set(self, sb, it, mark):
        if mark is sb.get_insert():
            if (it.compare(sb.get_iter_at_mark(self.start_mark)) < 0
                or it.compare(sb.get_iter_at_mark(self.end_mark)) > 0):
                self.hide()
            else:
                idle_add(self.place_window)

    def on_insert_text(self, sb, it, text, length):
        if ('(' in text
            or ')' in text
            or it.compare(sb.get_iter_at_mark(self.start_mark)) < 0
            or it.compare(sb.get_iter_at_mark(self.end_mark)) > 0):
            self.hide()
        else:
            idle_add(self.place_window)

    def on_delete_range(self, sb, start, end):
        text = sb.get_slice(start, end).decode('utf8')
        if ('(' in text
            or ')' in text
            or start.compare(sb.get_iter_at_mark(self.start_mark)) < 0
            or end.compare(sb.get_iter_at_mark(self.end_mark)) > 0):
            self.hide()
        else:
            idle_add(self.place_window)

    def on_keypress(self, widget, event):
        keyval_name = gdk.keyval_name(event.keyval)
        if keyval_name == 'Escape':
            self.hide()

    def on_focus_out(self, widget, event):
        self.hide()

    def hide(self):
        if not self.is_shown:
            return
        
        self.disconnect_all()
        self.window.destroy()
        self.window = None
        self.label = None

        self.is_shown = False

