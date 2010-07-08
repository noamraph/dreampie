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

import sys
import os
from os.path import join, isdir, exists
import stat
import imp
import re
import time

TIMEOUT = 1 # Stop after 1 second

# Match any of the suffixes
suffix_re = re.compile(
    r'(?:%s)$' % '|'.join(re.escape(suffix[0]) for suffix in imp.get_suffixes()))

# A mapping from absolute names to (mtime, module_names) tuple.
cache = {}

def find_in_dir(dirname):
    """
    Yield all names of modules in the given dir.
    """
    if dirname == '':
        dirname = '.'
    try:
        basenames = os.listdir(dirname)
    except OSError:
        return
    for basename in basenames:
        m = suffix_re.search(basename)
        if m:
            yield basename[:m.start()]
        else:
            if '.' not in basename and isdir(join(dirname, basename)):
                init = join(dirname, basename, '__init__.py')
                if exists(init) or exists(init+'c'):
                    yield basename    

def find_in_dir_cached(dirname):
    if dirname not in cache:
        # If it is in cache, it's already absolute.
        dirname = os.path.abspath(dirname)
    try:
        st = os.stat(dirname)
    except OSError:
        return ()
    if not stat.S_ISDIR(st.st_mode):
        return ()
    try:
        mtime, modules = cache[dirname]
    except KeyError:
        mtime = 0
    if mtime != st.st_mtime:
        modules = list(find_in_dir(dirname))
        cache[dirname] = (st.st_mtime, modules)
    return modules

def find_package_path(package):
    """
    Get a package as a list, try to find its path (list of dirs) or return None.
    """
    for i in xrange(len(package), 0, -1):
        package_name = '.'.join(package[:i])
        if package_name in sys.modules:
            try:
                path = sys.modules[package_name].__path__
            except AttributeError:
                return None
            break
    else:
        i = 0
        path = sys.path
    
    for j in xrange(i, len(package)):
        name = package[j]
        for dir in path:
            newdir = join(dir, name)
            if isdir(newdir):
                path = [newdir]
                break
        else:
            return None
    
    return path

def find_modules(package):
    """
    Get a sequence of names (what you get from package_name.split('.')),
    or [] for a toplevel module.
    Return a list of module names.
    """
    start_time = time.time()
    r = set()
    path = find_package_path(package)
    if path:
        for dirname in path:
            r.update(find_in_dir_cached(dirname))
            if time.time() - start_time > TIMEOUT:
                break
    prefix = ''.join(s+'.' for s in package)
    for name in sys.modules:
        if name.startswith(prefix):
            mod = name[len(prefix):]
            if '.' not in mod:
                r.add(mod)
    r.discard('__init__')
    return sorted(r)
