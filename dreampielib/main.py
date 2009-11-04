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

import sys

def main(dreampie_script):
    """
    This is the main function, called by the 'dreampie' script. What it does is:
    * If the first argument is 'subprocess':
        * If we are running under python 3, modify dreampielib.__path__ to use
          dreampielib.py3k.
        * Run dreampielib.subprocess.main()
    * Otherwise:
        * Run dreampielib.gui.main(dreampie_script)
    """
    if len(sys.argv) > 1 and sys.argv[1] == 'subprocess':
        port = int(sys.argv[2])
        if sys.version_info[0] == 3:
            from . import py3k, __path__
            __path__[:] = py3k.__path__
            #import pdb; pdb.set_trace()
        from .subprocess import main as subprocess_main
        subprocess_main(port)

    else:
        from .gui import main as gui_main
        gui_main(dreampie_script)

