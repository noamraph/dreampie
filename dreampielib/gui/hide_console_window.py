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
        
