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

"""
An ugly hack to hide the console window associated with the current process.
See http://support.microsoft.com/kb/124103
"""

__all__ = ['hide_console_window']

import time
import ctypes
kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

def hide_console_window():
    BUFSIZE = 1024
    buf = ctypes.create_string_buffer('', BUFSIZE)

    # Get current title
    length = kernel32.GetConsoleTitleA(buf, BUFSIZE)
    title = buf.raw[:length]

    # Change title to a unique string
    temp_title = '%s/%s' % (kernel32.GetCurrentProcessId(),
                            kernel32.GetTickCount())
    kernel32.SetConsoleTitleA(temp_title)
    time.sleep(.04)

    # Get window handle
    handle = user32.FindWindowA(None, temp_title)

    # Get current title, to make sure that we got the right handle
    length = user32.GetWindowTextA(handle, buf, BUFSIZE)
    cur_title = buf.raw[:length]

    # Restore title
    kernel32.SetConsoleTitleA(title)
    
    if cur_title == temp_title:
        # We got the correct handle, so hide the window.
        SW_HIDE = 0
        user32.ShowWindow(handle, SW_HIDE)
        
