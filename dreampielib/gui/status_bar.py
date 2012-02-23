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

__all__ = ['StatusBar']

try:
    from glib import timeout_add_seconds, source_remove
except ImportError:
    timeout_add_seconds = None
    # In PyGObject 2.14, it's in gobject.
    from gobject import timeout_add, source_remove

class StatusBar(object):
    """
    Add messages to the status bar which disappear when the contents is changed.
    """
    def __init__(self, sourcebuffer, sv_changed, statusbar):
        self.sourcebuffer = sourcebuffer
        sv_changed.append(self.on_sv_changed)
        self.statusbar = statusbar
        
        # id of a message displayed in the status bar to be removed when
        # the contents of the source buffer is changed
        self.sourcebuffer_status_id = None
        self.sourcebuffer_changed_handler_id = None
        
        self.timeout_handle = None

    def on_sv_changed(self, new_sv):
        if self.sourcebuffer_status_id is not None:
            self.clear_status()
        self.sourcebuffer = new_sv.get_buffer()
    
    def set_status(self, message):
        """Set a message in the status bar to be removed when the contents
        of the source buffer is changed"""
        if self.sourcebuffer_status_id is not None:
            self.clear_status()
        self.sourcebuffer_status_id = self.statusbar.push(0, message)
        self.sourcebuffer_changed_handler_id = \
            self.sourcebuffer.connect('changed', self.on_sourcebuffer_changed)
        
        if timeout_add_seconds is not None:
            timeout_add_seconds(10, self.on_timeout)
        else:
            timeout_add(10000, self.on_timeout)

    def clear_status(self):
        try:
            self.statusbar.remove_message(0, self.sourcebuffer_status_id)
        except AttributeError:
            # Support older PyGTK
            self.statusbar.remove(0, self.sourcebuffer_status_id)
        self.sourcebuffer_status_id = None
        self.sourcebuffer.disconnect(self.sourcebuffer_changed_handler_id)
        self.sourcebuffer_changed_handler_id = None
        
        if self.timeout_handle is not None:
            source_remove(self.timeout_handle)
            self.timeout_handle = None
    
    def on_sourcebuffer_changed(self, _widget):
        self.clear_status()
        return False
    
    def on_timeout(self):
        if self.sourcebuffer_status_id is not None:
            self.clear_status()
        return False
    
    
