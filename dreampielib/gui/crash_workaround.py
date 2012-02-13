# Copyright 2012 Noam Yorav-Raphael
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

__all__ = ['TextViewCrashWorkaround']

import sys
import ctypes as ct

import gtk
import glib

class TextViewCrashWorkaround(object):
    """
    This class fixes the annoying crash which happens when the mouse hovers
    over a folded area which is updated - bug #525429.
    As of 2012/02, a patch to the underlying GTK bug was submitted.
    The problem is that when updating a gtk.TextView, it leaves some processing
    to be done when idle. However, if an event occurs (such as the mouse moving
    over the widget), GTK first handles the event and then processes the idle
    job. The event is handled when the textview is in inconsistent state, and
    we get a crash.
    
    The solution is to listen to the event, and let it propagate only after the
    idle job was done. To do this, we check a (semi) private field of the
    TextView instance, which has the handle of the idle callback, and process
    GTK events until is it zeroed.
    
    The place in the struct is hardcoded, but it seems that it has never changed
    in GTK+-2. Just to be on the safer side, we check - if the field doesn't
    change to zero after GTK handled the events, we print an error and don't
    try to fix again.
    """
    
    # Offset in bytes to the first_validate_idle field in the GtkTextView struct
    first_validate_idle_offset = 192
    
    def __init__(self, textview):
        if gtk.gtk_version[0] != 2:
            return
        self._wrong_offset = False
        textview.connect('event', self._on_textview_event)
    
    def _on_textview_event(self, textview, _event):
        if self._wrong_offset:
            return
        first_validate_idle = ct.c_uint.from_address(
            hash(textview)+self.first_validate_idle_offset)
        con = glib.main_context_default()
        while first_validate_idle.value != 0:
            if not con.pending():
                # No pending callbacks, and still not 0? We have the wrong offset
                self._wrong_offset = True
                print >> sys.stderr, 'Warning: wrong first_validate_idle offset'
                return
            con.iteration()
