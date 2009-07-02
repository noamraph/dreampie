__all__ = ['Autocomplete']

import string
from logging import debug

from gtk import gdk

from .hyper_parser import HyperParser
from .autocomplete_window import AutocompleteWindow, find_prefix_range

# This string includes all chars that may be in an identifier
ID_CHARS = string.ascii_letters + string.digits + "_"

class Autocomplete(object):
    def __init__(self, sourceview, call_subp, INDENT_WIDTH):
        self.sourceview = sourceview
        self.sourcebuffer = sourceview.get_buffer()
        self.call_subp = call_subp
        self.INDENT_WIDTH = INDENT_WIDTH

        self.window = AutocompleteWindow(sourceview)

    def show_completions(self, auto, complete):
        """
        If complete is False, just show the comopletion list.
        If complete is True, complete as far as possible. If there's only
        one completion, don't show the window.

        If auto is True, don't beep if can't find completions.
        """
        sb = self.sourcebuffer
        text = sb.get_slice(sb.get_start_iter(),
                            sb.get_end_iter()).decode('utf8')
        index = sb.get_iter_at_mark(sb.get_insert()).get_offset()
        hp = HyperParser(text, index, self.INDENT_WIDTH)

        if hp.is_in_code():
            i = index
            while i and text[i-1] in ID_CHARS:
                i -= 1
            comp_prefix = text[i:index]
            if i and text[i-1] == '.':
                hp.set_index(i-1)
                comp_what = hp.get_expression()
                if not comp_what:
                    if not auto:
                        gdk.beep()
                    return
            else:
                comp_what = ''
        else:
            if not auto:
                gdk.beep()
            return

        public, private = self.call_subp('complete_attributes', comp_what)
        
        combined = public + private
        combined.sort()
        start, end = find_prefix_range(combined, comp_prefix)
        if start == end:
            # No completions
            if not auto:
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
        
