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

__all__ = ['split_to_singles']

import tokenize
import itertools

class ReadLiner(object):
    """
    Perform readline over a string.
    After finishing, line_offsets contains the offset in the string for each
    line. Each line, except for the last one, ends with a '\n'. The last line
    doesn't end with a '\n'. So the number of lines is the number of '\n' chars
    in the string plus 1.
    """
    def __init__(self, s):
        self.s = s
        self.line_offsets = [0]
        self.finished = False

    def __call__(self):
        if self.finished:
            return ''
        s = self.s
        line_offsets = self.line_offsets
        next_offset = s.find('\n', line_offsets[-1])
        if next_offset == -1:
            self.finished = True
            return s[line_offsets[-1]:]
        else:
            line_offsets.append(next_offset+1)
            return s[line_offsets[-2]:line_offsets[-1]]

class TeeIter(object):
    """Wrap an iterable to add a tee() method which tees."""
    def __init__(self, iterable):
        self._it = iterable
    
    def __iter__(self):
        return self
    
    def next(self):
        return self._it.next()
    
    def tee(self):
        self._it, r = itertools.tee(self._it)
        return r

def split_to_singles(source):
    """Get a source string, and split it into several strings,
    each one a "single block" which can be compiled in the "single" mode.
    Every string which is not the last one ends with a '\n', so to convert
    a line number of a sub-string to a line number of the big string, add
    the number of '\n' chars in the preceding strings.
    """
    readline = ReadLiner(source)
    first_lines = [0] # Indices, 0-based, of the rows which start a new single.
    cur_indent_level = 0
    had_decorator = False
    
    # What this does is pretty simple: We split on every NEWLINE token which
    # is on indentation level 0 and is not followed by "else", "except" or
    # "finally" (in that case it should be kept with the previous "single").
    # Since we get the tokens one by one, and INDENT and DEDENT tokens come
    # *after* the NEWLINE token, we need a bit of care, so we peek at tokens
    # after the NEWLINE token to decide what to do.
    
    tokens_iter = TeeIter(
        itertools.ifilter(lambda x: x[0] not in (tokenize.COMMENT, tokenize.NL),
                          tokenize.generate_tokens(readline)))
    try:
        for typ, s, (srow, _scol), (_erow, _rcol), line in tokens_iter:
            if typ == tokenize.NEWLINE:
                for typ2, s2, (_srow2, _scol2), (_erow2, _rcol2), _line2 \
                    in tokens_iter.tee():
                    if typ2 == tokenize.INDENT:
                        cur_indent_level += 1
                    elif typ2 == tokenize.DEDENT:
                        cur_indent_level -= 1
                    else:
                        break
                else:
                    raise AssertionError("Should have received an ENDMARKER")
                # Now we have the first token after INDENT/DEDENT ones.
                if (cur_indent_level == 0
                    and (typ2 != tokenize.ENDMARKER
                         and not (typ2 == tokenize.NAME
                                  and s2 in ('else', 'except', 'finally')))):
                    if not had_decorator:
                        first_lines.append(srow)
                    else:
                        had_decorator = False

            elif s == '@' and cur_indent_level == 0:
                # Skip next first-line
                had_decorator = True
                        
                        
    except tokenize.TokenError:
        # EOF in the middle, it's a syntax error anyway.
        pass
        
    line_offsets = readline.line_offsets
    r = []
    for i, line in enumerate(first_lines):
        if i != len(first_lines)-1:
            r.append(source[line_offsets[line]:line_offsets[first_lines[i+1]]])
        else:
            r.append(source[line_offsets[line]:])
    return r

tests = [
"""
a = 3
""","""
a = 3
b = 5
""","""
if 1:
    1
""","""
if 1:
    2
else:
    3
""","""
if 1:
    1
if 1:
    2
else:
    3
# comment
""","""
try:
    1/0
except:
    print 'oops'
""","""
def f():
    a = 3
    def g():
        a = 4
f()
""","""
def f():
    a = 3
    def g():
        a = 4
f()
# comment
""","""
try:
    1
finally:
    2
""","""
a=3
if 1:
# comment
    2
    # comment
# comment
else:
    3
""","""
@dec

def f():
    pass
""","""
if 1:
    pass
    
@dec

def f():
    pass
""","""
class Class:
    @dec
    def method():
        pass

def f():
    pass
"""
]

def test():
    # This should raise a SyntaxError if splitting wasn't right.
    for t in tests:
        singles = split_to_singles(t)
        for s in singles:
            compile(s, "fn", "single")
    print "Test was successful"