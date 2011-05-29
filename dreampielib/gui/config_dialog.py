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

__all__ = ['ConfigDialog']

import re

import gobject
import gtk
from gtk import gdk
import gtksourceview2
import pango

from .SimpleGladeApp import SimpleGladeApp
from . import tags
from .tags import DEFAULT, FG, BG, COLOR, ISSET
from .common import beep, get_text
from .file_dialogs import open_dialog

# Allow future translations
_ = lambda s: s

class ConfigDialog(SimpleGladeApp):
    def __init__(self, config, gladefile, parent):
        self.is_initializing = True
        SimpleGladeApp.__init__(self, gladefile, 'config_dialog')
        
        self.config_dialog.set_transient_for(parent)
        
        self.config = config
        
        self.fontsel.props.font_name = config.get('font')
        self.cur_font = self.fontsel.props.font_name
        
        self.pprint_chk.props.active = config.get_bool('pprint')
        
        self.reshist_chk.props.active = config.get_bool('use-reshist')
        self.on_reshist_chk_toggled(self.reshist_chk)
        self.reshist_spin.props.value = config.get_int('reshist-size')
        
        self.autofold_chk.props.active = config.get_bool('autofold')
        self.on_autofold_chk_toggled(self.autofold_chk)
        self.autofold_spin.props.value = config.get_int('autofold-numlines')
        
        self.viewer_entry.props.text = eval(config.get('viewer'))
        
        self.autoparen_chk.props.active = config.get_bool('autoparen')
        self.expects_str_entry.props.text = config.get('expects-str-2')
        
        self.vertical_layout_rad.props.active = config.get_bool('vertical-layout')
        self.horizontal_layout_rad.props.active = not config.get_bool('vertical-layout')
        
        self.leave_code_chk.props.active = config.get_bool('leave-code')
        
        self.hide_defs_chk.props.active = config.get_bool('hide-defs')
        
        switch = config.get_bool('matplotlib-ia-switch')
        warn = config.get_bool('matplotlib-ia-warn')
        if switch:
            self.matplotlib_ia_switch_rad.props.active = True
        elif warn:
            self.matplotlib_ia_warn_rad.props.active = True
        else:
            self.matplotlib_ia_ignore_rad.props.active = True
    
        self.ask_on_quit_chk.props.active = config.get_bool('ask-on-quit')
    
        self.themes = dict((name, tags.get_theme(config, name))
                           for name in tags.get_theme_names(config))
        self.cur_theme = self.themes[config.get('current-theme')]

        self.fg_default_rad.set_group(self.fg_special_rad)
        self.bg_default_rad.set_group(self.bg_special_rad)

        TYPE_STRING = gobject.TYPE_STRING
        self.themes_list = gtk.ListStore(TYPE_STRING)
        self.themes_trv.set_model(self.themes_list)
        self.init_themes_list()
        
        # tag, desc, fg, bg
        self.elements_list = gtk.ListStore(TYPE_STRING, TYPE_STRING,
                                           TYPE_STRING, TYPE_STRING)
        self.elements_trv.set_model(self.elements_list)
        # cur_tag is the currently selected tag. It is set to None when props
        # are changed, to mark that they weren't changed as a result of a user
        # action.
        self.cur_tag = None
        self.init_elements_list()

        self.textbuffer = self.textview.get_buffer()
        self.init_textview()

        self.sourcebuffer = gtksourceview2.Buffer()
        self.sourceview = gtksourceview2.View(self.sourcebuffer)
        self.sourcebuffer.set_text(eval(config.get('init-code')))
        self.init_sourceview()
        
        self.font_changed()
        self.theme_changed()
        
        self.is_initializing = False

    def run(self):
        while True:
            r = self.config_dialog.run()
            if r != gtk.RESPONSE_OK:
                return r
            expects_str = self.expects_str_entry.props.text.decode('utf8').strip()
            is_ident = lambda s: re.match(r'[A-Za-z_][A-Za-z0-9_]*$', s)
            if not all(is_ident(s) for s in expects_str.split()):
                warning = _("All names in the auto-quote list must be legal "
                            "Python identifiers and be separated by spaces.")
                msg = gtk.MessageDialog(self.config_dialog, gtk.DIALOG_MODAL,
                                        gtk.MESSAGE_WARNING, gtk.BUTTONS_CLOSE,
                                        warning)
                _response = msg.run()
                msg.destroy()
                self.expects_str_entry.grab_focus()
                continue
            
            # r == gtk.RESPONSE_OK and everything is ok.
            break
        
        config = self.config

        config.set('font', self.fontsel.props.font_name)
        
        config.set_bool('pprint', self.pprint_chk.props.active)
        
        config.set_bool('use-reshist', self.reshist_chk.props.active)
        config.set_int('reshist-size', self.reshist_spin.props.value)
        
        config.set_bool('autofold', self.autofold_chk.props.active)
        config.set_int('autofold-numlines', self.autofold_spin.props.value)
        
        config.set('viewer', repr(self.viewer_entry.props.text.decode('utf8').strip()))
        
        config.set_bool('autoparen', self.autoparen_chk.props.active)
        config.set('expects-str-2', expects_str)
        
        config.set_bool('vertical-layout', self.vertical_layout_rad.props.active)
        
        config.set_bool('leave-code', self.leave_code_chk.props.active)
        
        config.set_bool('hide-defs', self.hide_defs_chk.props.active)
        
        if self.matplotlib_ia_switch_rad.props.active:
            switch = True
            warn = False
        elif self.matplotlib_ia_warn_rad.props.active:
            switch = False
            warn = True
        else:
            switch = warn = False
        config.set_bool('matplotlib-ia-switch', switch)
        config.set_bool('matplotlib-ia-warn', warn)
        
        config.set_bool('ask-on-quit', self.ask_on_quit_chk.props.active)
        
        sb = self.sourcebuffer
        init_code = get_text(sb, sb.get_start_iter(), sb.get_end_iter())
        config.set('init-code', repr(init_code))
        
        tags.remove_themes(config)
        for name, theme in self.themes.iteritems():
            tags.set_theme(config, name, theme)
        cur_theme_name = [name for name, theme in self.themes.iteritems()
                          if theme is self.cur_theme][0]
        config.set('current-theme', cur_theme_name)

        config.save()
        return r # gtk.RESPONSE_OK
    
    def destroy(self):
        self.config_dialog.destroy()
    
    def init_themes_list(self):
        ttv = self.themes_trv; tl = self.themes_list
        for name in self.themes:
            tl.append((name,))
        cr = gtk.CellRendererText()
        cr.props.editable = True
        cr.connect('edited', self.on_theme_renamed)
        ttv.insert_column_with_attributes(0, 'Theme Name', cr, text=0)
        tl.set_sort_column_id(0, gtk.SORT_ASCENDING)
        for i, row in enumerate(tl):
            name = row[0]
            if self.themes[name] is self.cur_theme:
                ttv.set_cursor((i,))
                break
        else:
            assert False, "Didn't find the current theme"
        self.del_theme_btn.props.sensitive = (len(tl) > 1)

    def init_elements_list(self):
        etv = self.elements_trv; el = self.elements_list
        for i, (tag, desc) in enumerate(tags.tag_desc):
            el.insert(i, (tag, desc, None, None))
        letter = gtk.CellRendererText()
        letter.props.text = 'A'
        etv.insert_column_with_attributes(0, 'Preview', letter,
                                          foreground=2, background=3)
        name = gtk.CellRendererText()
        etv.insert_column_with_attributes(1, 'Element Name', name,
                                          text=1)
        etv.set_cursor((0,)) # Default

    def init_textview(self):
        from .tags import (STDIN, STDOUT, STDERR, EXCEPTION, PROMPT, MESSAGE,
                           FOLD_MESSAGE, RESULT_IND, RESULT,
                           KEYWORD, BUILTIN, STRING, NUMBER, COMMENT)
        tb = self.textbuffer
        tags.add_tags(tb)
        def w(s, *tags):
            tb.insert_with_tags_by_name(tb.get_end_iter(), s, *tags)
        w('>>>', PROMPT); w(' '); w('# You can click here', COMMENT); w('\n')
        w('...', PROMPT); w(' '); w('# to choose elements!', COMMENT); w('\n')
        w('...', PROMPT); w(' '); w('def', KEYWORD); w(' add1():\n')
        w('...', PROMPT); w('     num = '); w('input', BUILTIN); w('()\n')
        w('...', PROMPT); w('     '); w('print', KEYWORD); w(' '); \
            w('"What about"', STRING); w(', num+'); w('1', NUMBER); w('\n')
        w('...', PROMPT); w('     '); w('return', KEYWORD); w(' num ** '); \
            w('2', NUMBER); w('\n')
        w('...', PROMPT); w(' add1()\n')
        w('5\n', STDIN)
        w('What about 6\n', STDOUT)
        w('0: ', RESULT_IND); w('25', RESULT); w('\n')
        w('====== New Session ======\n', MESSAGE)
        w('>>>', PROMPT); w(' '); w('from', KEYWORD); w(' sys '); \
            w('import', KEYWORD); w(' stderr\n')
        w('...', PROMPT); w(' '); w('print', KEYWORD); w(' >> stderr, '); \
            w(r'"err\n"', STRING); w(', '); w('1', NUMBER); w('/'); \
            w('0', NUMBER); w('\n')
        w('err\n', STDERR)
        w('Traceback (most recent call last):\n', EXCEPTION)
        w('[About 4 more lines.]', FOLD_MESSAGE)

    def on_textview_realize(self, _widget):
        win = self.textview.get_window(gtk.TEXT_WINDOW_TEXT)
        win.set_cursor(None)
    
    def init_sourceview(self):
        sv = self.sourceview; sb = self.sourcebuffer
        lm = gtksourceview2.LanguageManager()
        python = lm.get_language('python')
        sb.set_language(python)
        self.scrolledwindow_sourceview.add(sv)
        sv.show()

    def font_changed(self):
        # Called when the font was changed, and elements need to be updated
        font = pango.FontDescription(self.cur_font)
        self.textview.modify_font(font)
        self.sourceview.modify_font(font)

    def theme_changed(self):
        # Called when the theme was changed, and elements need to be updated

        theme = self.cur_theme

        tags.apply_theme_text(self.textview, self.textbuffer, theme)
        tags.apply_theme_source(self.sourcebuffer, theme)

        el = self.elements_list
        for i, (tag, _desc) in enumerate(tags.tag_desc):
            el[i][2] = tags.get_actual_color(theme, tag, FG)
            el[i][3] = tags.get_actual_color(theme, tag, BG)
        
        self.update_color_sel_widgets()

    def on_elements_trv_cursor_changed(self, _widget):
        (row,), _col = self.elements_trv.get_cursor()
        self.cur_tag = tags.tag_desc[row][0]
        self.update_color_sel_widgets()

    def update_color_sel_widgets(self):
        tag = self.cur_tag
        # Set cur_tag to None to mark that changes are not the result of user
        # interaction
        self.cur_tag = None

        theme = self.cur_theme
        if tag == DEFAULT:
            self.fg_special_rad.props.active = True
            self.fg_default_rad.props.active = False
            self.fg_default_rad.props.sensitive = False
            self.bg_special_rad.props.active = True
            self.bg_default_rad.props.active = False
            self.bg_default_rad.props.sensitive = False
        else:
            self.fg_special_rad.props.active = theme[tag, FG, ISSET]
            self.fg_default_rad.props.active = not theme[tag, FG, ISSET]
            self.fg_default_rad.props.sensitive = True
            self.bg_special_rad.props.active = theme[tag, BG, ISSET]
            self.bg_default_rad.props.active = not theme[tag, BG, ISSET]
            self.bg_default_rad.props.sensitive = True
        
        self.fg_cbut.props.color = gdk.color_parse(theme[tag, FG, COLOR])
        self.bg_cbut.props.color = gdk.color_parse(theme[tag, BG, COLOR])
        
        self.cur_tag = tag

    def on_viewer_button_clicked(self, _widget):
        def f(filename):
            self.viewer_entry.props.text = filename
        open_dialog(f, _('Choose the viewer program'), self.config_dialog,
                    _('Executables'), '*')
    
    def on_textview_button_press_event(self, _widget, event):
        tv = self.textview
        if tv.get_window(gtk.TEXT_WINDOW_TEXT) is not event.window:
            # Probably a click on the border or something
            return
        x, y = tv.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
                                          int(event.x), int(event.y))
        it = tv.get_iter_at_location(x, y)
        it_tags = it.get_tags()
        if not it_tags:
            tag_index = 0 # Default
        else:
            tag_name = it_tags[-1].props.name
            for i, (tag, _desc) in enumerate(tags.tag_desc):
                if tag == tag_name:
                    tag_index = i
                    break
            else:
                tag_index = 0
        self.elements_trv.set_cursor((tag_index,))

    @staticmethod
    def _format_color(color):
        return '#%04x%04x%04x' % (color.red, color.green, color.blue)
    
    def on_fg_special_rad_toggled(self, _widget):
        is_special = self.fg_special_rad.props.active
        self.fg_cbut.props.sensitive = is_special
        
        if self.cur_tag:
            self.cur_theme[self.cur_tag, FG, ISSET] = is_special
            self.theme_changed()

    def on_fg_cbut_color_set(self, _widget):
        if self.cur_tag:
            color = self._format_color(self.fg_cbut.props.color)
            self.cur_theme[self.cur_tag, FG, COLOR] = color
            self.theme_changed()

    def on_bg_special_rad_toggled(self, _widget):
        is_special = self.bg_special_rad.props.active
        self.bg_cbut.props.sensitive = is_special
        
        if self.cur_tag:
            self.cur_theme[self.cur_tag, BG, ISSET] = is_special
            self.theme_changed()

    def on_bg_cbut_color_set(self, _widget):
        if self.cur_tag:
            color = self._format_color(self.bg_cbut.props.color)
            self.cur_theme[self.cur_tag, BG, COLOR] = color
            self.theme_changed()

    def on_themes_trv_cursor_changed(self, _widget):
        if self.is_initializing:
            return
        ttv = self.themes_trv; tl = self.themes_list
        path, _col = ttv.get_cursor()
        cur_name = tl[path][0]
        self.cur_theme = self.themes[cur_name]
        self.theme_changed()                

    def on_copy_theme_btn_clicked(self, _widget):
        ttv = self.themes_trv; tl = self.themes_list
        path, _col = ttv.get_cursor()
        cur_name = tl[path][0]
        i = 2
        while True:
            new_name = '%s %d' % (cur_name, i)
            if new_name not in self.themes:
                break
            i += 1
        self.themes[new_name] = self.cur_theme = dict(self.themes[cur_name])
        tl.append((new_name,))
        self.del_theme_btn.props.sensitive = True
        tl.set_sort_column_id(0, gtk.SORT_ASCENDING)
        cur_index = [i for i, row in enumerate(tl) if row[0] == new_name][0]
        ttv.set_cursor(cur_index, ttv.get_column(0), start_editing=True)
        self.theme_changed()

    def on_del_theme_btn_clicked(self, _widget):
        self.delete_theme()

    def on_themes_trv_key_press_event(self, _widget, event):
        if gdk.keyval_name(event.keyval) == 'Delete':
            if len(self.themes_list) < 2:
                beep()
            else:
                self.delete_theme()
    
    def delete_theme(self):
        ttv = self.themes_trv; tl = self.themes_list
        assert len(tl) > 1
        path, _col = ttv.get_cursor()
        cur_name = tl[path][0]
        del self.themes[cur_name]
        del tl[path]
        ttv.set_cursor(0)
        self.cur_theme = self.themes[tl[0][0]]
        self.theme_changed()
        if len(tl) < 2:
            self.del_theme_btn.props.sensitive = False

    def on_theme_renamed(self, _widget, path, new_name):
        tl = self.themes_list
        if new_name == tl[path][0]:
            # The name wasn't changed
            return
        if new_name in [row[0] for row in tl]:
            beep()
            return False
        cur_name = tl[path][0]
        theme = self.themes.pop(cur_name)
        self.themes[new_name] = theme
        tl[path][0] = new_name

    def on_notebook_switch_page(self, _widget, _page, _page_num):
        # This should have been on the FontSelection signal, but there isn't
        # one.
        if self.cur_font != self.fontsel.props.font_name:
            self.cur_font = self.fontsel.props.font_name
            self.font_changed()

    def on_reshist_chk_toggled(self, _widget):
        self.reshist_spin.props.sensitive = self.reshist_chk.props.active
    
    def on_autofold_chk_toggled(self, _widget):
        self.autofold_spin.props.sensitive = self.autofold_chk.props.active

    def on_autoparen_chk_toggled(self, _widget):
        self.expects_str_alignment.props.sensitive = self.autoparen_chk.props.active
