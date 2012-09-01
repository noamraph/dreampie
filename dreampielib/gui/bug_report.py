# Copyright 2012 Noam Yorav-Raphael
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

__all__ = ['bug_report', 'set_subp_pyexec']

import sys
import platform
import time
import webbrowser

import gtk
from gtk import glade

from .. import __version__
from .git import get_commit_details

subp_pyexec = None
subp_desc = None
def set_subp_info(pyexec, welcome):
    global subp_pyexec, subp_desc
    subp_pyexec = pyexec
    subp_desc = welcome.split('\n')[0]


_is_git = _latest_name = _latest_time = _cur_time = None
def set_update_info(is_git, latest_name, latest_time, cur_time):
    global _is_git, _latest_name, _latest_time, _cur_time
    _is_git = is_git
    _latest_name = latest_name
    _latest_time = latest_time
    _cur_time = cur_time

def get_prefilled(trace):
    commit_id, commit_time = get_commit_details()
    commit_date = time.strftime('%Y/%m/%d', time.localtime(commit_time))
    s = """\
What steps will reproduce the problem?
1.
2.
3.

What is the expected result?


What happens instead?


Please provide any additional information below. To submit a screenshot, you \
can go to imgur.com, upload the image, and paste the URL.





-------------------
Diagnostic information:

DreamPie version: {version}
git commit: {commit_id} from {commit_date}
platform: {platform}
architecture: {architecture}
python_version: {python_version}
python_implementation: {python_implementation}
executable: {executable}
subprocess executable: {subp_pyexec}
subprocess description: {subp_desc}

""".format(version=__version__,
           commit_id=commit_id,
           commit_date=commit_date,
           platform=platform.platform(),
           architecture=platform.architecture(),
           python_version=platform.python_version(),
           python_implementation=platform.python_implementation(),
           executable=sys.executable,
           subp_pyexec=subp_pyexec,
           subp_desc=subp_desc,
           )
    if trace:
        s += trace
    return s

def get_update_message():
    if _latest_time is None:
        return None
    if _latest_time <= _cur_time and _is_git:
        return None
    
    if _latest_time > _cur_time:
        if _is_git:
            msg = """\
Note: you are not using the latest git commit. Please run 'git pull' and see \
if the problem persists."""
        else:
            msg = """\
Note: you are using an out of date version of DreamPie. Please go to \
www.dreampie.org/download.html and download a new version.

If you can, please use a git repository. This will let you see if the bug was \
already fixed and let you check immediately if the committed fix actually \
works. You will also enjoy other improvements earlier."""
    else:
        msg = """\
Note: you are using the DreamPie released version. If you can, please clone \
the git repository from https://github.com/noamraph/dreampie.git and see if \
the problem persists. Even if it does, it will let you check immediately if \
the committed fix actually works. You will also enjoy other improvements \
earlier."""

    return '<span color="red">%s</span>\n' % msg

def bug_report(master_window, gladefile, trace):
    """
    Send the user to a bug report webpage, instructing him to paste a template
    with questions and diagnostics information.
    
    master_window: gtk.Window, master of the dialog.
    gladefile: glade filename, for getting the widgets.
    trace: a string with the formatted traceback, or None.
    """
    xml = glade.XML(gladefile, 'bug_report_dialog')
    d = xml.get_widget('bug_report_dialog')
    bug_report_textview = xml.get_widget('bug_report_textview')
    update_label = xml.get_widget('update_label')
    d.set_transient_for(master_window)
    d.set_default_response(gtk.RESPONSE_OK)
    
    prefilled = get_prefilled(trace)
    tb = bug_report_textview.get_buffer()
    tb.set_text(prefilled)
    update_msg = get_update_message()
    if update_msg:
        update_label.set_markup(update_msg)
        update_label.show()
    clipboard = gtk.Clipboard()
    clipboard.set_text(prefilled)
    
    r = d.run()
    d.destroy()
    
    if r == gtk.RESPONSE_OK:
        webbrowser.open('https://github.com/noamraph/dreampie/issues/new')
