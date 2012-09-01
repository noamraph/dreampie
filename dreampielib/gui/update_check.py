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

all = ['update_check']

import threading
import httplib
import json

try:
    from glib import idle_add
except ImportError:
    # In PyGObject 2.14, it's in gobject.
    from gobject import idle_add

from .. import release_timestamp
from .git import get_commit_details
from . import bug_report

def log(s):
    pass

def update_check_in_thread(is_git, cur_time, on_update_available):
    if is_git:
        fn = '/latest-commit.json'
    else:
        fn = '/latest-release.json'

    try:
        conn = httplib.HTTPConnection("www.dreampie.org")
        log("Fetching http://www.dreampie.org%s" % fn)
        conn.request("GET", fn)
        r = conn.getresponse()
        if r.status != 200:
            return
        data = r.read()
        d = json.loads(data)
    except Exception, e:
        log("Exception while fetching update info: %s" % e)
        return
    
    if is_git:
        latest_name = None
        latest_time = d['latest_commit_timestamp']
    else:
        latest_name = d['latest_release_name']
        latest_time = d['latest_release_timestamp']
    
    bug_report.set_update_info(is_git, latest_name, latest_time, cur_time)
    if latest_time > cur_time:
        # Call in main thread
        idle_add(on_update_available, is_git, latest_name, latest_time)
    else:
        log("No more recent release/commit")

def update_check(on_update_available):
    """
    Check (in the background) if updates are available.
    If so, on_update_available(is_git, latest_name, latest_time) will be called.
    """
    commit_id, commit_time = get_commit_details()
    if commit_id is not None:
        is_git = True
        cur_time = commit_time
    else:
        is_git = False
        cur_time = release_timestamp
    
    t = threading.Thread(target=update_check_in_thread,
                         args=(is_git, cur_time, on_update_available))
    t.daemon = True
    t.start()
    