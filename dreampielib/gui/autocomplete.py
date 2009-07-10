__all__ = ['Autocomplete']

import os
from os import path
import string
from logging import debug

from gtk import gdk

from .hyper_parser import HyperParser
from .autocomplete_window import AutocompleteWindow, find_prefix_range

# This string includes all chars that may be in an identifier
ID_CHARS = string.ascii_letters + string.digits + "_"

from os.path import sep
#sep = '\\'

class Autocomplete(object):
    def __init__(self, sourceview, complete_attributes, subp_abspath,
                 INDENT_WIDTH):
        self.sourceview = sourceview
        self.sourcebuffer = sourceview.get_buffer()
        self.complete_attributes = complete_attributes
        self.subp_abspath = subp_abspath
        self.INDENT_WIDTH = INDENT_WIDTH

        self.window = AutocompleteWindow(sourceview, self._on_complete)

    def show_completions(self, is_auto, complete):
        """
        If complete is False, just show the comopletion list.
        If complete is True, complete as far as possible. If there's only
        one completion, don't show the window.

        If is_auto is True, don't beep if can't find completions.
        """
        sb = self.sourcebuffer
        text = sb.get_slice(sb.get_start_iter(),
                            sb.get_end_iter()).decode('utf8')
        index = sb.get_iter_at_mark(sb.get_insert()).get_offset()
        hp = HyperParser(text, index, self.INDENT_WIDTH)

        if hp.is_in_code():
            res = self._complete_attributes(text, index, hp, is_auto)
        elif hp.is_in_string():
            res = self._complete_filenames(text, index, hp, is_auto)
        else:
            # Not in string and not in code
            res = None

        if res is not None:
            comp_prefix, public, private = res
        else:
            if not is_auto:
                gdk.beep()
            return

        combined = public + private
        combined.sort()
        start, end = find_prefix_range(combined, comp_prefix)
        if start == end:
            # No completions
            if not is_auto:
                gdk.beep()
            return

        if complete:
            # Find maximum prefix
            first = combined[start]
            last = combined[end-1]
            i = 0
            while i < len(first) and i < len(last) and first[i] == last[i]:
                i += 1
            if i > len(comp_prefix):
                sb.insert_at_cursor(first[len(comp_prefix):i])
                comp_prefix = first[:i]
            if end == start + 1:
                # Only one matchine completion - don't show the window
                return

        self.window.show(public, private, len(comp_prefix))
        
    def _complete_attributes(self, text, index, hp, is_auto):
        """
        Return (comp_prefix, public, private) - a string and two lists.
        If shouldn't complete - return None.
        """
        # Check whether autocompletion is really appropriate
        if is_auto and text[index-1] != '.':
            return
        
        i = index
        while i and text[i-1] in ID_CHARS:
            i -= 1
        comp_prefix = text[i:index]
        if i and text[i-1] == '.':
            hp.set_index(i-1)
            comp_what = hp.get_expression()
            if not comp_what:
                return
            if is_auto and '(' in comp_what:
                # Don't evaluate expressions which may contain a function call.
                return
        else:
            comp_what = ''
        public_and_private = self.complete_attributes(comp_what)
        if public_and_private is None:
            return
        public, private = public_and_private
        return comp_prefix, public, private

    def _complete_filenames(self, text, index, hp, is_auto):
        """
        Return (comp_prefix, public, private) - a string and two lists.
        If shouldn't complete - return None.
        """
        str_start = hp.bracketing[hp.indexbracket][0] + 1
        # Analyze string a bit
        pos = str_start - 1
        str_char = text[pos]
        if text[pos+1:pos+3] == str_char + str_char:
            # triple-quoted string - not for us
            return
        is_raw = pos > 0 and text[pos-1].lower() == 'r'
        if is_raw:
            pos -= 1
        is_unicode = pos > 0 and text[pos-1].lower() == 'u'
        if is_unicode:
            pos -= 1
        str_prefix = text[pos:str_start]

        # Check whether autocompletion is really appropriate
        if is_auto:
            if text[index-1] != sep:
                return
            if sep == '\\' and not is_raw:
                if not self._is_backslash_char(text, index-1):
                    return

        # Find completion start - last (real) sep
        i = index
        while True:
            i = text.rfind(sep, 0, i)
            if i == -1 or i < str_start:
                # not found - prefix is all the string.
                comp_prefix_index = str_start
                break
            if sep != '\\' or is_raw or self._is_backslash_char(text, i):
                comp_prefix_index = i+1
                break

        comp_prefix = text[comp_prefix_index:index]
        try:
            # We add a space because a backslash can't be the last
            # char of a raw string literal
            comp_what = eval(str_prefix
                             + text[str_start:comp_prefix_index]
                             + ' '
                             + str_char)[:-1]
        except SyntaxError:
            return

        abspath = self.subp_abspath(comp_what)
        if abspath is None:
            return
        try:
            dirlist = os.listdir(abspath)
        except OSError:
            return
        dirlist.sort()
        public = []
        private = []
        for name in dirlist:
            if is_unicode and isinstance(name, str):
                # A filename which can't be unicode
                continue
            if not is_unicode:
                # We need a unicode string. From what I see, Python evaluates
                # unicode characters in byte strings as utf-8.
                try:
                    name = name.decode('utf8')
                except UnicodeDecodeError:
                    continue
            # skip troublesome names
            try:
                rename = eval(str_prefix + name + str_char)
            except (SyntaxError, UnicodeDecodeError):
                continue
            if rename != name:
                continue

            is_dir = os.path.isdir(os.path.join(abspath, name))

            if not is_dir:
                name += str_char
            else:
                if sep == '\\' and not is_raw:
                    name += '\\\\'
                else:
                    name += sep

            if name.startswith('.'):
                private.append(name)
            else:
                public.append(name)

        return comp_prefix, public, private
    
    def _on_complete(self):
        # Called when the user completed. This is relevant if he completed
        # a dir name, so that another completion window will be opened.
        self.show_completions(is_auto=True, complete=False)
        
    @staticmethod
    def _is_backslash_char(string, index):
        """
        Assuming that string[index] is a backslash, check whether it's a
        real backslash char or just an escape - if it has an odd number of
        preceding backslashes it's a real backslash
        """
        assert string[index] == '\\'
        count = 0
        while index-count > 0 and string[index-count-1] == '\\':
            count += 1
        return (count % 2) == 1
