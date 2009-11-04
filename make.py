#!/usr/bin/env python

# This is a simple script which creates the files in the dreampielib/py3k dir
# from the files in the dreampielib dir.

from os.path import join, abspath, dirname, pardir
import shutil
from lib2to3.main import main as lib2to3_main

origdir = abspath(join(dirname(__file__), 'dreampielib'))
py3kdir = join(origdir, 'py3k')

def fix_file(path):
    print path
    py3kpath = join(py3kdir, path)
    origpath = join(origdir, path)
    shutil.copy(origpath, py3kpath)
    lib2to3_main('lib2to3.fixes', ['-w', '-n', py3kpath])

files = ['subprocess/__init__.py',
         'common/__init__.py',
         'common/objectstream.py',
         'common/brine.py',
         ]

def main():
    for fn in files:
        fix_file(fn)

if __name__ == '__main__':
    main()
