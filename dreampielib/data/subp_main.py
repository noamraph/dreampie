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

# This file is a script (not a module) run by the DreamPie GUI.
# It expects one argument: the port to connect to.
# It creates a package called dreampielib from subp-py2.zip or subp-py3.zip
# (which are expected to be in the directory of __file__),
# and runs dreampielib.subprocess.main(port).

# This is a hack to solve bug #527630. Python2.5 ignores the PYTHONIOENCODING
# environment variable, but we want to set the output encoding to utf-8 so that
# unicode chars will be printed. So we disable automatic loading of site.py with
# the -S flag, and call sys.setdefaultencoding before site.py has a chance of
# doing anything else.
import sys
if sys.version_info[0] < 3:
    sys.setdefaultencoding('utf-8') #@UndefinedVariable
import site
site.main()

from os.path import abspath, join, dirname

def main():
    port = int(sys.argv[1])

    py_ver = sys.version_info[0]
    lib_name = abspath(join(dirname(__file__), 'subp-py%d' % py_ver))
    
    sys.path.insert(0, lib_name)
    from dreampielib.subprocess import main as subprocess_main
    del sys.path[0]
    
    if sys.version_info[:2] == (3, 0):
        sys.stderr.write("Warning: DreamPie doesn't support Python 3.0. \n"
                         "Please upgrade to Python 3.1.\n")
    
    subprocess_main(port)

if __name__ == '__main__':
    main()
