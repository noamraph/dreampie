#!/usr/bin/env python

# This script creates the py3k.zip archive inside dreampielib.

import os
from os.path import join, abspath, dirname, pardir
from zipfile import ZipFile
from tempfile import mkstemp
from lib2to3.main import main as lib2to3_main

dp_dir = abspath(join(dirname(__file__), 'dreampielib'))

def fix_file(path, zipfile):
    print path
    # The practically calls 2to3, which prints a lot of noise.
    # Probably would have been better to understand the lib2to3 interface.
    orig_path = join(dp_dir, path)
    handle, temp_path = mkstemp()
    os.close(handle)
    orig_contents = open(orig_path).read()
    f = open(temp_path,'w')
    f.write(orig_contents)
    f.close()
    lib2to3_main('lib2to3.fixes', ['-w', '-n', temp_path])
    f = open(temp_path)
    new_contents = f.read()
    f.close()
    os.remove(temp_path)
    zipfile.writestr(path, new_contents)

files = ['subprocess/__init__.py',
         'common/__init__.py',
         'common/objectstream.py',
         'common/brine.py',
         ]

def main():
    zipfile = ZipFile(join(dp_dir, 'py3k.zip'), 'w')
    for fn in files:
        fix_file(fn, zipfile)
    zipfile.close()

if __name__ == '__main__':
    main()
