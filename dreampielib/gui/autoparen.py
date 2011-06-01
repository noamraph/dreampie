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

__all__ = ['Autoparen']

import string
from keyword import iskeyword
import re

from .hyper_parser import HyperParser
from .common import get_text

# These are all the chars that may be before the parens
LAST_CHARS = set(string.ascii_letters + string.digits + "_)]")

_for_re = re.compile(r'\bfor\b')
_in_re = re.compile(r'\bin\b')

class Autoparen(object):
    """
    Add parentheses if a space was pressed after a callable-only object.
    """

    def __init__(self, sourcebuffer, is_callable_only, get_expects_str,
                 show_call_tip, INDENT_WIDTH):
        self.sourcebuffer = sb = sourcebuffer
        self.is_callable_only = is_callable_only
        self.get_expects_str = get_expects_str
        self.show_call_tip = show_call_tip
        self.INDENT_WIDTH = INDENT_WIDTH
        
        # We place this mark at the end of the expression we added parens to,
        # so that if the user removes the paren and presses space, we won't
        # interfere another time.
        self.mark = sb.create_mark(None, sb.get_start_iter(), left_gravity=True)
        
        # If the first thing the user does after the autoparen is adding "=",
        # then he meant to write "f =" and not "f(=)". We listen for the next
        # insert, and if it's a "=", we remove the parens.
        self.insert_handler = None

    def add_parens(self):
        """
        This is called if the user pressed space on the sourceview, and
        the subprocess is not executing commands (so is_callable_only can work.)
        Should return True if event-handling should stop, or False if it should
        continue as usual.
        
        Should be called only when is_callable_only can be called safely.
        """
        sb = self.sourcebuffer
        
        # Quickly discard some cases
        insert = sb.get_iter_at_mark(sb.get_insert())
        mark_it = sb.get_iter_at_mark(self.mark)
        if mark_it.equal(insert):
            return False
        it = insert.copy()
        it.backward_char()
        if it.get_char() not in LAST_CHARS:
            return False
        it.forward_char()
        it.backward_word_start()
        if iskeyword(get_text(sb, it, insert)):
            return False
        
        text = get_text(sb, sb.get_start_iter(), sb.get_end_iter())
        index = sb.get_iter_at_mark(sb.get_insert()).get_offset()

        line = text[text.rfind('\n', 0, index)+1:index].lstrip()
        # don't add parens in import and except statements
        if line.startswith(('import ', 'from ', 'except ')):
            return False
        # don't add parens between 'for' and 'in'
        m = list(_for_re.finditer(line))
        if m:
            if not _in_re.search(line, m[-1].end()):
                return False

        hp = HyperParser(text, index, self.INDENT_WIDTH)

        if not hp.is_in_code():
            return False

        expr = hp.get_expression()
        if not expr:
            return False
        if '(' in expr:
            # Don't evaluate expressions which may contain a function call.
            return False
        
        is_callable_only, expects_str = self.is_callable_only(expr)
        if not is_callable_only:
            return False
        
        sb.move_mark(self.mark, insert)
        
        last_name = expr.rsplit('.', 1)[-1]
        sb.begin_user_action()
        if expects_str or last_name in self.get_expects_str():
            sb.insert(insert, '("")')
            insert.backward_chars(2)
        else:
            sb.insert(insert, '()')
            insert.backward_char()
        sb.place_cursor(insert)
        sb.end_user_action()
        
        self.insert_handler = sb.connect('insert-text', self.on_insert_text)

        self.show_call_tip()
        
        return True
    
    def on_insert_text(self, _textbuffer, iter, text, _length):
        """
        This is called upon the first insert after autoparen.
        """
        sb = self.sourcebuffer
        
        sb.disconnect(self.insert_handler)
        
        if text != '=':
            return
        # We should be one char after the mark
        it = sb.get_iter_at_mark(self.mark)
        iter.backward_char()
        if not it.equal(iter):
            return
        
        it2 = iter.copy()
        it2.forward_chars(3)
        sb.delete(iter, it2)
        sb.insert(iter, ' ')
        
        # The '=' will be added by the default event handler.