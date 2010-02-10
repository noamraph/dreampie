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
Build zips used by the subprocess.
This is not in setup.py so that it may be called at runtime when running
from the source directory.
"""

import sys
import os
import zipfile

try:
    from lib2to3 import refactor
except ImportError:
    py3_available = False
else:
    py3_available = True

zip_fns = {2: 'subp-py2.zip', 3: 'subp-py3.zip'}
if py3_available:
    zip_vers = [2, 3]
else:
    zip_vers = [2]

def newer_group (sources, target):
    """This is equivalent to distutils.dep_util.newer_group, where
    messing=='error'. It's here because I didn't want to depend on distutils.
    """
    if not os.path.exists(target):
        return True

    target_mtime = os.path.getmtime(target)
    for source in sources:
        source_mtime = os.path.getmtime(source)
        if source_mtime > target_mtime:
            return True
    else:
        return False

class SimpleLogger(object):
    """Used when real logging isn't needed"""
    def debug(self, s):
        pass
    def info(self, s):
        print >> sys.stderr, s
simple_logger = SimpleLogger()

def build(src_dir, build_dir, log=simple_logger, force=False):
    join = os.path.join
    
    files = ['subprocess/__init__.py',
             'common/__init__.py',
             'common/objectstream.py',
             'common/brine.py',
             ]
    
    for ver in zip_vers:
        zip_fn = join(build_dir, zip_fns[ver])

        src_files = [join(src_dir, fn) for fn in files]
        if not force and not newer_group(src_files, zip_fn):
            log.debug("not building %s (up-to-date)" % zip_fn)
            continue
            
        log.info("Building %s" % zip_fn)
        zf = zipfile.ZipFile(zip_fn, 'w')
        if ver == 3:
            avail_fixes = refactor.get_fixers_from_package('lib2to3.fixes')
            rt = refactor.RefactoringTool(avail_fixes)
            for fn in files:
                log.info("Converting %s to Python 3 and archiving..." % fn)
                f = open(join(src_dir, fn), 'rb')
                src = f.read()
                f.close()
                dst = str(rt.refactor_string(src+'\n', fn))[:-1]
                zf.writestr(fn, dst)
        else:
            for fn in files:
                log.info("Archiving %s..." % fn)
                f = open(join(src_dir, fn), 'rb')
                src = f.read()
                f.close()
                zf.writestr(fn, src)
        zf.close()
        log.info("Finished building %s." % zip_fn)
