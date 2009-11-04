#!/usr/bin/env python

from distutils.core import setup
from distutils.command.install_lib import install_lib

class InstallLib(install_lib):
    def byte_compile(self, files):
        filtered_files = [f for f in files if 'py3k' not in f]
        install_lib.byte_compile(self, filtered_files)

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
              'dreampielib.py3k',
              'dreampielib.py3k.common', 'dreampielib.py3k.subprocess',
              ],
    package_data={'dreampielib.gui':
                  ['dreampie.glade', 'dreampie.svg', 'dreampie.png'],
                  },
    data_files=[
                ('share/applications', ['dreampie.desktop']),
                ('share/man/man1', ['dreampie.1']),
               ],
    cmdclass={'install_lib': InstallLib}
    )

