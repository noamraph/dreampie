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

__all__ = ['Output']

import re
from StringIO import StringIO

from .tags import OUTPUT
from .common import get_text

# This RE is used to remove chars that won't be displayed from the data string.
remove_cr_re = re.compile(r'\n[^\n]*\r')
# Match ANSI escapes. See http://en.wikipedia.org/wiki/ANSI_escape_code
ansi_escape_re = re.compile(r'\x1b\[[^@-~]*?[@-~]')

# Length after which to break a line with a '\r' - a character which we
# ignore when copying.
BREAK_LEN = 1600

class Output(object):
    """
    Manage writing output to the text view.
    See a long documentation string in tags.py for more information about the
    model.
    """
    def __init__(self, textview):
        self.textview = textview
        self.textbuffer = tb = textview.get_buffer()

        # A mark where new output should be written
        self.mark = tb.create_mark(None, tb.get_end_iter(), left_gravity=True)
        # If the real output doesn't end with a newline, we add "our own",
        # because we want the output section to always end with a newline.
        # This newline will be deleted if more output is written.
        # If we did, self.added_newline is True.
        self.added_newline = False
        # Was something written at all in this section?
        self.was_something_written = False
        # Does the output end with a cr? (If it does, the last line will be
        # deleted unless the next output starts with a lf)
        self.is_cr = False

    def start_new_section(self):
        tb = self.textbuffer
        it = tb.get_end_iter()
        tb.move_mark(self.mark, it)
        self.added_newline = False
        self.was_something_written = False
        self.is_cr = False

    def write(self, data, tag_names, onnewline=False, addbreaks=True):
        """
        Write data (unicode string) to the text buffer, marked with tag_names.
        (tag_names can be either a string or a list of strings)
        If onnewline is True, will add a newline if the output until now doesn't
        end with one.
        If addbreaks is True, '\r' chars will be added so that lines will be
        broken and output will not burden the textview.
        Return a TextIter pointing to the end of the written text.
        """
        tb = self.textbuffer
        
        if isinstance(tag_names, basestring):
            tag_names = [tag_names]
        
        if not data:
            return
        
        if self.added_newline:
            if onnewline:
                # If we added a newline, it means that the section didn't end
                # with a newline, so we need to add one.
                data = '\n' + data
            it = tb.get_iter_at_mark(self.mark)
            it2 = it.copy()
            it2.backward_char()
            assert get_text(tb, it2, it) == '\n'
            tb.delete(it2, it)
            self.added_newline = False

        # Keep lines if after the cr there was no data before the lf.
        # Since that's the normal Windows newline, it's very important.
        data = data.replace('\r\n', '\n')
        
        # Remove ANSI escapes
        data = ansi_escape_re.sub('', data)
        
        # Remove NULL chars
        data = data.replace('\0', '')
        
        has_trailing_cr = data.endswith('\r')
        if has_trailing_cr:
            data = data[:-1]
        
        if data.startswith('\n'):
            # Don't delete the last line if it ended with a cr but this data
            # starts with a lf.
            self.is_cr = False
            
        # Remove chars that will not be displayed from data. No crs will be left
        # after the first lf.
        data = remove_cr_re.sub('\n', data)

        cr_pos = data.rfind('\r')
        if (self.is_cr or cr_pos != -1) and self.was_something_written:
            # Delete last written line
            it = tb.get_iter_at_mark(self.mark)
            output_start = it.copy()
            output_tag = tb.get_tag_table().lookup(OUTPUT)
            output_start.backward_to_tag_toggle(output_tag)
            assert output_start.begins_tag(output_tag)
            r = it.backward_search('\n', 0, output_start)
            if r is not None:
                _before_newline, after_newline = r
            else:
                # Didn't find a newline - delete from beginning of output
                after_newline = output_start
            tb.delete(after_newline, it)

        # Remove data up to \r.
        if cr_pos != -1:
            data = data[cr_pos+1:]

        if addbreaks:
            # We DO use \r characters as linebreaks after BREAK_LEN chars, which
            # are not copied.
            f = StringIO()
    
            pos = 0
            copied_pos = 0
            col = tb.get_iter_at_mark(self.mark).get_line_offset()
            next_newline = data.find('\n', pos)
            if next_newline == -1:
                next_newline = len(data)
            while pos < len(data):
                if next_newline - pos + col > BREAK_LEN:
                    pos = pos + BREAK_LEN - col
                    f.write(data[copied_pos:pos])
                    f.write('\r')
                    copied_pos = pos
                    col = 0
                else:
                    pos = next_newline + 1
                    col = 0
                    next_newline = data.find('\n', pos)
                    if next_newline == -1:
                        next_newline = len(data)
            f.write(data[copied_pos:])
            data = f.getvalue()

        it = tb.get_iter_at_mark(self.mark)
        tb.insert_with_tags_by_name(it, data, OUTPUT, *tag_names)

        if not data.endswith('\n'):
            tb.insert_with_tags_by_name(it, '\n', OUTPUT)
            self.added_newline = True
        
        # Move mark to after the written text
        tb.move_mark(self.mark, it)

        self.is_cr = has_trailing_cr

        self.was_something_written = True
        
        return it


