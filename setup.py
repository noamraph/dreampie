#!/usr/bin/env python

import os
from os.path import join, dirname, getmtime, exists
import sys
import zipfile

from distutils.core import setup
from distutils.command.build import build
from distutils.core import Command

try:
    from lib2to3 import refactor
except ImportError:
    refactor = None

class build_subp_zips(Command):
    description = 'Build the subprocess zips, which include the needed modules.'

    user_options = []

    def initialize_options(self):
    	pass

    def finalize_options(self):
    	pass

    def run(self):
        join = os.path.join
        
        files = ['subprocess/__init__.py',
                 'common/__init__.py',
                 'common/objectstream.py',
                 'common/brine.py',
                 ]
        
        my_dir = dirname(__file__)
        src_dir = join(my_dir, 'dreampielib')
        zip_fns = {2: join(my_dir, 'share/dreampie/subp-py2.zip'),
                   3: join(my_dir, 'share/dreampie/subp-py3.zip')}
        
        last_mtime = max(getmtime(join(src_dir, fn)) for fn in files)
        
        if refactor:
            vers = [2, 3]
        else:
            print >> sys.stderr, "Warning: Python 3 support will not be built, "\
                                 "because lib2to3 is not available. Build with "\
                                 "Python 2.6!"
            vers = [2]
            
        for ver in vers:
            zip_fn = zip_fns[ver]
            if not exists(zip_fn) or getmtime(zip_fn) < last_mtime:
                print >> sys.stderr, "Building %s" % zip_fn
                zf = zipfile.ZipFile(zip_fn, 'w')
                if ver == 3:
                    avail_fixes = refactor.get_fixers_from_package('lib2to3.fixes')
                    rt = refactor.RefactoringTool(avail_fixes)
                    for fn in files:
                        print >> sys.stderr, "Converting %s to Python 3 and archiving..." % fn
                        f = open(join(src_dir, fn), 'rb')
                        src = f.read()
                        f.close()
                        dst = str(rt.refactor_string(src+'\n', fn))[:-1]
                        zf.writestr(fn, dst)
                else:
                    for fn in files:
                        print >> sys.stderr, "Archiving %s..." % fn
                        f = open(join(src_dir, fn), 'rb')
                        src = f.read()
                        f.close()
                        zf.writestr(fn, src)
                zf.close()
                print >> sys.stderr, "Finished building %s." % zip_fn

build.sub_commands.append(('build_subp_zips', None))


setup(
    name='DreamPie',
    version='0.1',
    description="The interactive Python shell you've always dreamed about!",
    author='Noam Yorav-Raphael',
    author_email='noamraph@gmail.com',
    url='https://launchpad.net/dreampie',
    license='GPL v3',
    scripts=['dreampie'],
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
                                    'share/dreampie/dreampie.glade',
                                    'share/dreampie/subp-py2.zip']
                                 + ['share/dreampie/subp-py3.zip'] if refactor else []),
               ],
    cmdclass={'build_subp_zips': build_subp_zips},
    )

