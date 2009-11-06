#!/usr/bin/env python

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

import sys
from os.path import abspath, join, dirname
from types import ModuleType

def main():
    port = int(sys.argv[1])

    py_ver = sys.version_info[0]
    dp_dir = abspath(join(dirname(__file__), 'subp-py%d.zip' % py_ver))

    dreampielib = ModuleType('dreampielib')
    dreampielib.__path__ = [dp_dir]
    sys.modules['dreampielib'] = dreampielib

    from dreampielib.subprocess import main as subprocess_main
    subprocess_main(port)

if __name__ == '__main__':
    main()
