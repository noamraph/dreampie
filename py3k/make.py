#!/usr/bin/env python

from os.path import join, abspath, dirname, pardir
import shutil
from lib2to3.main import main as lib2to3_main

py3kdir = abspath(dirname(__file__))
origdir = abspath(join(py3kdir, pardir))

def fix_file(path):
    print path
    py3kpath = join(py3kdir, 'dreampielib', path)
    origpath = join(origdir, 'dreampielib', path)
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
