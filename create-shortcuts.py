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

# This script is run after the win32 installation has finished. it creates
# start menu shortcuts for the available Python installations, as found in the
# registry. 
# It can also be run by the user, to create shortcuts to another interpreter.

import sys
import os
from os.path import join, abspath, dirname, basename, exists
from optparse import OptionParser
import _winreg
import ctypes
from ctypes import c_int, c_ulong, c_char_p, c_wchar_p, c_ushort

class OPENFILENAME(ctypes.Structure):
    _fields_ = (("lStructSize", c_int),
                ("hwndOwner", c_int),
                ("hInstance", c_int),
                ("lpstrFilter", c_wchar_p),
                ("lpstrCustomFilter", c_char_p),
                ("nMaxCustFilter", c_int),
                ("nFilterIndex", c_int),
                ("lpstrFile", c_wchar_p),
                ("nMaxFile", c_int),
                ("lpstrFileTitle", c_wchar_p),
                ("nMaxFileTitle", c_int),
                ("lpstrInitialDir", c_wchar_p),
                ("lpstrTitle", c_wchar_p),
                ("flags", c_int),
                ("nFileOffset", c_ushort),
                ("nFileExtension", c_ushort),
                ("lpstrDefExt", c_char_p),
                ("lCustData", c_int),
                ("lpfnHook", c_char_p),
                ("lpTemplateName", c_char_p),
                ("pvReserved", c_char_p),
                ("dwReserved", c_int),
                ("flagsEx", c_int))

MB_YESNO = 0x4

MB_ICONQUESTION = 0x20
MB_ICONWARNING = 0x30
MB_ICONINFORMATION = 0x40

MB_DEFBUTTON2 = 0x100

IDYES = 6
IDNO = 7

from comtypes.client import CreateObject
ws = CreateObject("WScript.Shell")
from comtypes.gen import IWshRuntimeLibrary

_ = lambda s: s

def select_file_dialog():
    ofx = OPENFILENAME()
    ofx.lStructSize = ctypes.sizeof(OPENFILENAME)
    ofx.nMaxFile = 1024
    ofx.hwndOwner = 0
    ofx.lpstrTitle = "Please select the Python interpreter executable"
    opath = u"\0" * 1024
    ofx.lpstrFile = opath
    filters = ["Executables|*.exe; *.bat", "All Files|*.*"]
    ofx.lpstrFilter = unicode("\0".join([f.replace("|", "\0") for f in filters])+"\0\0")
    OFN_HIDEREADONLY = 4
    ofx.flags = OFN_HIDEREADONLY
    is_ok = ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofx))
    if is_ok:
        absPath = opath.replace(u"\0", u"")
        return absPath
    else:
        return None

def get_subkey_names(reg_key):
    index = 0
    while True:
        try:
            name = _winreg.EnumKey(reg_key, index)
        except EnvironmentError:
            break
        index += 1
        yield name

def find_python_installations():
    """
    Return a list with info about installed versions of Python.

    For each version, return a tuple with these elements:

    0   A string with the interpreter name ('Python 2.7').
    1   A string of the absolute path to the interpreter executable.
    """
    python_paths = [('Python', r'software\python\pythoncore', 'python.exe'),
                    ('IronPython', r'software\IronPython', 'ipy.exe')]
    L = []
    for reg_hive in (_winreg.HKEY_LOCAL_MACHINE,
                     _winreg.HKEY_CURRENT_USER):
        for name, path, exec_base in python_paths:
            try:
                python_key = _winreg.OpenKey(reg_hive, path)
            except EnvironmentError:
                continue
            for version_name in get_subkey_names(python_key):
                try:
                    key = _winreg.OpenKey(python_key, version_name)
                    install_path = _winreg.QueryValue(key, 'installpath')
                    pyexec = join(install_path, exec_base)
                    if os.path.exists(pyexec):
                        L.append(('%s %s' % (name, version_name), pyexec))
                except WindowsError:
                    # Probably a remain of a previous installation, and a key
                    # wasn't found.
                    pass
    return L

def create_shortcut(dp_folder, ver_name, pyexec):
    """
    Create a shortcut.
    dp_folder should be the folder where the shortcuts are created.
    The shortcut will be called "DreamPie ({ver_name})".
    pyexec is the argument to the dreampie executable - the interpreter.
    """
    shortcut_name = "DreamPie (%s).lnk" % ver_name
    shortcut_fn = join(dp_folder, shortcut_name)
    shortcut = ws.CreateShortcut(shortcut_fn).QueryInterface(IWshRuntimeLibrary.IWshShortcut)
    args = []
    if hasattr(sys, 'frozen'):
        shortcut.TargetPath = join(dirname(abspath(sys.executable)), "dreampie.exe")
    else:
        shortcut.TargetPath = sys.executable
        args.append('"%s"' % join(dirname(abspath(sys.argv[0])), "dreampie.py"))
    args.extend(['--hide-console-window', '"%s"' % pyexec])
    shortcut.WorkingDirectory = dirname(pyexec)
    shortcut.Arguments = ' '.join(args)
    shortcut.Save()

def create_self_shortcut(dp_folder):
    """
    Create a shortcut for creating shortcuts...
    """
    shortcut_name = "Add Interpreter.lnk"
    shortcut_fn = join(dp_folder, shortcut_name)
    shortcut = ws.CreateShortcut(shortcut_fn).QueryInterface(IWshRuntimeLibrary.IWshShortcut)
    args = []
    if hasattr(sys, 'frozen'):
        shortcut.TargetPath = abspath(sys.executable)
    else:
        shortcut.TargetPath = abspath(sys.executable)
        args.append('"%s"' % abspath(sys.argv[0]))
    args.append('--no-self-shortcut')
    args.append('"%s"' % dp_folder)
    shortcut.Arguments = ' '.join(args)
    shortcut.Save()

def create_shortcuts_auto(dp_folder):
    py_installs = find_python_installations()
    for version_name, pyexec in py_installs:
        create_shortcut(dp_folder, version_name, pyexec)
    return py_installs

def create_shortcut_ask(dp_folder):
    pyexec = select_file_dialog()
    if not pyexec:
        # Canceled
        return
    if pyexec.lower().endswith('w.exe'):
        pyexec = pyexec[:-len('w.exe')] + '.exe'
        if not os.path.exists(pyexec):
            ctypes.windll.user32.MessageBoxW(
                None, u"pythonw.exe would not run DreamPie, and python.exe not found. "
                "You will have to select another executable.", u"DreamPie Installation", MB_ICONWARNING)
            return
        
    ver_name = basename(dirname(pyexec))
     
    create_shortcut(dp_folder, ver_name, pyexec)

    ctypes.windll.user32.MessageBoxW(
        None, u"Shortcut created successfully.", u"DreamPie Installation", MB_ICONINFORMATION)


def main():
    usage = "%prog [--auto] [shortcut-dir]"
    description = "Create shortcuts for DreamPie"
    parser = OptionParser(usage=usage, description=description)
    parser.add_option("--no-self-shortcut", action="store_true",
                      dest="no_self_shortcut",
                      help="Don't create a shortcut to this script.")
    parser.add_option("--auto", action="store_true", dest="auto",
                      help="Don't ask the user, just automatically create "
                      "shortcuts for Python installations found in registry")

    opts, args = parser.parse_args()
    if len(args) == 0:
        dp_folder = join(ws.SpecialFolders('Programs'), 'DreamPie')
    elif len(args) == 1:
        dp_folder, = args
    else:
        parser.error("Must get at most one argument")
    if not exists(dp_folder):
        os.mkdir(dp_folder)
    if not opts.no_self_shortcut:
        create_self_shortcut(dp_folder)

    py_installs = create_shortcuts_auto(dp_folder)
    if not opts.auto:
        if len(py_installs) == 0:
            msg_start = u'No Python interpreters found in registry. '
        else:
            msg_start = (u'I found %d Python interpreter(s) in registry (%s), '
                         'and updated their shortcuts. ' % (
                len(py_installs),
                ', '.join(ver_name for ver_name, _path in py_installs)))
        msg = (msg_start + u'Do you want to manually specify another Python '
               'interpreter?')
        
        answer = ctypes.windll.user32.MessageBoxW(
            None, msg, u"DreamPie Installation", MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2)
        
        if answer == IDYES:
            create_shortcut_ask(dp_folder)

if __name__ == '__main__':
    main()