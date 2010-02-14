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

__all__ = ['VAdjToBottom']

try:
    from glib import idle_add
except ImportError:
    # In PyGObject 2.14, it's in gobject.
    from gobject import idle_add

class VAdjToBottom(object):
    """
    Scroll automatically to the bottom of the VAdj if the height changes
    and it was at bottom
    """
    # The way this works is a little bit tricky, so here is the reasoning:
    # self.user_wants_bottom records whether the user wants to see the bottom,
    # so we should automatically scroll if more text was added. It is changed
    # by self.on_value_changed; It assumes that if the scrollbar is at the
    # bottom then that's what the user wants, but if it isn't at the bottom,
    # it means that the user doesn't want to see the bottom only if the
    # scrollbar was scrolled upwards - otherwise it's just us trying to catch
    # up.
    # self.on_changed monitors changes in the textview. If the scrollbar isn't
    # at the bottom (as the result of changes) but self.user_wants_bottom is
    # True, it schedules a call to scroll_to_bottom when idle. We don't call
    # scroll_to_bottom immediately because many times the are a few changes
    # before display, and scrolling before they are finished will cause
    # redisplay after every stage, which will be slow.
    def __init__(self, vadj):
        self.vadj = vadj
        self.last_value = self.vadj.value
        self.user_wants_bottom = True
        self.is_scroll_scheduled = False
        
        vadj.connect('changed', self.on_changed)
        vadj.connect('value-changed', self.on_value_changed)

    def is_at_bottom(self):
        return self.vadj.value + self.vadj.page_size - self.vadj.upper == 0

    def scroll_to_bottom(self):
        # Callback function
        try:
            self.is_scroll_scheduled = False
            self.vadj.set_value(self.vadj.upper - self.vadj.page_size)
        finally:
            # Avoid future calls
            return False

    def on_changed(self, _widget):
        if (not self.is_scroll_scheduled
            and self.user_wants_bottom
            and not self.is_at_bottom()):
            idle_add(self.scroll_to_bottom)
            self.is_scroll_scheduled = True

    def on_value_changed(self, _widget):
        is_at_bottom = self.is_at_bottom()
        if is_at_bottom:
            self.user_wants_bottom = True
        else:
            if self.vadj.value < self.last_value:
                self.user_wants_bottom = False
        self.last_value = self.vadj.value
