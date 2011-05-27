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

__all__ = ['trunc_traceback']

import sys
py3k = (sys.version_info[0] == 3)
import traceback
import linecache
from StringIO import StringIO

def unicodify(s):
    """Fault-tolerant conversion to unicode"""
    return s if isinstance(s, unicode) else s.decode('utf8', 'replace')

#######################################################################
# This is copied from traceback.py from Python 3.1.1.
# It is copied because I don't want to rely on private functions.

_cause_message = (
    "\nThe above exception was the direct cause "
    "of the following exception:\n")

_context_message = (
    "\nDuring handling of the above exception, "
    "another exception occurred:\n")

def _iter_chain(exc, custom_tb=None, seen=None):
    if seen is None:
        seen = set()
    seen.add(exc)
    its = []
    cause = exc.__cause__
    context = exc.__context__
    if cause is not None and cause not in seen:
        its.append(_iter_chain(cause, None, seen))
        its.append([(_cause_message, None)])
    if context is not None and context is not cause and context not in seen:
        its.append(_iter_chain(context, None, seen))
        its.append([(_context_message, None)])
    its.append([(exc, custom_tb or exc.__traceback__)])
    # itertools.chain is in an extension module and may be unavailable
    for it in its:
        for x in it:
            yield x

# Copied up to here.
#######################################################################


def canonical_fn(fn):
    """
    Return something that will be equal for both source file and the cached
    compile file.
    """
    # If the file contains a '$', remove from it (Jython uses it). Otherwise,
    # remove from a '.'.
    if '$' in fn:
        return fn.rsplit('$', 1)[0]
    else:
        return fn.rsplit('.', 1)[0]

def trunc_traceback((_typ, value, tb), source_file):
    """
    Format a traceback where entries before a frame from source_file are
    omitted (unless the last frame is from source_file).
    Return the result as a unicode string.
    """
    # This is complicated because we want to support nested tracebacks
    # in Python 3.

    linecache.checkcache()
    efile = StringIO()
    
    if py3k:
        values = _iter_chain(value, tb)
    else:
        values = [(value, tb)]
    
    # The source_file and filename may differ in extension (pyc/py), so we
    # ignore the extension
    source_file = canonical_fn(source_file)
    
    for value, tb in values:
        if isinstance(value, basestring):
            efile.write(value+'\n')
            continue
    
        tbe = traceback.extract_tb(tb)
        # This is a work around a really weird IronPython bug.
        while len(tbe)>1 and 'split_to_singles' in tbe[-1][0]:
            tbe.pop()
            
        # tbe may be an empty list if "raise from ExceptionClass" was used.
        if tbe and canonical_fn(tbe[-1][0]) != source_file:
            # If the last entry is from this file, don't remove
            # anything. Otherwise, remove lines before the current
            # frame.
            for i in xrange(len(tbe)-2, -1, -1):
                if canonical_fn(tbe[i][0]) == source_file:
                    tbe = tbe[i+1:]
                    break
                
        if tbe:
            efile.write('Traceback (most recent call last):'+'\n')
        traceback.print_list(tbe, file=efile)
        lines = traceback.format_exception_only(type(value), value)
        for line in lines:
            efile.write(line)
            
    if not hasattr(efile, 'buflist'):
        # Py3k
        return efile.getvalue()
    else:
        # The following line replaces efile.getvalue(), because if it
        # includes both unicode strings and byte string with non-ascii
        # chars, it fails.
        return u''.join(unicodify(s) for s in efile.buflist)
