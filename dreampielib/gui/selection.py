__all__ = ['Selection']

import gtk
from gtk import gdk

from .tags import COMMAND, PROMPT

class Selection(object):
    """
    Handle clipboard events.
    When something is selected, "Copy" should be enabled. When nothing is
    selected, "Interrupt" should be enabled.
    Also, "copy only commands" command.
    """
    def __init__(self, textview, sourceview,
                 on_is_something_selected_changed):
        self.textview = textview
        self.textbuffer = textview.get_buffer()
        self.sourceview = sourceview
        self.sourcebuffer = sourceview.get_buffer()
        self.on_is_something_selected_changed = on_is_something_selected_changed
        
        self.primary_selection = gtk.Clipboard(selection=gdk.SELECTION_PRIMARY)
        self.primary_selection.connect('owner-change',
                                       self.on_selection_changed)
        self.clipboard = gtk.Clipboard()

    def on_selection_changed(self, clipboard, event):
        is_something_selected = (self.textbuffer.get_has_selection()
                                 or self.sourcebuffer.get_has_selection())
        self.on_is_something_selected_changed(is_something_selected)

    def cut(self):
        if self.sourcebuffer.get_has_selection():
            self.sourcebuffer.cut_clipboard(self.clipboard, True)
        else:
            gdk.beep()

    def copy(self):
        if self.textbuffer.get_has_selection():
            self.textbuffer.copy_clipboard(self.clipboard)
        elif self.sourcebuffer.get_has_selection():
            self.sourcebuffer.copy_clipboard(self.clipboard)
        else:
            gdk.beep()

    def copy_only_commands(self):
        if self.sourcebuffer.get_has_selection():
            self.sourcebuffer.copy_clipboard(self.clipboard)
            return
        if not self.textbuffer.get_has_selection():
            gdk.beep()
            return
        # We need to copy the text which has the COMMAND tag, doesn't have
        # the PROMPT tag, and is selected.
        # We need to remember that the trailing newline of commands isn't
        # marked, but we need to copy it.
        tb = self.textbuffer
        command = tb.get_tag_table().lookup(COMMAND)
        prompt = tb.get_tag_table().lookup(PROMPT)
        r = []
        it, sel_end = tb.get_selection_bounds()
        reached_end = False
        while not reached_end:
            it2 = it.copy()
            it2.forward_to_tag_toggle(None)
            if it2.compare(sel_end) >= 0:
                it2 = sel_end.copy()
                reached_end = True
            if it.has_tag(command) and not it.has_tag(prompt):
                r.append(tb.get_text(it, it2).decode('utf8'))
                if (not reached_end
                    and not it2.has_tag(command)
                    and it2.get_char() == '\n'):
                    
                    r.append('\n')
            it = it2
        r = ''.join(r)
        if not r:
            gdk.beep()
        else:
            self.clipboard.set_text(r)

    def paste(self):
        if self.sourceview.is_focus():
            self.sourcebuffer.paste_clipboard(self.clipboard, None, True)
        else:
            gdk.beep()
