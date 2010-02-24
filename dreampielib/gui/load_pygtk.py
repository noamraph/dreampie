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

__all__ = ['load_pygtk']

import os
from os.path import join, pardir
import sys

def load_pygtk(data_dir):
    """On win32, load PyGTK from subdirectory, if available."""
    pygtk_dir = join(data_dir, pardir,
                     'pygtk-%d.%d' % (sys.version_info[0], sys.version_info[1]))
    if os.path.isdir(pygtk_dir):
        orig_pypath = sys.path
        sys.path = [pygtk_dir] + sys.path
    else:
        orig_pypath = None
        
    gtk_runtime_dir = join(data_dir, pardir, 'gtk-runtime')
    if os.path.isdir(gtk_runtime_dir):
        orig_path = os.environ['PATH']
        os.environ['PATH'] = join(gtk_runtime_dir, 'bin')
    else:
        orig_path = None
        
    try:
        import pygtk
        pygtk.require('2.0')
        import gobject
        import gtk
        _ = gtk
        import gtk.glade
        import pango
        import gtksourceview2
        # Make pydev quiet
        _ = gobject, gtk, gtk.glade, pango, gtksourceview2
        try:
            import glib
            _ = glib
        except ImportError:
            # glib is only from 2.14, I think.
            pass
        
    finally:
        if orig_pypath is not None:
            sys.path = orig_pypath
        if orig_path is not None:
            os.environ['PATH'] = orig_path

