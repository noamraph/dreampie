DreamPie - The Python shell you've always dreamed about!
========================================================

DreamPie is a Python shell which is designed to be reliable and fun. It is licensed under GPLv3.

For more information, take a look at http://www.dreampie.org/

To run, you will need Python 2.6 or 2.7, and PyGTK with pygtksourceview.

* On Windows, get the PyGTK all-in-one installer from
  http://ftp.gnome.org/pub/GNOME/binaries/win32/pygtk/2.24/ and be sure to
  select pygtksourceview.
* On Mac, get it from http://sourceforge.net/projects/macpkg/files/PyGTK/2.24.0/
* On Linux, it's probably already installed.

You can simply run dreampie.py or dreampie. Or, if you wish:

* On Windows, you can run create-shortcuts.py to create start menu shortcuts.
* On Mac and Linux, run

    ln -s dreampie /usr/local/bin

DreamPie can use just about any Python interpreter (Jython, IronPython, PyPy).
You can give as it an argument with the name of the interpreter:

    ./dreampie python3
    ./dreampie /path/to/pypy
