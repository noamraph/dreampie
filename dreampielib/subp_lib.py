# Copyright 2010 Noam Yorav-Raphael
#
# This file is part of DreamPie.
# 
# DreamPie is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# DreamPie is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with DreamPie.  If not, see <http://www.gnu.org/licenses/>.

"""
Build library used by the subprocess.
This is not in setup.py so that it may be called at runtime when running
from the source directory.
"""

__all__ = ['build', 'dirs', 'files', 'lib_fns', 'lib_vers']

import sys
import os
from os.path import join, abspath, dirname

try:
    from lib2to3 import refactor
except ImportError:
    py3_available = False
else:
    py3_available = True

dirs = [
    'dreampielib',
    'dreampielib/subprocess',
    'dreampielib/common']

files = [
    'dreampielib/__init__.py',
    'dreampielib/subprocess/__init__.py',
    'dreampielib/subprocess/find_modules.py',
    'dreampielib/subprocess/split_to_singles.py',
    'dreampielib/subprocess/trunc_traceback.py',
    'dreampielib/common/__init__.py',
    'dreampielib/common/objectstream.py',
    'dreampielib/common/brine.py',
    ]

lib_fns = {2: 'subp-py2', 3: 'subp-py3'}
if py3_available:
    lib_vers = [2, 3]
else:
    lib_vers = [2]

def newer(source, target):
    """
    Return True if the source is newer than the target or if the target doesn't
    exist.
    """
    if not os.path.exists(target):
        return True
    
    return os.path.getmtime(source) > os.path.getmtime(target)

class SimpleLogger(object):
    """Used when real logging isn't needed"""
    def debug(self, s):
        pass
    def info(self, s):
        print >> sys.stderr, s
simple_logger = SimpleLogger()

def build(log=simple_logger, force=False):
    dreampielib_dir = dirname(abspath(__file__))
    src_dir = dirname(dreampielib_dir)
    build_dir = join(dreampielib_dir, 'data')
    
    if py3_available:
        avail_fixes = refactor.get_fixers_from_package('lib2to3.fixes')
        rt = refactor.RefactoringTool(avail_fixes)
    
    for ver in lib_vers:
        lib_fn = join(build_dir, lib_fns[ver])

        # Make dirs if they don't exist yet
        if not os.path.exists(lib_fn):
            os.mkdir(lib_fn)
        for dir in dirs:
            dir_fn = join(lib_fn, dir)
            if not os.path.exists(dir_fn):
                os.mkdir(dir_fn)
        
        # Write files if not up to date
        for fn in files:
            src_fn = join(src_dir, fn)
            dst_fn = join(lib_fn, fn)
            if not force and not newer(src_fn, dst_fn):
                continue
            
            if ver == 3:
                log.info("Converting %s to Python 3..." % fn)
            else:
                log.info("Copying %s..." % fn)
            
            f = open(join(src_dir, fn), 'rb')
            src = f.read()
            f.close()
            
            if ver == 3:
                dst = str(rt.refactor_string(src+'\n', fn))[:-1]
            else:
                dst = src
            
            dst = """\
# This file was automatically generated from a file in the source DreamPie dir.
# DO NOT EDIT IT, as your changes will be gone when the file is created again.

""" + dst
            
            f = open(dst_fn, 'wb')
            f.write(dst)
            f.close()
