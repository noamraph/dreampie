#!/usr/bin/env python

import sys
import os
from os.path import join

from distutils.core import setup

from dreampielib import __version__, subp_lib

# What's non-standard about installing DreamPie is:
# * There are automatically generated modules, in dreampielib/data.
#   These are generated whenever the setup.py script is run, so from the
#   distutils point of view these files are regular package data files.
# * py2exe doesn't support package data, so "regular" data_files are used,
#   and the 'data' directory ends up near the executable.
# * when py2exe is used, the version is automatically set in setup.nsi.

subp_lib.build()

if 'py2exe' in sys.argv:
    import py2exe #@UnresolvedImport
else:
    py2exe = None

package_data_files = (['data/dreampie.glade',
                       'data/dreampie.png',
                       'data/subp_main.py'] + 
                      [join('data', libfn, fn)
                       for libfn in subp_lib.lib_fns.values()
                       for fn in subp_lib.files])

if py2exe is not None:
    # Add files normally installed in package_data to data_files
    d = {}
    for fn in package_data_files:
        d.setdefault(os.path.dirname(fn), []).append(join('dreampielib', fn))
    additional_py2exe_data_files = d.items()
    
    # Update setup.nsi
    mydir = os.path.dirname(os.path.abspath(__file__))
    template = open(join(mydir, 'setup.nsi.in')).read()
    prod_ver_num_short = map(int, __version__.split('.'))
    prod_ver_num = prod_ver_num_short + [0] * (4-len(prod_ver_num_short))
    prod_ver = '.'.join(map(str, prod_ver_num))
    setup_nsi = ('# Generate from setup.nsi.in. DO NOT EDIT.\n'
                 + template.replace('{AUTO_VERSION}', __version__)
                           .replace('{AUTO_PRODUCT_VERSION}', prod_ver))
    f = open(join(mydir, 'setup.nsi'), 'w')
    f.write(setup_nsi)
    f.close()
    
    
else:
    additional_py2exe_data_files = []


setup_args = dict(
    name='dreampie',
    version=__version__,
    description="DreamPie - The interactive Python shell you've always dreamed about!",
    author='Noam Yorav-Raphael',
    author_email='noamraph@gmail.com',
    url='http://www.dreampie.org/',
    license='GPL v3+',
    scripts=['dreampie'],
    packages=['dreampielib',
              'dreampielib.common', 'dreampielib.gui', 'dreampielib.subprocess',
              ],
    package_data={'dreampielib': package_data_files},
    data_files=[
                ('share/applications', ['share/applications/dreampie.desktop']),
                ('share/man/man1', ['share/man/man1/dreampie.1']),
                ('share/pixmaps', ['share/pixmaps/dreampie.svg',
                                   'share/pixmaps/dreampie.png']),
               ] + additional_py2exe_data_files,
    zip_safe=False,
    )

if py2exe is not None:
    setup_args.update(dict(
        console=[{'script': 'dreampie.py',
                  'icon_resources': [(1, 'dreampie.ico')]}],
        windows=[{'script': 'create-shortcuts.py',
                  'icon_resources': [(1, 'blank.ico')]}],
        options={'py2exe':
                 {'excludes':['_scproxy', 'glib', 'gobject', 'gtk',
                             'gtk.gdk', 'gtk.glade', 'gtksourceview2',
                             'pango', 'pygtk', 'runtime', 'comtypes.gen',
                             '_ssl', 'doctest', 'pdb', 'unittest', 'difflib',
                             'unicodedata', 'bz2', 'zipfile', 'lib2to3',
                             'dulwich', 'dulwich.repo', 'win32api', 'win32con',
                             'win32pipe', 'Carbon', 'Carbon.Files', 'decimal'],
                  'includes':['fnmatch', 'glob', 'ctypes.util'],
                  
                 }},
    ))

setup(**setup_args)
