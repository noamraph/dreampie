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
