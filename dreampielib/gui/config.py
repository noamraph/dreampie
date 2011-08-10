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

__all__ = ['Config']

import sys
import os
from ConfigParser import RawConfigParser
from StringIO import StringIO

from .odict import OrderedDict

# We use expects-str-2, because expects-str had a different format (uses repr)
# in DreamPie 1.1

default_config = """
[DreamPie]
show-getting-started = True
font=Courier New 10
current-theme = Dark
pprint = True
use-reshist = True
reshist-size = 30
autofold = True
autofold-numlines = 30
viewer = ''
init-code = ''
autoparen = True
expects-str-2 = execfile chdir open run runeval
vertical-layout = True
ask-on-quit = True
matplotlib-ia-switch = False
matplotlib-ia-warn = True

recall-1-char-commands = False
hide-defs = False
leave-code = False

[Dark theme]
is-active = True

default-fg = white
default-bg = black

stdin-fg = white
stdin-bg = black
stdout-fg = #bcffff
stdout-bg = black
stderr-fg = #ff8080
stderr-bg = black
result-ind-fg = blue
result-ind-bg = black
result-fg = #bcffff
result-bg = black
exception-fg = #ff8080
exception-bg = black
prompt-fg = #e400b6
prompt-bg = black
message-fg = yellow
message-bg = black
fold-message-fg = #a7a7a7
fold-message-bg = #003b6c

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
bracket-1-fg = #abffab
bracket-1-bg = black
bracket-2-fg = #dfabff
bracket-2-bg = black
bracket-3-fg = #ffabab
bracket-3-bg = black
error-fg = white
error-bg = red

stdin-fg-set = False
stdin-bg-set = False
stdout-fg-set = True
stdout-bg-set = False
stderr-fg-set = True
stderr-bg-set = False
result-ind-fg-set = True
result-ind-bg-set = False
result-fg-set = True
result-bg-set = False
exception-fg-set = True
exception-bg-set = False
prompt-fg-set = True
prompt-bg-set = False
message-fg-set = True
message-bg-set = False
fold-message-fg-set = True
fold-message-bg-set = True

keyword-fg-set = True
keyword-bg-set = False
builtin-fg-set = True
builtin-bg-set = False
string-fg-set = True
string-bg-set = False
number-fg-set = True
number-bg-set = False
comment-fg-set = True
comment-bg-set = False

bracket-match-fg-set = False
bracket-match-bg-set = True
bracket-1-fg-set = True
bracket-1-bg-set = False
bracket-2-fg-set = True
bracket-2-bg-set = False
bracket-3-fg-set = True
bracket-3-bg-set = False
error-fg-set = False
error-bg-set = True

[Light theme]
is-active = True

default-fg = black
default-bg = white

stdin-fg = #770000
stdin-bg = white
stdout-fg = blue
stdout-bg = white
stderr-fg = red
stderr-bg = white
result-ind-fg = #808080
result-ind-bg = white
result-fg = blue
result-bg = white
exception-fg = red
exception-bg = white
prompt-fg = #770000
prompt-bg = white
message-fg = #008000
message-bg = white
fold-message-fg = #404040
fold-message-bg = #b2ddff

keyword-fg = #ff7700
keyword-bg = white
builtin-fg = #0000ff
builtin-bg = white
string-fg = #00aa00
string-bg = white
number-fg = blue
number-bg = white
comment-fg = #dd0000
comment-bg = white

bracket-match-fg = black
bracket-match-bg = lightblue
bracket-1-fg = #005400
bracket-1-bg = white
bracket-2-fg = #9400f0
bracket-2-bg = white
bracket-3-fg = brown
bracket-3-bg = #a50000
error-fg = black
error-bg = red

stdin-fg-set = False
stdin-bg-set = False
stdout-fg-set = True
stdout-bg-set = False
stderr-fg-set = True
stderr-bg-set = False
result-ind-fg-set = True
result-ind-bg-set = False
result-fg-set = True
result-bg-set = False
exception-fg-set = True
exception-bg-set = False
prompt-fg-set = True
prompt-bg-set = False
message-fg-set = True
message-bg-set = False
fold-message-fg-set = True
fold-message-bg-set = True

keyword-fg-set = True
keyword-bg-set = False
builtin-fg-set = True
builtin-bg-set = False
string-fg-set = True
string-bg-set = False
number-fg-set = True
number-bg-set = False
comment-fg-set = True
comment-bg-set = False

bracket-match-fg-set = False
bracket-match-bg-set = True
bracket-1-fg-set = True
bracket-1-bg-set = False
bracket-2-fg-set = True
bracket-2-bg-set = False
bracket-3-fg-set = True
bracket-3-bg-set = False
error-fg-set = False
error-bg-set = True

"""

def get_config_fn():
    if sys.platform != 'win32':
        return os.path.expanduser('~/.dreampie')
    else:
        # On win32, expanduser doesn't work when the path includes unicode
        # chars.
        import ctypes
        MAX_PATH = 255
        nFolder = 26 # CSIDL_APPDATA
        flags = 0
        buf = ctypes.create_unicode_buffer(MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, nFolder, None, flags, buf)
        return os.path.join(buf.value, 'DreamPie')

class Config(object):
    """
    Manage configuration - a simple wrapper around RawConfigParser.
    Upon initialization, the loaded file is updated with the default values.
    config.save() will save the current state.
    """
    def __init__(self):
        self.filename = get_config_fn()
        try:
            self.parser = RawConfigParser(dict_type=OrderedDict)
        except TypeError:
            # Python versions < 2.6 don't support dict_type
            self.parser = RawConfigParser()
        f = StringIO(default_config)
        self.parser.readfp(f)
        self.parser.read(self.filename)
        self.save()
    
    def get(self, key, section='DreamPie'):
        return self.parser.get(section, key)
    
    def get_bool(self, key, section='DreamPie'):
        return self.parser.getboolean(section, key)
    
    def get_int(self, key, section='DreamPie'):
        return self.parser.getint(section, key)
    
    def set(self, key, value, section='DreamPie'):
        self.parser.set(section, key, value)
    
    def set_bool(self, key, value, section='DreamPie'):
        value_str = 'True' if value else 'False'
        self.set(key, value_str, section)
    
    def set_int(self, key, value, section='DreamPie'):
        if value != int(value):
            raise ValueError("Expected an int, got %r" % value)
        self.set(key, '%d' % value, section)
    
    def sections(self):
        return self.parser.sections()

    def has_section(self, section):
        return self.parser.has_section(section)

    def add_section(self, section):
        return self.parser.add_section(section)

    def remove_section(self, section):
        return self.parser.remove_section(section)

    def save(self):
        f = open(self.filename, 'w')
        self.parser.write(f)
        f.close()

