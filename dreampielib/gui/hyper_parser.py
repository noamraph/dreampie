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

# This file is based on idlelib/HyperParser.py from Python 2.5.
# Copyright Python Software Foundation.

__all__ = ['HyperParser']
"""
This module defines the HyperParser class, which provides advanced parsing
abilities.
The HyperParser uses pyparse. pyparse is intended mostly to give information
on the proper indentation of code. HyperParser gives some information on the
structure of code.
"""

import string
import keyword
from . import pyparse

class HyperParser(object):

    def __init__(self, text, index, INDENT_WIDTH):
        """Initialize the HyperParser to analyze the surroundings of the given
        index.
        Index must be in the last statement.
        """
        self.text = text

        parser = pyparse.Parser(INDENT_WIDTH, INDENT_WIDTH)
        # We add the newline because pyparse requires a newline at end.
        # We add a space so that index won't be at end of line, so that
        # its status will be the same as the char before it, if should.
        parser.set_str(text+' \n')
        parser.set_lo(0)

        self.bracketing = parser.get_last_stmt_bracketing()
        # find which pairs of bracketing are openers. These always correspond
        # to a character of text.
        self.isopener = [i>0 and self.bracketing[i][1] > self.bracketing[i-1][1]
                         for i in range(len(self.bracketing))]

        self.index = None
        self.set_index(index)

    def set_index(self, index):
        """Set the index to which the functions relate. Note that it must be
        in the last statement.
        """
        self.index = index
        # find the rightmost bracket to which index belongs
        self.indexbracket = 0
        while self.indexbracket < len(self.bracketing)-1 and \
              self.bracketing[self.indexbracket+1][0] < index:
            self.indexbracket += 1
        if self.indexbracket < len(self.bracketing)-1 and \
           self.bracketing[self.indexbracket+1][0] == index and \
           not self.isopener[self.indexbracket+1]:
            self.indexbracket += 1

    def is_in_string(self):
        """Is the index given to the HyperParser is in a string?"""
        # The bracket to which we belong should be an opener.
        # If it's an opener, it has to have a character.
        return self.isopener[self.indexbracket] and \
               self.text[self.bracketing[self.indexbracket][0]] in ('"', "'")

    def is_in_code(self):
        """Is the index given to the HyperParser is in a normal code?"""
        return not self.isopener[self.indexbracket] or \
               self.text[self.bracketing[self.indexbracket][0]] not in \
                                                                ('#', '"', "'")

    def get_surrounding_brackets(self, openers='([{'):
        """If the index given to the HyperParser is surrounded by a bracket
        defined in openers (or at least has one before it), return the
        indices of the opening bracket and the closing bracket.
        If it is not surrounded by brackets, return (None, None).
        If there is no closing bracket, return (before_index, None).
        """
        bracketinglevel = self.bracketing[self.indexbracket][1]
        before = self.indexbracket
        while not self.isopener[before] or \
              self.text[self.bracketing[before][0]] not in openers or \
              self.bracketing[before][1] > bracketinglevel:
            before -= 1
            if before < 0:
                return (None, None)
            bracketinglevel = min(bracketinglevel, self.bracketing[before][1])
        after = self.indexbracket + 1
        while after < len(self.bracketing) and \
              self.bracketing[after][1] >= bracketinglevel:
            after += 1

        beforeindex = self.bracketing[before][0]
        if after >= len(self.bracketing):
            afterindex = None
        else:
            # Return the index of the closing bracket char.
            afterindex = self.bracketing[after][0] - 1

        return beforeindex, afterindex

    # This string includes all chars that may be in a white space
    _whitespace_chars = " \t\n\\"
    # This string includes all chars that may be in an identifier
    _id_chars = string.ascii_letters + string.digits + "_"
    # This string includes all chars that may be the first char of an identifier
    _id_first_chars = string.ascii_letters + "_"

    # Given a string and pos, return the number of chars in the identifier
    # which ends at pos, or 0 if there is no such one. Saved words are not
    # identifiers.
    def _eat_identifier(self, str, limit, pos):
        i = pos
        while i > limit and str[i-1] in self._id_chars:
            i -= 1
        if i < pos and (str[i] not in self._id_first_chars or \
                        keyword.iskeyword(str[i:pos])):
            i = pos
        return pos - i

    def get_expression(self):
        """Return a string with the Python expression which ends at the given
        index, which is empty if there is no real one.
        """
        if not self.is_in_code():
            raise ValueError("get_expression should only be called if index "\
                             "is inside a code.")

        text = self.text
        bracketing = self.bracketing

        brck_index = self.indexbracket
        brck_limit = bracketing[brck_index][0]
        pos = self.index

        last_identifier_pos = pos
        postdot_phase = True

        while 1:
            # Eat whitespaces, comments, and if postdot_phase is False - one dot
            while 1:
                if pos>brck_limit and text[pos-1] in self._whitespace_chars:
                    # Eat a whitespace
                    pos -= 1
                elif not postdot_phase and \
                     pos > brck_limit and text[pos-1] == '.':
                    # Eat a dot
                    pos -= 1
                    postdot_phase = True
                # The next line will fail if we are *inside* a comment, but we
                # shouldn't be.
                elif pos == brck_limit and brck_index > 0 and \
                     text[bracketing[brck_index-1][0]] == '#':
                    # Eat a comment
                    brck_index -= 2
                    brck_limit = bracketing[brck_index][0]
                    pos = bracketing[brck_index+1][0]
                else:
                    # If we didn't eat anything, quit.
                    break

            if not postdot_phase:
                # We didn't find a dot, so the expression end at the last
                # identifier pos.
                break

            ret = self._eat_identifier(text, brck_limit, pos)
            if ret:
                # There is an identifier to eat
                pos = pos - ret
                last_identifier_pos = pos
                # Now, in order to continue the search, we must find a dot.
                postdot_phase = False
                # (the loop continues now)

            elif pos == brck_limit:
                # We are at a bracketing limit. If it is a closing bracket,
                # eat the bracket, otherwise, stop the search.
                level = bracketing[brck_index][1]
                while brck_index > 0 and bracketing[brck_index-1][1] > level:
                    brck_index -= 1
                if bracketing[brck_index][0] == brck_limit:
                    # We were not at the end of a closing bracket
                    break
                pos = bracketing[brck_index][0]
                brck_index -= 1
                brck_limit = bracketing[brck_index][0]
                last_identifier_pos = pos
                if text[pos] in "([":
                    # [] and () may be used after an identifier, so we
                    # continue. postdot_phase is True, so we don't allow a dot.
                    pass
                else:
                    # We can't continue after other types of brackets
                    break

            else:
                # We've found an operator or something.
                break

        return text[last_identifier_pos:self.index]
