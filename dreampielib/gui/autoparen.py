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

# Compile REs for checking if we are between 'for' and 'in'.
_for_re = re.compile(r'\bfor\b')
_in_re = re.compile(r'\bin\b')

# If after adding parens one of these strings is typed, we remove the parens.
# These are symbols (or prefixes of symbols) which don't make sense at the
# beginning of an expression, but do between two expressions - for example,
# "a and b" is fine, but "a(and b)" doesn't make sense.
undo_strings = set(x+' ' for x in 'and or is not if else for as'.split())
undo_strings.update('! % & * + / < = > ^ , ) ] }'.split())
undo_strings.add('- ') # A binary '-', not an unary '-'.
# A set of prefixes of undo_strings
prefixes = set(s[:i] for s in undo_strings for i in range(1, len(s)))

class Autoparen(object):
    """
    Add parentheses if a space was pressed after a callable-only object.
    """

    def __init__(self, sourcebuffer, sv_changed, is_callable_only, get_expects_str,
                 show_call_tip, INDENT_WIDTH):
        self.sourcebuffer = sb = sourcebuffer
        sv_changed.append(self.on_sv_changed)
        self.is_callable_only = is_callable_only
        self.get_expects_str = get_expects_str
        self.show_call_tip = show_call_tip
        self.INDENT_WIDTH = INDENT_WIDTH
        
        # We place this mark at the end of the expression we added parens to,
        # so that if the user removes the paren and presses space, we won't
        # interfere another time.
        self.mark = sb.create_mark(None, sb.get_start_iter(), left_gravity=True)
        
        # If a string in undo_strings is typed, we undo. We track changes to
        # the sourcebuffer until we are not in 'prefixes' or we are in
        # undo_strings.
        # To accomplish that, we listen for insert-text and delete-range
        # signals while we are in 'prefixes'.
        self.cur_prefix = None
        self.insert_handler = None
        self.delete_handler = None

    def on_sv_changed(self, new_sv):
        self.sourcebuffer.delete_mark(self.mark)
        self.disconnect()
        self.sourcebuffer = sb = new_sv.get_buffer()
        self.mark = sb.create_mark(None, sb.get_start_iter(), left_gravity=True)
    
    def add_parens(self):
        """
        This is called if the user pressed space on the sourceview, and
        the subprocess is not executing commands (so is_callable_only can work.)
        Should return True if event-handling should stop, or False if it should
        continue as usual.
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
        
        r = self.is_callable_only(expr)
        if r is None:
            return False
        is_callable_only, expects_str = r
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
        
        if not expects_str:
            self.cur_prefix = ''
            self.disconnect()
            self.insert_handler = sb.connect('insert-text', self.on_insert_text)
            self.delete_handler = sb.connect('delete-range', self.on_delete_range)

        self.show_call_tip()
        
        return True
    
    def disconnect(self):
        if self.insert_handler:
            self.sourcebuffer.disconnect(self.insert_handler)
            self.insert_handler = None
        if self.delete_handler:
            self.sourcebuffer.disconnect(self.delete_handler)
            self.delete_handler = None
    
    def on_insert_text(self, _textbuffer, iter, text, _length):
        sb = self.sourcebuffer
        
        if len(text) != 1:
            self.disconnect()
            return
        it = sb.get_iter_at_mark(self.mark)
        it.forward_chars(len(self.cur_prefix)+1)
        if not it.equal(iter):
            self.disconnect()
            return
        
        new_prefix = self.cur_prefix + text
        if new_prefix in prefixes:
            # We continue to wait
            self.cur_prefix = new_prefix
        elif new_prefix in undo_strings:
            # Undo adding the parens.
            # Currently we have: "obj(prefi|)"
            # ("|" is iter. The last char wasn't written yet.)
            # We want: "obj prefix".
            # (the last char will be added by the default event handler.)
            # So we delete '(' and ')' and insert ' '.
            # We must keep 'iter' validated for the default handler, so it is
            # used in all insert and delete operations.
            self.disconnect()
            it = iter.copy()
            it.forward_char()
            sb.delete(iter, it)
            iter.backward_chars(len(self.cur_prefix))
            it = iter.copy()
            it.backward_char()
            sb.delete(it, iter)
            sb.insert(iter, ' ')
            iter.forward_chars(len(self.cur_prefix))
            return
        else:
            self.disconnect()
    
    def on_delete_range(self, _textbuffer, start, end):
        sb = self.sourcebuffer
        it = sb.get_iter_at_mark(self.mark)
        it.forward_chars(len(self.cur_prefix))
        it2 = it.copy()
        it2.forward_char()
        if self.cur_prefix and it.equal(start) and it2.equal(end):
            # BS was pressed, remove a char from cur_prefix and keep watching.
            self.cur_prefix = self.cur_prefix[:-1]
        else:
            self.disconnect()