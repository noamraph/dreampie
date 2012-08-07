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

__all__ = ['beep', 'get_text']

import sys
if sys.platform == 'win32':
    from winsound import MessageBeep as beep #@UnresolvedImport @UnusedImport
else:
    from gtk.gdk import beep #@UnusedImport @Reimport

def get_text(textbuffer, *args):
    # Unfortunately, PyGTK returns utf-8 encoded byte strings instead of unicode
    # strings. There's no point in getting the utf-8 byte string, so whenever
    # TextBuffer.get_text is used, this function should be used instead.
    return textbuffer.get_text(*args).decode('utf8')

class TimeoutError(Exception):
    pass
