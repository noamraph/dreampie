#!/usr/bin/env python

import os

from distutils.core import setup
from distutils.command.build import build
from distutils.command.install import install
from distutils.core import Command
from distutils import log

from dreampielib import __version__, subp_lib

try:
    import py2exe
except ImportError:
    py2exe = None

# This file is non-standard because we want to build the subprocess library
# (subp-py2, subp-py3) and put them in share/dreampie.
# When run from the source directory, these files are automatically
# created in the local share/dreampie.
# We don't want to always do that in the setup script because the debian 
# packaging doesn't expect to find new files outside the build directory.
# So we build them in the build directory and have a special install command
# which copies them to the right place.
# However, py2exe doesn't run custom install commands. So it py2exe is
# available, the build_subp_lib commands puts them in the local share/dreampie
# dir, and they are added to the data_files list. 

class build_subp_lib(Command):
    description = 'Build the subprocess lib, which include the needed modules.'

    user_options = [
        ('build-dir=', 'd', "directory to build to"),
        ('force', 'f', "forcibly build everything (ignore file timestamps"),
        ]
    
    boolean_options = ['force']


    def initialize_options(self):
        self.build_dir = None
        self.force = None

    def finalize_options(self):
        self.set_undefined_options('build',
                                   ('build_base', 'build_dir'),
                                   ('force', 'force'),
                                   )

    def run(self):
        my_dir = os.path.dirname(__file__)
        src_dir = my_dir
        if py2exe is None:
            dst_dir = self.build_dir
        else:
            dst_dir = os.path.join(my_dir, 'share', 'dreampie')
        subp_lib.build(src_dir, dst_dir, log, self.force)

build.sub_commands.append(('build_subp_lib', None))

class install_subp_lib (Command):

    description = "install the subprocess lib"

    user_options = [
        ('install-dir=', 'd', "directory to install lib to"),
        ('build-dir=','b', "build directory (where to install from)"),
        ('force', 'f', "force installation (overwrite existing files)"),
        ('skip-build', None, "skip the build steps"),
    ]

    boolean_options = ['force', 'skip-build']


    def initialize_options (self):
        self.install_dir = None
        self.force = 0
        self.build_dir = None
        self.skip_build = None
        self.outfiles = []

    def finalize_options (self):
        self.set_undefined_options('build', ('build_base', 'build_dir'))
        self.set_undefined_options('install',
                                   ('install_data', 'install_dir'),
                                   ('force', 'force'),
                                   ('skip_build', 'skip_build'),
                                  )

    def run (self):
        join = os.path.join

        if not self.skip_build:
            self.run_command('build_subp_lib')
        
        for ver in subp_lib.lib_vers:
            src = join(self.build_dir, subp_lib.lib_fns[ver])
            dst = join(self.install_dir, 'share', 'dreampie', subp_lib.lib_fns[ver])
            self.outfiles.append(self.copy_tree(src, dst))

    def get_outputs(self):
        return self.outfiles

if py2exe is None:
    install.sub_commands.append(('install_subp_lib', None))

if py2exe is not None:
    d = {}
    for v in subp_lib.lib_vers:
        for fn in subp_lib.files:
            dst_dir = os.path.join('share/dreampie',
                                   subp_lib.lib_fns[v],
                                   os.path.dirname(fn))
            src_fn = os.path.join('share/dreampie', subp_lib.lib_fns[v], fn)
            d.setdefault(dst_dir, []).append(src_fn)
    additional_py2exe_data_files = d.items()
else:
    additional_py2exe_data_files = []

setup_args = dict(
    name='dreampie',
    version=__version__,
    description="DreamPie - The interactive Python shell you've always dreamed about!",
    author='Noam Yorav-Raphael',
    author_email='noamraph@gmail.com',
    url='http://dreampie.sourceforge.net/',
    license='GPL v3+',
    scripts=['dreampie'],
    console=[{'script': 'dreampie.py',
              'icon_resources': [(1, 'dreampie.ico')]}],
    windows=[{'script': 'create-shortcuts.py',
              'icon_resources': [(1, 'blank.ico')]}],
    packages=['dreampielib',
              'dreampielib.common', 'dreampielib.gui', 'dreampielib.subprocess',
              ],
    data_files=[
                ('share/applications', ['share/applications/dreampie.desktop']),
                ('share/man/man1', ['share/man/man1/dreampie.1']),
                ('share/pixmaps', ['share/pixmaps/dreampie.svg',
                                   'share/pixmaps/dreampie.png']),
                ('share/dreampie', ['share/dreampie/subp_main.py',
                                    'share/dreampie/dreampie.glade']),
               ] + additional_py2exe_data_files,
    cmdclass={'build_subp_lib': build_subp_lib,
              'install_subp_lib': install_subp_lib},
    options={'py2exe':
             {'ignores':['_scproxy', 'glib', 'gobject', 'gtk',
                         'gtk.gdk', 'gtk.glade', 'gtksourceview2',
                         'pango', 'pygtk'],
              'excludes':['_ssl', 'doctest', 'pdb', 'unittest', 'difflib',
                          'unicodedata', 'bz2', 'zipfile', 'lib2to3'],
              'includes':['fnmatch', 'glob'],
             }},
     
    )
if py2exe is None:
    # Avoid the warning if py2exe is not available
    del setup_args['console']
    del setup_args['windows']
setup(**setup_args)
