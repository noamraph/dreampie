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

__all__ = ['CallTipWindow']

import gtk
from gtk import gdk
import pango
from gobject import TYPE_NONE

from .keyhandler import make_keyhandler_decorator, handle_keypress

N_ROWS = 4
N_COLS = 80

# A decorator for managing sourceview key handlers
keyhandlers = {}
keyhandler = make_keyhandler_decorator(keyhandlers)

class CallTipWindow(object):
    """
    This class manages the calltip window, which displays function documentation.
    The window is shown and hidden upon request.
    """
    # The window looks like this: Most of it is occupied by the text box.
    # Below we have a horizontal scroll bar, which is displayed only when
    # needed, and to the right there's a vertical scroll bar, which is always
    # displayed. Below it is a "resize grip", which lets you resize the window.
    # The window can be moved by dragging the main text area.
    
    # This looks pretty much like a ScrolledWindow, but a SW doesn't have the
    # resize grip, So we layout the widgets by ourselves, and handle scrolling.
    
    # We implement our own resize grip - for some reason, the resize grip of
    # a status bar doesn't work on popup windows.
    
    def __init__(self, sourceview, sv_changed):
        self.sourceview = sourceview
        sv_changed.append(self.on_sv_changed)
        
        # Widgets
        self.textview = tv = gtk.TextView()
        self.hscrollbar = hs = gtk.HScrollbar()
        self.vscrollbar = vs = gtk.VScrollbar()
        self.resizegrip = rg = gtk.EventBox()
        self.vbox1 = vb1 = gtk.VBox()
        self.vbox2 = vb2 = gtk.VBox()
        self.hbox = hb = gtk.HBox()
        self.window = win = gtk.Window(gtk.WINDOW_POPUP)
        
        self.char_width, self.char_height = self.get_char_size(tv)
        
        # Dragging vars
        self.is_dragging = None
        self.drag_x = None
        self.drag_y = None
        self.drag_left = None
        self.drag_top = None
        self.was_dragged = None
        
        # Resizing vars
        self.is_resizing = None
        self.resize_x = None
        self.resize_y = None
        self.resize_width = None
        self.resize_height = None
        
        self.was_displayed = False
        
        # Initialization
        
        style = gtk.rc_get_style_by_paths(
            tv.get_settings(), 'gtk-tooltip', 'gtk-tooltip', TYPE_NONE)
        tv.modify_text(gtk.STATE_NORMAL, style.fg[gtk.STATE_NORMAL])
        tv.modify_base(gtk.STATE_NORMAL, style.bg[gtk.STATE_NORMAL])
        tv.set_size_request(0,0)
        tv.props.editable = False
        
        tv.connect('event', self.on_textview_event)
        
        tv.set_scroll_adjustments(hs.props.adjustment, vs.props.adjustment)
        
        tv.connect('scroll-event', self.on_textview_scroll)
        
        hs.props.adjustment.connect('changed', self.on_hadj_changed)

        rg.add_events(gdk.BUTTON_PRESS_MASK
                      | gdk.BUTTON_MOTION_MASK
                      | gdk.BUTTON_RELEASE_MASK
                      | gdk.EXPOSURE_MASK)
        
        rg.connect('event', self.on_resizegrip_event)
        rg.set_size_request(vs.size_request()[0], vs.size_request()[0])
        
        vb1.pack_start(tv, True, True)
        vb1.pack_start(hs, False, False)
        vb2.pack_start(vs, True, True)
        vb2.pack_end(rg, False, False)
        hb.pack_start(vb1, True, True)
        hb.pack_start(vb2, False, False)
        win.add(hb)
        
        # Make all widgets except the window visible, so that a simple "show"
        # will suffice to show the window
        hb.show_all()
        
        # We define this handler here so that it will be defined before
        # the default key-press handler, and so will have higher priority.
        self.keypress_handler = self.sourceview.connect(
            'key-press-event', self.on_keypress)
        self.sourceview.handler_block(self.keypress_handler)
        self.keypress_handler_blocked = True

    def on_sv_changed(self, new_sv):
        self.hide()
        self.sourceview.disconnect(self.keypress_handler)
        self.sourceview = new_sv
        self.keypress_handler = self.sourceview.connect(
            'key-press-event', self.on_keypress)
        self.sourceview.handler_block(self.keypress_handler)

    @staticmethod
    def get_char_size(textview):
        """
        Get width, height of a character in pixels.
        """
        tv = textview
        context = tv.get_pango_context()
        metrics = context.get_metrics(tv.style.font_desc,
                                      context.get_language())
        width = pango.PIXELS(metrics.get_approximate_digit_width())
        height = pango.PIXELS(metrics.get_ascent() + metrics.get_descent())
        return width, height
    
    def on_textview_scroll(self, _widget, event):
        adj = self.vscrollbar.props.adjustment
        # Scrolling: 3 lines
        step = self.char_height * 3
        
        if event.direction == gtk.gdk.SCROLL_UP:
            adj.props.value -= step
        elif event.direction == gtk.gdk.SCROLL_DOWN:
            adj.props.value = min(adj.props.value+step, 
                                  adj.props.upper-adj.props.page_size)

    def on_hadj_changed(self, adj):
        self.hscrollbar.props.visible = (adj.props.page_size < adj.props.upper)

    def on_textview_event(self, _widget, event):
        if event.type == gdk.BUTTON_PRESS:
            self.is_dragging = True
            self.was_dragged = True
            self.drag_x = event.x_root
            self.drag_y = event.y_root
            self.drag_left, self.drag_top = self.window.get_position()
            return True
        elif event.type == gdk.MOTION_NOTIFY and self.is_dragging:
            left = self.drag_left + event.x_root - self.drag_x
            top = self.drag_top + event.y_root - self.drag_y
            self.window.move(int(left), int(top))
            return True
        elif event.type == gdk.BUTTON_RELEASE:
            self.is_dragging = False

    def on_resizegrip_event(self, _widget, event):
        if event.type == gdk.BUTTON_PRESS:
            self.resize_x = event.x_root
            self.resize_y = event.y_root
            self.resize_width, self.resize_height = self.window.get_size()
            return True
        elif event.type == gdk.MOTION_NOTIFY:
            width = max(0, self.resize_width + event.x_root - self.resize_x)
            height = max(0, self.resize_height + event.y_root - self.resize_y)
            self.window.resize(int(width), int(height))
            return True
        elif event.type == gdk.EXPOSE:
            rg = self.resizegrip
            win = rg.window
            _x, _y, width, height, _depth = win.get_geometry()
            rg.get_style().paint_resize_grip(
                win, gtk.STATE_NORMAL, None, rg, None, 
                gdk.WINDOW_EDGE_SOUTH_EAST, 0, 0, width, height)
            return True
    
    @keyhandler('Up', 0)
    def on_up(self):
        adj = self.vscrollbar.props.adjustment
        adj.props.value -= self.char_height
        return True

    @keyhandler('Down', 0)
    def on_down(self):
        adj = self.vscrollbar.props.adjustment
        adj.props.value = min(adj.props.value + self.char_height, 
                              adj.props.upper - adj.props.page_size)
        return True

    @keyhandler('Page_Up', 0)
    def on_page_up(self):
        self.textview.emit('move-viewport', gtk.SCROLL_PAGES, -1)
        return True
        
    @keyhandler('Page_Down', 0)
    def on_page_down(self):
        self.textview.emit('move-viewport', gtk.SCROLL_PAGES, 1)
        return True

    @keyhandler('Escape', 0)
    def on_esc(self):
        self.hide()
        # Don't return True - other things may be escaped too.

    def on_keypress(self, _widget, event):
        return handle_keypress(self, event, keyhandlers)

    def show(self, text, x, y):
        """
        Show the window with the given text, its top-left corner at x-y.
        Decide on initial size.
        """
        # The initial size is the minimum of:
        # * N_COLS*N_ROWS
        # * Whatever fits into the screen
        # * The actual content
        
        tv = self.textview
        vs = self.vscrollbar
        win = self.window
        
        text = text.replace('\0', '') # Fixes bug #611513
        
        win.hide()
        tv.get_buffer().set_text(text)
        
        f_width = self.char_width * N_COLS
        f_height = self.char_height * N_ROWS
        
        s_width = gdk.screen_width() - x
        s_height = gdk.screen_height() - y
        
        # Get the size of the contents
        layout = tv.create_pango_layout(text)
        p_width, p_height = layout.get_size()
        c_width = pango.PIXELS(p_width)
        c_height = pango.PIXELS(p_height)
        del layout
        
        add_width = vs.size_request()[0] + 5
        width = int(min(f_width, s_width, c_width) + add_width)
        height = int(min(f_height, s_height, c_height))
        
        # Don't show the vertical scrollbar if the height is short enough.
        vs.props.visible = (height > vs.size_request()[1])
        
        win.resize(width, height)
        
        win.move(x, y)
        
        self.hscrollbar.props.adjustment.props.value = 0
        self.vscrollbar.props.adjustment.props.value = 0
        
        self.sourceview.handler_unblock(self.keypress_handler)
        self.keypress_handler_blocked = False

        win.show()
        
        # This has to be done after the textview was displayed
        if not self.was_displayed:
            self.was_displayed = True
            hand = gdk.Cursor(gdk.HAND1)
            tv.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(hand)
            br_corner = gdk.Cursor(gdk.BOTTOM_RIGHT_CORNER)
            self.resizegrip.window.set_cursor(br_corner)
    
    def hide(self):
        self.window.hide()

        if not self.keypress_handler_blocked:
            self.sourceview.handler_block(self.keypress_handler)
            self.keypress_handler_blocked = True

        self.is_dragging = False
        self.is_resizing = False
        self.was_dragged = False
    
    def move_perhaps(self, x, y):
        """
        Move the window to x-y, unless it was already manually dragged.
        """
        if not self.was_dragged:
            self.window.move(x, y)