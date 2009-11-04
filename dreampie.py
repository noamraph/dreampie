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

if len(sys.argv) > 1 and sys.argv[1] == 'subprocess':
    port = int(sys.argv[2])
    if sys.version_info[0] == 3:
        import os
        import dreampielib
        dreampielib.__path__[0] = os.path.join(dreampielib.__path__[0],
                                               os.path.pardir,
                                               'py3k', 'dreampielib')
    from dreampielib.subprocess import main
    main(port)

else:
    if len(sys.argv) > 1 and sys.argv[1] == 'hide-console-window':
        from dreampielib.gui.hide_console_window import hide_console_window
        hide_console_window()
        
    from dreampielib.gui import main
    main(__file__)
