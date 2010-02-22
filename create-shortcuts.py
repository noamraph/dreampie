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
# registry. If non are found, asks the user to find the Python installation.
# If an executable isn't found, it creates a shortcut to the bare dreampie.exe,
# which will show a warning that a Python executable is needed.

import sys
import os
from os.path import join, abspath, dirname, exists
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

from comtypes.client import CreateObject
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
    filters = ["Executables|*.exe", "All Files|*.*"]
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

    0   A string with major and minor version number e.g '2.4'.
    1   A string of the absolute path to the installation directory.
    """
    python_path = r'software\python\pythoncore'
    L = []
    for reg_hive in (_winreg.HKEY_LOCAL_MACHINE,
                     _winreg.HKEY_CURRENT_USER):
        try:
            python_key = _winreg.OpenKey(reg_hive, python_path)
        except EnvironmentError:
            continue
        for version_name in get_subkey_names(python_key):
            try:
                key = _winreg.OpenKey(python_key, version_name)
                install_path = _winreg.QueryValue(key, 'installpath')
                L.append((version_name, install_path))
            except WindowsError:
                # Probably a remain of a previous installation, and a key
                # wasn't found.
                pass
    return L

def create_shortcut(ws, dp_folder, ver_name, pyexec):
    """
    Create a shortcut.
    ws should be a Shell COM object.
    dp_folder should be the folder where the shortcuts are created.
    If ver_name is None, the shortcut will be "DreamPie"
    instead of "DreamPie ({ver_name})".
    If pyexec is None, will start dreampie.exe with no arguments.
    """
    if ver_name:
        shortcut_name = "DreamPie (Python %s).lnk" % ver_name
    else:
        shortcut_name = "DreamPie.lnk"
    shortcut_fn = join(dp_folder, shortcut_name)
    shortcut = ws.CreateShortcut(shortcut_fn).QueryInterface(IWshRuntimeLibrary.IWshShortcut)
    shortcut.TargetPath = abspath(join(dirname(sys.executable), "dreampie.exe"))
    args = ['--hide-console-window']
    if pyexec: 
        args.append('"%s"' % pyexec)
        shortcut.WorkingDirectory = dirname(pyexec)
    shortcut.Arguments = ' '.join(args)
    shortcut.Save()

def create_shortcuts(dp_folder):
    ws = CreateObject("WScript.Shell")
    #programs_folder = ws.SpecialFolders('Programs')
    #dp_folder = join(programs_folder, "DreamPie")
    if not exists(dp_folder):
        os.mkdir(dp_folder)
    py_installs = [(ver_name, path)
                   for ver_name, path in find_python_installations()
                   if ver_name >= '2.5'
                      and exists(join(path, 'python.exe'))]
    if py_installs:
        for version_name, install_path in py_installs:
            pyexec = join(install_path, "python.exe")
            create_shortcut(ws, dp_folder, version_name, pyexec)
    else:
        MB_YESNO=4; MB_ICONWARNING=0x30; IDYES = 6
        response = ctypes.windll.user32.MessageBoxW(
            None, u"No matching Python installations were found. Do you wish to "
            "manually find the Python interpreter program?", u"DreamPie Installation",
            MB_YESNO | MB_ICONWARNING)
        pyexec = None
        if response == IDYES:
            pyexec = select_file_dialog()
            # If canceled, pyexec will stay None
        if pyexec and pyexec.lower().endswith('pythonw.exe'):
            pyexec = pyexec[:-len('w.exe')] + '.exe'
            if not os.path.exists(pyexec):
                ctypes.windll.user32.MessageBoxW(
                    None, u"pythonw.exe would not run DreamPie, and python.exe not found. "
                    "You will have to select another executable.", u"DreamPie Installation", MB_ICONWARNING)
                pyexec = None
        if pyexec:
            create_shortcut(ws, dp_folder, None, pyexec)
        else:
            create_shortcut(ws, dp_folder, None, None)

def main():
    if len(sys.argv) != 2 or sys.argv[1] in ('-h', '--help'):
        print "Usage: %s <dreampie shortcut folder>" % sys.argv[0]
        print "This program is used internally by the DreamPie installer."
        sys.exit(1)
    dp_folder = sys.argv[1]
    create_shortcuts(dp_folder)

if __name__ == '__main__':
    main()