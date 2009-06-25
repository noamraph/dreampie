import gtk
from gtk import gdk

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

    def on_cut(self, widget):
        if self.sourcebuffer.get_has_selection():
            self.sourcebuffer.cut_clipboard(self.clipboard, True)
        else:
            gdk.beep()

    def on_copy(self, widget):
        if self.textbuffer.get_has_selection():
            self.textbuffer.copy_clipboard(self.clipboard)
        elif self.sourcebuffer.get_has_selection():
            self.sourcebuffer.copy_clipboard(self.clipboard)
        else:
            gdk.beep()

    def on_paste(self, widget):
        if self.sourceview.is_focus():
            self.sourcebuffer.paste_clipboard(self.clipboard, None, True)
        else:
            gdk.beep()
