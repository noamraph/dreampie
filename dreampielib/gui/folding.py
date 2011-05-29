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

all = ['Folding']

from .tags import OUTPUT, COMMAND, FOLDED, FOLD_MESSAGE
from .common import beep, get_text

# Maybe someday we'll want translations...
_ = lambda s: s

class Folding(object):
    """
    Support folding and unfolding of output and code sections.
    """
    def __init__(self, textbuffer, LINE_LEN):
        self.textbuffer = tb = textbuffer
        self.LINE_LEN = LINE_LEN
        
        # Mark the bottom-most section which was unfolded, so as not to
        # auto-fold it.
        self.last_unfolded_mark = tb.create_mark(
            'last-folded', tb.get_start_iter(), left_gravity=True)
        
        tt = self.textbuffer.get_tag_table()
        self.fold_message_tag = tt.lookup(FOLD_MESSAGE)
        self.output_tag = tt.lookup(OUTPUT)
        self.command_tag = tt.lookup(COMMAND)
        self.tags = {OUTPUT: self.output_tag, COMMAND: self.command_tag}
    
    def get_section_status(self, it):
        """
        Get an iterator of the sourcebuffer. Return a tuple:
        (typ, is_folded, start_it)
        typ: one of tags.OUTPUT, tags.COMMAND
        is_folded: boolean (is folded), or None if not folded but too short
                   to fold (1 line or less).
        start_it: An iterator pointing to the beginning of the section.
        
        If it isn't in an OUTPUT or COMMAND section, return None.
        """
        it = it.copy()
        # The iterator is in an OUTPUT section if it's either tagged with
        # OUTPUT or if it's inside a FOLD_MESSAGE which goes right after
        # the OUTPUT tagged text. The same goes for COMMAND - note that STDIN
        # is marked with both COMMAND and OUTPUT and is considered output, so
        # we check OUTPUT first.
        # A section is folded iff it's followed by a FOLD_MESSAGE.
        if it.has_tag(self.fold_message_tag):
            if not it.begins_tag(self.fold_message_tag):
                it.backward_to_tag_toggle(self.fold_message_tag)
            if it.ends_tag(self.output_tag):
                typ = OUTPUT
            elif it.ends_tag(self.command_tag):
                typ = COMMAND
            else:
                assert False, "FOLD_MESSAGE doesn't follow OUTPUT/COMMAND"
            it.backward_to_tag_toggle(self.tags[typ])
            return (typ, True, it)
        else:
            if it.has_tag(self.output_tag) or it.ends_tag(self.output_tag):
                typ = OUTPUT
                tag = self.output_tag
            elif it.has_tag(self.command_tag) or it.ends_tag(self.command_tag):
                typ = COMMAND
                tag = self.command_tag
            else:
                return None
            if not it.ends_tag(tag):
                it.forward_to_tag_toggle(tag)
            end_it = it.copy()
            is_folded = end_it.has_tag(self.fold_message_tag)
            it.backward_to_tag_toggle(tag)
            if not is_folded:
                n_lines = self._count_lines(it, end_it)
                if n_lines <= 1:
                    is_folded = None
            return (typ, is_folded, it)
    
    def _count_lines(self, start_it, end_it):
        return max(end_it.get_line()-start_it.get_line(),
                   (end_it.get_offset()-start_it.get_offset())//self.LINE_LEN)
    
    def fold(self, typ, start_it):
        """
        Get an iterator pointing to the beginning of an unfolded OUTPUT/COMMAND
        section. Fold it.
        """
        tb = self.textbuffer
        
        # Move end_it to the end of the section
        end_it = start_it.copy()
        end_it.forward_to_tag_toggle(self.tags[typ])
        n_lines = self._count_lines(start_it, end_it)
        
        # Move 'it' to the end of the first line (this is where we start hiding)
        it = start_it.copy()
        it.forward_chars(self.LINE_LEN)
        first_line = get_text(tb, start_it, it)
        newline_pos = first_line.find('\n')
        if newline_pos != -1:
            it.backward_chars(len(first_line)-newline_pos)
        
        # Hide
        tb.apply_tag_by_name(FOLDED, it, end_it)
        
        # Add message
        tb.insert_with_tags_by_name(
            end_it,
            _("[About %d more lines. Double-click to unfold]\n") % (n_lines-1),
            FOLD_MESSAGE)
    
    def unfold(self, typ, start_it):
        """
        Get an iterator pointing to the beginning of an unfolded OUTPUT/COMMAND
        section. Unfold it.
        """
        tb = self.textbuffer
        
        last_unfolded_it = tb.get_iter_at_mark(self.last_unfolded_mark)
        if start_it.compare(last_unfolded_it) > 0:
            tb.move_mark(self.last_unfolded_mark, start_it)
    
        it = start_it.copy()
        it.forward_to_tag_toggle(self.tags[typ])
        tb.remove_tag_by_name(FOLDED, start_it, it)
        
        it2 = it.copy()
        it2.forward_to_tag_toggle(self.fold_message_tag)
        assert it2.ends_tag(self.fold_message_tag)
        tb.delete(it, it2)
        
    def autofold(self, it, numlines):
        """
        Get an iterator to a recently-written output section.
        If it is folded, update the fold message and hide what was written.
        It it isn't folded, then if the number of lines exceeds numlines and
        the section wasn't manually unfolded, fold it.
        """
        tb = self.textbuffer
        
        typ, is_folded, start_it = self.get_section_status(it)
        if is_folded:
            # Just unfold and fold. We create a mark because start_iter is
            # invalidated
            start_it_mark = tb.create_mark(None, start_it, left_gravity=True)
            self.unfold(typ, start_it)
            start_it = tb.get_iter_at_mark(start_it_mark)
            tb.delete_mark(start_it_mark)
            self.fold(typ, start_it)
        else:
            last_unfolded_it = tb.get_iter_at_mark(self.last_unfolded_mark)
            if not start_it.equal(last_unfolded_it):
                end_it = start_it.copy()
                end_it.forward_to_tag_toggle(self.tags[typ])
                n_lines = self._count_lines(start_it, end_it)
                if n_lines >= numlines:
                    self.fold(typ, start_it)
    
    def get_tag(self, typ):
        """Return the gtk.TextTag for a specific typ string."""
        return self.tags[typ]
    
    def fold_last(self):
        """
        Fold last unfolded output section.
        """
        tb = self.textbuffer
        it = tb.get_end_iter()

        while True:
            r = it.backward_to_tag_toggle(self.output_tag)
            if not r:
                # Didn't find something to fold
                beep()
                break
            if it.begins_tag(self.output_tag):
                typ, is_folded, start_it = self.get_section_status(it)
                if is_folded is not None and not is_folded:
                    self.fold(typ, start_it)
                    break
                

    def unfold_last(self):
        """
        Unfold last folded output section.
        """
        tb = self.textbuffer
        it = tb.get_end_iter()
        
        while True:
            r = it.backward_to_tag_toggle(self.output_tag)
            if not r:
                # Didn't find something to fold
                beep()
                return
            if not it.begins_tag(self.output_tag):
                continue
            typ, is_folded, start_it = self.get_section_status(it)
            if is_folded:
                self.unfold(typ, start_it)
                return
