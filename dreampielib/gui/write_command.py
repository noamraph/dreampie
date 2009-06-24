__all__ = ['write_command']

import tokenize
import keyword

PROMPT = 'prompt'; COMMAND = 'command'

KEYWORD = 'keyword'; BUILTIN = 'builtin'; STRING = 'string'
NUMBER = 'number'; COMMENT = 'comment'

keywords = set(keyword.kwlist)
builtins = set(__builtins__)

def write_command(write, command):
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
