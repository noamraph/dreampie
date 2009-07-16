__all__ = ['Config']

import os
from ConfigParser import RawConfigParser
from StringIO import StringIO

from .odict import OrderedDict

default_config = """
[DreamPie]
font=Courier New 10

[Colors]
text-fg = white
text-bg = black

stdin-fg = white
stdin-bg = black
stdout-fg = #bcffff
stdout-bg = black
stderr-fg = #ff8080
stderr-bg = black
exception-fg = #ff8080
exception-bg = black
prompt-fg = #e400b6
prompt-bg = black
command-fg = white
command-bg = black
message-fg = yellow
message-bg = black

keyword-fg = #ff7700
keyword-bg = black
builtin-fg = #efcfcf
builtin-bg = black
string-fg = #00e400
string-bg = black
number-fg = #aeacff
number-bg = black
comment-fg = #c9a3a0
comment-bg = black

bracket-match-fg = white
bracket-match-bg = darkblue
"""

class Config(object):
    """
    Manage configuration.
    config.get(key) - gets a value from the loaded file.
    config.set(key, value) - stores a value, and saves.
    """
    def __init__(self):
        self.filename = os.path.join(os.path.expanduser('~'), '.dreampie')
        try:
            self.parser = RawConfigParser(dict_type=OrderedDict)
        except TypeError:
            # Python versions < 2.6 don't support dict_type
            self.parser = RawConfigParser()
        f = StringIO(default_config)
        self.parser.readfp(f)
        self.parser.read(self.filename)
        f = open(self.filename, 'w')
        self.parser.write(f)
        f.close()
    
    def get(self, key, section='DreamPie'):
        return self.parser.get(section, key)
    
    def set(self, key, value, section='DreamPie'):
        self.parser.set(section, key, value)
        f = open(self.filename, 'w')
        self.parser.write(f)
        f.close()

