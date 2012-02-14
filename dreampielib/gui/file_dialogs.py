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

__all__ = ['open_dialog', 'save_dialog']

"""
Easy to use wrappers around GTK file dialogs.
"""

import os
from os.path import abspath, dirname, basename, exists

import gtk

# Support translation in the future
_ = lambda s: s

def open_dialog(func, title, parent, filter_name, filter_pattern):
    """
    Display the Open dialog.
    func - a function which gets a file name and does something. If it throws
        an IOError, it will be catched and the user will get another chance.
    title - window title
    parent - parent window, or None
    filter_name - "HTML Files"
    filter_pattern - "*.html"
    """
    d = gtk.FileChooserDialog(
        title, parent,
        gtk.FILE_CHOOSER_ACTION_OPEN,
        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
         gtk.STOCK_OK, gtk.RESPONSE_OK))
    fil = gtk.FileFilter()
    fil.set_name(filter_name)
    fil.add_pattern(filter_pattern)
    d.add_filter(fil)
    while True:
        r = d.run()
        if r != gtk.RESPONSE_OK:
            break
        filename = abspath(d.get_filename().decode('utf8'))
        try:
            func(filename)
        except IOError, e:
            m = gtk.MessageDialog(d, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING,
                                    gtk.BUTTONS_OK)
            m.props.text = _('Error when loading file: %s') % e
            m.run()
            m.destroy()
        else:
            break
    d.destroy()

def save_dialog(func, title, parent, filter_name, filter_pattern, auto_ext=None,
                prev_dir=None, prev_name=None):
    """
    Display the Save As dialog.
    func - a function which gets a file name and does something. If it throws
        an IOError, it will be catched and the user will get another chance.
    title - window title
    parent - parent window, or None
    filter_name - "HTML Files"
    filter_pattern - "*.html"
    auto_ext - "html", if not None will be added if no extension given.
    prev_dir, prev_name - will set the default if given.
    
    Return True if file was saved.
    """
    d = gtk.FileChooserDialog(
        title, parent,
        gtk.FILE_CHOOSER_ACTION_SAVE,
        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
         gtk.STOCK_OK, gtk.RESPONSE_OK))
    fil = gtk.FileFilter()
    fil.set_name(filter_name)
    fil.add_pattern(filter_pattern)
    d.add_filter(fil)
    if prev_dir:
        d.set_current_folder(prev_dir)
    if prev_name:
        d.set_current_name(prev_name)
    saved = False
    while True:
        r = d.run()
        if r != gtk.RESPONSE_OK:
            break
        filename = abspath(d.get_filename()).decode('utf8')
        if auto_ext and not os.path.splitext(filename)[1]:
            filename += os.path.extsep + auto_ext
        if exists(filename):
            m = gtk.MessageDialog(d, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION)
            m.props.text = _('A file named "%s" already exists.  Do '
                                'you want to replace it?'
                                ) % basename(filename)
            m.props.secondary_text = _(
                'The file already exists in "%s".  Replacing it will '
                'overwrite its contents.'
                ) % basename(dirname(filename))
            m.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
            m.add_button(_('_Replace'), gtk.RESPONSE_OK)
            m.set_default_response(gtk.RESPONSE_CANCEL)
            mr = m.run()
            m.destroy()
            if mr == gtk.RESPONSE_CANCEL:
                continue
                
        try:
            func(filename)
        except IOError, e:
            m = gtk.MessageDialog(d, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING,
                                  gtk.BUTTONS_OK)
            m.props.text = _('Error when saving file: %s') % e
            m.run()
            m.destroy()
        else:
            saved = True
            break
    d.destroy()
    return saved