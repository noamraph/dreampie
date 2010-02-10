#!/usr/bin/env python

import os

from distutils.core import setup
from distutils.command.build import build
from distutils.command.install import install
from distutils.core import Command
from distutils import log

from dreampielib import __version__, subp_zips

try:
    import py2exe
except ImportError:
    py2exe = None

class build_subp_zips(Command):
    description = 'Build the subprocess zips, which include the needed modules.'

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
                                   ('build_lib', 'build_dir'),
                                   ('force', 'force'),
                                   )

    def run(self):
        my_dir = os.path.dirname(__file__)
        src_dir = os.path.join(my_dir, 'dreampielib')
        subp_zips.build(src_dir, self.build_dir, log, self.force)

build.sub_commands.append(('build_subp_zips', None))

class install_subp_zips (Command):

    description = "install the subprocess zips"

    user_options = [
        ('install-dir=', 'd', "directory to install zips to"),
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
        self.infiles = []
        self.outfiles = []

    def finalize_options (self):
        self.set_undefined_options('build', ('build_lib', 'build_dir'))
        self.set_undefined_options('install',
                                   ('install_data', 'install_dir'),
                                   ('force', 'force'),
                                   ('skip_build', 'skip_build'),
                                  )

    def run (self):
        join = os.path.join

        if not self.skip_build:
            self.run_command('build_subp_zips')
        
        for ver in subp_zips.zip_vers:
            src = join(self.build_dir, subp_zips.zip_fns[ver])
            dst = join(self.install_dir, 'share', 'dreampie', subp_zips.zip_fns[ver])
            self.copy_file(src, dst)
            self.infiles.append(src)
            self.outfiles.append(dst)

    def get_inputs (self):
        return self.infiles

    def get_outputs(self):
        return self.outfiles

install.sub_commands.append(('install_subp_zips', None))


setup_args = dict(
    name='dreampie',
    version=__version__,
    description="DreamPie - The interactive Python shell you've always dreamed about!",
    author='Noam Yorav-Raphael',
    author_email='noamraph@gmail.com',
    url='https://launchpad.net/dreampie',
    license='GPL v3',
    scripts=['dreampie'],
    console=[{'script': 'dreampie.py',
              'icon_resources': [(1, 'dreampie.ico')]}],
    windows=[{'script': 'create-shortcuts.py',
              'icon_resources': [(1, 'dreampie.ico')]}],
    packages=['dreampielib',
              'dreampielib.common', 'dreampielib.gui', 'dreampielib.subprocess',
              ],
    package_data={'dreampielib.gui':
                  ['dreampie.glade', 'dreampie.svg', 'dreampie.png'],
                  'dreampielib': ['py3k.zip'],
                  },
    data_files=[
                ('share/applications', ['share/applications/dreampie.desktop']),
                ('share/man/man1', ['share/man/man1/dreampie.1']),
                ('share/pixmaps', ['share/pixmaps/dreampie.svg',
                                   'share/pixmaps/dreampie.png']),
                ('share/dreampie', ['share/dreampie/subp_main.py',
                                    'share/dreampie/dreampie.glade']),
               ],
    cmdclass={'build_subp_zips': build_subp_zips,
              'install_subp_zips': install_subp_zips},
    options={'py2exe':
             {'ignores':['_scproxy', 'glib', 'gobject', 'gtk',
                         'gtk.gdk', 'gtk.glade', 'gtksourceview2',
                         'pango', 'pygtk'],
              'excludes':['_ssl', 'doctest', 'pdb', 'unittest', 'difflib' ],
              'includes':['fnmatch', 'glob'],
             }},
     
    )
if py2exe is None:
    # Avoid the warning if py2exe is not available
    del setup_args['console']
    del setup_args['windows']
setup(**setup_args)
