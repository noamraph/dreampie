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
# along with Foobar.  If not, see <http://www.gnu.org/licenses/>.

__all__ = ['write_command']
import tokenize
import keyword

from .tags import PROMPT, COMMAND

from .tags import KEYWORD, BUILTIN, STRING, NUMBER, COMMENT

keywords = set(keyword.kwlist)
builtins = set(__builtins__)

def write_command(write, command):
    """Write a command to the textview, with syntax highlighting and "...".
    """
    lines = [x+'\n' for x in command.split('\n')]
    # Remove last newline - we don't tag it with COMMAND to separate commands
    lines[-1] = lines[-1][:-1]
    tok_iter = tokenize.generate_tokens(iter(lines).next)
    highs = []
    for typ, token, (sline, scol), (eline, ecol), line in tok_iter:
        tag = None
        if typ == tokenize.NAME:
            if token in keywords:
                tag = KEYWORD
            elif token in builtins:
                tag = BUILTIN
        elif typ == tokenize.STRING:
            tag = STRING
        elif typ == tokenize.NUMBER:
            tag = NUMBER
        elif typ == tokenize.COMMENT:
            tag = COMMENT
        if tag is not None:
            highs.append((tag, sline-1, scol, eline-1, ecol))
    # Adding a terminal highlight will help us avoid end-cases
    highs.append((None, len(lines), 0, len(lines), 0))

    high_pos = 0
    cur_high = highs[0]
    in_high = False
    for lineno, line in enumerate(lines):
        if lineno != 0:
            write('... ', COMMAND, PROMPT)
        col = 0
        while col < len(line):
            if not in_high:
                if cur_high[1] == lineno:
                    if cur_high[2] > col:
                        write(line[col:cur_high[2]], COMMAND)
                        col = cur_high[2]
                    in_high = True
                else:
                    write(line[col:], COMMAND)
                    col = len(line)
            else:
                if cur_high[3] == lineno:
                    if cur_high[4] > col:
                        write(line[col:cur_high[4]], COMMAND, cur_high[0])
                        col = cur_high[4]
                    in_high = False
                    high_pos += 1
                    cur_high = highs[high_pos]
                else:
                    write(line[col:], COMMAND, cur_high[0])
                    col = len(line)
    write('\n')
