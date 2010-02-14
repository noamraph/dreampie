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

__all__ = ['write_command']
import tokenize
import keyword

from .tags import PROMPT, COMMAND, COMMAND_DEFS, COMMAND_SEP

from .tags import KEYWORD, BUILTIN, STRING, NUMBER, COMMENT

keywords = set(keyword.kwlist)
builtins = set(__builtins__)

def write_command(write, command):
    """Write a command to the textview, with syntax highlighting and "...".
    """
    lines = [x+'\n' for x in command.split('\n')]
    # Remove last newline - we don't tag it with COMMAND to separate commands
    lines[-1] = lines[-1][:-1]
    defs_lines = get_defs_lines(lines)
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

    def my_write(s, is_defs, *tags):
        if not is_defs:
            write(s, *tags)
        else:
            write(s, COMMAND_DEFS, *tags)

    high_pos = 0
    cur_high = highs[0]
    in_high = False
    for lineno, line in enumerate(lines):
        is_defs = defs_lines[lineno]
            
        if lineno != 0:
            my_write('... ', is_defs, COMMAND, PROMPT)
        col = 0
        while col < len(line):
            if not in_high:
                if cur_high[1] == lineno:
                    if cur_high[2] > col:
                        my_write(line[col:cur_high[2]], is_defs, COMMAND)
                        col = cur_high[2]
                    in_high = True
                else:
                    my_write(line[col:], is_defs, COMMAND)
                    col = len(line)
            else:
                if cur_high[3] == lineno:
                    if cur_high[4] > col:
                        my_write(line[col:cur_high[4]],
                                 is_defs, COMMAND, cur_high[0])
                        col = cur_high[4]
                    in_high = False
                    high_pos += 1
                    cur_high = highs[high_pos]
                else:
                    my_write(line[col:], is_defs, COMMAND, cur_high[0])
                    col = len(line)
    write('\n', COMMAND)
    write('\r', COMMAND_SEP)

def get_defs_lines(lines):
    """
    Get a list of lines - strings with Python code.
    Return a list of booleans - whether a line should be hidden when hide-defs
    is True, because it's a part of a function or class definitions.
    """
    # return value
    defs_lines = [False for _line in lines]
    # Last line with a 'def' or 'class' NAME
    last_def_line = -2
    # Indentation depth - when reaches 0, we are back in a non-filtered area.
    cur_depth = 0
    # First line of current filtered area
    first_filtered_line = None
    
    tok_iter = tokenize.generate_tokens(iter(lines).next)
    for typ, token, (sline, _scol), (_eline, _ecol), _line in tok_iter:
        if cur_depth > 0:
            if typ == tokenize.INDENT:
                cur_depth += 1
            elif typ == tokenize.DEDENT:
                cur_depth -= 1
                if cur_depth == 0:
                    for i in range(first_filtered_line, sline-1):
                        defs_lines[i] = True
                    first_filtered_line = None
        else:
            if typ == tokenize.NAME and token in ('def', 'class'):
                last_def_line = sline
            elif typ == tokenize.INDENT and sline == last_def_line + 1:
                cur_depth = 1
                first_filtered_line = sline-1
    
    return defs_lines
