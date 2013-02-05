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

__all__ = ['Selection']

import gtk

from .tags import COMMAND, PROMPT
from .common import beep, get_text

class Selection(object):
    """
    Handle clipboard events.
    When something is selected, "Copy" should be enabled. When nothing is
    selected, "Interrupt" should be enabled.
    Also, "copy only commands" command.
    """
    def __init__(self, textview, sourceview, sv_changed,
                 on_is_something_selected_changed):
        self.textview = textview
        self.textbuffer = textview.get_buffer()
        self.sourceview = sourceview
        self.sourcebuffer = sourceview.get_buffer()
        sv_changed.append(self.on_sv_changed)
        self.on_is_something_selected_changed = on_is_something_selected_changed
        
        self.is_something_selected = None
        self.textbuffer.connect('mark-set', self.on_mark_set)
        self.mark_set_handler = self.sourcebuffer.connect('mark-set',
                                                          self.on_mark_set)
        self.clipboard = gtk.Clipboard()

    def on_sv_changed(self, new_sv):
        self.sourcebuffer.disconnect(self.mark_set_handler)
        self.sourceview = new_sv
        self.sourcebuffer = new_sv.get_buffer()
        self.mark_set_handler = self.sourcebuffer.connect('mark-set',
                                                          self.on_mark_set)
    
    def on_selection_changed(self, _clipboard, _event):
        is_something_selected = (self.textbuffer.get_has_selection()
                                 or self.sourcebuffer.get_has_selection())
        self.on_is_something_selected_changed(is_something_selected)

    def on_mark_set(self, _widget, _it, _mark):
        is_something_selected = (self.textbuffer.get_has_selection()
                                 or self.sourcebuffer.get_has_selection())
        if self.is_something_selected is None \
           or is_something_selected != self.is_something_selected:
            self.is_something_selected = is_something_selected
            self.on_is_something_selected_changed(is_something_selected)

    def cut(self):
        if self.sourcebuffer.get_has_selection():
            self.sourcebuffer.cut_clipboard(self.clipboard, True)
        else:
            beep()

    def copy(self):
        if self.textbuffer.get_has_selection():
            # Don't copy '\r' chars, which are newlines only used for
            # display
            tb = self.textbuffer
            sel_start, sel_end = tb.get_selection_bounds()
            text = get_text(tb, sel_start, sel_end)
            text = text.replace('\r', '')
            self.clipboard.set_text(text)
        elif self.sourcebuffer.get_has_selection():
            self.sourcebuffer.copy_clipboard(self.clipboard)
        else:
            beep()

    def commands_only(self):
        if self.sourcebuffer.get_has_selection():
            self.sourcebuffer.copy_clipboard(self.clipboard)
            return
        if not self.textbuffer.get_has_selection():
            beep()
            return
        # We need to copy the text which has the COMMAND tag, doesn't have
        # the PROMPT tag, and is selected.
        tb = self.textbuffer
        command = tb.get_tag_table().lookup(COMMAND)
        prompt = tb.get_tag_table().lookup(PROMPT)
        r = []
        it, sel_end = tb.get_selection_bounds()
        reached_end = False
        while not reached_end:
            it2 = it.copy()
            it2.forward_to_tag_toggle(None)
            if it2.compare(sel_end) >= 0:
                it2 = sel_end.copy()
                reached_end = True
            if it.has_tag(command) and not it.has_tag(prompt):
                r.append(get_text(tb, it, it2))
            it = it2
        r = ''.join(r)
        return r
    def copy_commands_only(self):
        r = self.commands_only()
        if not r:
            beep()
        else:
            self.clipboard.set_text(r)

    def save_commands_only(self, filename):
        """Save only the selected commands to the specified filename;
        if no commands are selected, beep and forget it"""

        r = self.commands_only()
        
        if not r:
            beep()
        else:
            with open(filename, "w") as f:
                f.write(r)

    def paste(self):
        if self.sourceview.is_focus():
            self.sourcebuffer.paste_clipboard(self.clipboard, None, True)
        else:
            beep()
