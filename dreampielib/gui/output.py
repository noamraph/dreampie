__all__ = ['Output']

import sys
import re
from StringIO import StringIO

from .tags import STDOUT, STDERR

remove_cr_re = re.compile(r'\n[^\n]*\r')
# Match ANSI escapes. See http://en.wikipedia.org/wiki/ANSI_escape_code
ansi_escape_re = re.compile(r'\x1b\[[^@-~]*?[@-~]')

class Output(object):
    """
    Manage writing output (stdout and stderr) to the text view.
    """
    def __init__(self, textview, LINE_LEN):
        self.textview = textview
        self.textbuffer = tb = textview.get_buffer()
        self.LINE_LEN = LINE_LEN

        self.mark = tb.create_mark(None, tb.get_end_iter(), left_gravity=True)
        self.is_cr = False

    def set_mark(self, it):
        self.textbuffer.move_mark(self.mark, it)
        self.is_cr = False

    def write(self, data, tag_name):
        tb = self.textbuffer

        # sys.stdout.encoding is transferred to the subprocess as
        # PYTHONENCODING, so that's how we should interpret its output.
        data = data.decode(sys.stdout.encoding, 'replace')

        data = ansi_escape_re.sub('', data)
        
        has_trailing_cr = data.endswith('\r')
        if has_trailing_cr:
            data = data[:-1]
            
        data = remove_cr_re.sub('\n', data)

        cr_pos = data.rfind('\r')
        if self.is_cr or cr_pos != -1:
            # Delete last written line
            it = tb.get_iter_at_mark(self.mark)
            it2 = it.copy()
            it2.set_line_offset(0)
            tb.delete(it2, it)

            # Remove data up to \r.
            if cr_pos != -1:
                data = data[cr_pos+1:]

        # We DO use \r characters as linebreaks after LINE_LEN chars, which
        # are not copied.
        f = StringIO()

        pos = 0
        copied_pos = 0
        col = tb.get_iter_at_mark(self.mark).get_line_offset()
        next_newline = data.find('\n', pos)
        if next_newline == -1:
            next_newline = len(data)
        while pos < len(data):
            if next_newline - pos + col > self.LINE_LEN:
                pos = pos + self.LINE_LEN - col
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

        it = tb.get_iter_at_mark(self.mark)
        tb.insert_with_tags_by_name(it, f.getvalue(), tag_name)
        # Move mark to after the written text
        tb.move_mark(self.mark, it)

        self.is_cr = has_trailing_cr

