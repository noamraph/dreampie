__all__ = ['load_pygtk']

import os
import sys

def load_pygtk():
    """On win32, load PyGTK from subdirectory, if available."""
    join = os.path.join
    mydir = os.path.dirname(__file__)
    
    pygtk_dir = join(mydir,
                     'pygtk-%d.%d' % (sys.version_info[0], sys.version_info[1]))
    if os.path.isdir(pygtk_dir):
        orig_pypath = sys.path
        sys.path = [pygtk_dir] + sys.path
    else:
        orig_pypath = None
        
    gtk_runtime_dir = join(mydir, 'gtk-runtime')
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
        import gtk.glade
        import pango
        import gtksourceview2
        try:
            import glib
        except ImportError:
            # glib is only from 2.14, I think.
            pass
        
    finally:
        if orig_pypath is not None:
            sys.path = orig_pypath
        if orig_path is not None:
            os.environ['PATH'] = orig_path

