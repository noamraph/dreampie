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


# dreampie.pyw - run DreamPie without a console window on win32.

# This is an ugly hack which allows us to run DreamPie on windows without
# an ugly black console window.
# The story is this:
# DreamPie subprocess must have a console, to be able to communicate with
# its parent.
# The console must be the same console as the parent's, so that the parent
# will be able to send Ctrl+C events to the subprocess.
# We usually don't want to see that console.
#
# So, what we do is this. If you run dreampie.pyw, it means that you don't
# want to see the console window. This scripts starts dreampie.py with a new
# console window, and adds the parameter 'hideconsole' so that it hides
# its console.
#
# Yuck.

import sys
import subprocess

CREATE_NEW_CONSOLE = 0x10

python_executable = sys.executable
if python_executable.lower().endswith('pythonw.exe'):
    # Remove the 'w' from 'pythonw.exe'.
    # Assume that there is python.exe in the same directory as pythonw.exe
    python_executable = python_executable[:-5] + python_executable[-4:]

# Remove the '.pyw' from 'dreampie.pyw'
assert __file__.endswith('.pyw')
dreampie_executable = __file__[:-4]

retcode = subprocess.call([python_executable, dreampie_executable,
                           'hide-console-window'],
                          creationflags=CREATE_NEW_CONSOLE)
sys.exit(retcode)
