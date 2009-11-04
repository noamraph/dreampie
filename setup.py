#!/usr/bin/env python

from distutils.core import setup

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
                ('share/applications', ['dreampie.desktop']),
                ('share/man/man1', ['dreampie.1']),
               ],
    )

