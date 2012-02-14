# Copyright 2009 Noam Yorav-Raphael
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

__all__ = ['HistPersist']

import os
from HTMLParser import HTMLParser
from htmlentitydefs import name2codepoint

from .file_dialogs import open_dialog, save_dialog
from .common import get_text

_ = lambda s: s

class HistPersist(object):
    """
    Provide actions for storing and loading history.
    """
    
    def __init__(self, window_main, textview, status_bar, recent_manager):
        self.window_main = window_main
        self.textview = textview
        self.textbuffer = textview.get_buffer()
        self.status_bar = status_bar
        self.recent_manager = recent_manager
        
        self.filename = None
        
        self.textbuffer.connect('modified-changed', self.on_modified_changed)
    
    def save_filename(self, filename):
        """
        Save history to a file.
        """
        f = open(filename, 'wb')
        save_history(self.textview, f)
        f.close()
        self.filename = filename
        self.status_bar.set_status(_('History saved.'))
        self.recent_add(filename)
        self.textbuffer.set_modified(False)

    def save(self):
        """
        Show the save dialog if there's no filename. Return True if was saved.
        """
        if self.filename is None:
            saved = self.save_as()
        else:
            self.save_filename(self.filename)
            saved = True
        return saved
    
    def save_as(self):
        """Show the save dialog. Return True if was saved."""
        if self.filename:
            prev_dir = os.path.dirname(self.filename)
            prev_name = os.path.basename(self.filename)
        else:
            prev_dir = None
            #prev_name = 'dreampie-history.html'
            prev_name = None
        saved = save_dialog(self.save_filename,
                            _('Choose where to save the history'),
                            self.window_main,
                            _('HTML Files'),
                            '*.html', 'html',
                            prev_dir, prev_name)
        return saved

    def load_filename(self, filename):
        s = open(filename, 'rb').read()
        parser = Parser(self.textbuffer)
        parser.feed(s)
        parser.close()
        self.status_bar.set_status(_('History loaded.'))
        self.filename = filename
        self.update_title()
        self.recent_add(filename)
    
    def load(self):
        open_dialog(self.load_filename,
                    _('Choose the saved history file'),
                    self.window_main,
                    _('HTML Files'),
                    '*.html')
    
    def recent_add(self, filename):
        # FIXME: This doesn't add an entry when saving HTML files. VERY strange.
        self.recent_manager.add_full('file://'+filename, {
            'mime_type': 'text/html', 'app_name': 'dreampie',
            'app_exec': 'dreampie'})
    
    def update_title(self):
        if self.filename:
            disp_fn = os.path.basename(self.filename)
            if self.textbuffer.get_modified():
                disp_fn += '*'
            self.window_main.set_title("%s - DreamPie" % disp_fn)
        else:
            self.window_main.set_title("DreamPie")
    
    def on_modified_changed(self, _widget):
        if self.filename:
            self.update_title()
    
    def was_saved(self):
        return self.filename is not None
    
    def forget_filename(self):
        self.filename = None
        self.update_title()


def _html_escape(s):
    """
    Replace special characters "&", "<" and ">" to HTML-safe sequences.
    """
    # This is taken from cgi.escape - I didn't want to import it, because of
    # py2exe
    s = s.replace("&", "&amp;") # Must be done first!
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    return s

def _format_color(color):
    return '#%02x%02x%02x' % (color.red >> 8, color.green >> 8, color.blue >> 8)

def save_history(textview, f):
    """
    Save the history - the content of the textview - to a HTML file f.
    """
    tv = textview
    tb = tv.get_buffer()
    style = tv.get_style()

    f.write("""\
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta name="DreamPie Format" content="1">
<title>DreamPie History</title>
<style>
body {
  white-space: pre-wrap;
  font-family: %s;
  font-size: %s;
  color: %s;
  background-color: %s;
}
""" % (
    style.font_desc.get_family(),
    style.font_desc.get_size(),
    _format_color(style.text[0]),
    _format_color(style.base[0]),
    )
)
    
    tt = tb.get_tag_table()
    all_tags = []
    tt.foreach(lambda tag, _data: all_tags.append(tag))
    all_tags.sort(key=lambda tag: -tag.get_priority())
    
    for tag in all_tags:
        f.write("span.%s {\n" % tag.props.name)
        if tag.props.foreground_set:
            f.write("  color: %s;\n" % _format_color(tag.props.foreground_gdk))
        if tag.props.background_set:
            f.write("  background-color: %s;\n"
                    % _format_color(tag.props.background_gdk))
        if tag.props.invisible:
            f.write(" display: none;\n")
        f.write("}\n")
    
    f.write("""\
</style>
</head>
<body>""")
    
    cur_tags = []
    it = tb.get_start_iter()
    while True:
        new_tags = cur_tags[:]
        for tag in it.get_toggled_tags(False):
            new_tags.remove(tag)
        for tag in it.get_toggled_tags(True):
            new_tags.append(tag)
        new_tags.sort(key=lambda tag: -tag.get_priority())
        
        shared_prefix = 0
        while (len(cur_tags) > shared_prefix and len(new_tags) > shared_prefix
               and cur_tags[shared_prefix] is new_tags[shared_prefix]):
            shared_prefix += 1
        for _i in range(len(cur_tags) - shared_prefix):
            f.write('</span>')
        for tag in new_tags[shared_prefix:]:
            f.write('<span class="%s">' % tag.props.name)
        
        if it.compare(tb.get_end_iter()) == 0:
            # We reached the end. We break here, because we want to close
            # the tags.
            break
        
        new_it = it.copy()
        new_it.forward_to_tag_toggle(None)
        text = get_text(tb, it, new_it)
        text = _html_escape(text)
        f.write(text.encode('utf8'))
        
        it = new_it
        cur_tags = new_tags
    
    f.write("""\
</body>
</html>
""")

class LoadError(Exception):
    pass

class Parser(HTMLParser):
    def __init__(self, textbuffer):
        HTMLParser.__init__(self)
        
        self.textbuffer = tb = textbuffer

        self.reached_body = False
        self.version = None
        self.cur_tags = []
        self.leftmark = tb.create_mark(None, tb.get_start_iter(), True)
        self.rightmark = tb.create_mark(None, tb.get_start_iter(), False)
    
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if not self.reached_body:
            if tag == 'meta':
                if 'name' in attrs and attrs['name'] == 'DreamPie Format':
                    if attrs['content'] != '1':
                        raise LoadError("Unrecognized DreamPie Format")
                    self.version = 1
            if tag == 'body':
                if self.version is None:
                    raise LoadError("File is not a DreamPie history file.")
                self.reached_body = True
        else:
            if tag == 'span':
                if 'class' not in attrs:
                    raise LoadError("<span> without a 'class' attribute")
                self.cur_tags.append(attrs['class'])
    
    def handle_endtag(self, tag):
        if tag == 'span':
            if not self.cur_tags:
                raise LoadError("Too many </span> tags")
            self.cur_tags.pop()
    
    def insert(self, data):
        tb = self.textbuffer
        leftmark = self.leftmark; rightmark = self.rightmark
        # For some reasoin, insert_with_tags_by_name marks everything with the
        # message tag. So we do it all by ourselves...
        tb.insert(tb.get_iter_at_mark(leftmark), data)
        leftit = tb.get_iter_at_mark(leftmark)
        rightit = tb.get_iter_at_mark(rightmark)
        tb.remove_all_tags(leftit, rightit)
        for tag in self.cur_tags:
            tb.apply_tag_by_name(tag, leftit, rightit)
        tb.move_mark(leftmark, rightit)

    def handle_data(self, data):
        if self.reached_body:
            self.insert(data.decode('utf8'))
    
    def handle_charref(self, name):
        raise LoadError("Got a charref %r and not expecting it." % name)
    
    def handle_entityref(self, name):
        if self.reached_body:
            self.insert(unichr(name2codepoint[name]))
    
    def close(self):
        HTMLParser.close(self)
        
        tb = self.textbuffer
        tb.delete_mark(self.leftmark)
        tb.delete_mark(self.rightmark)
