class StatusBar(object):
    """
    Add messages to the status bar which disappear when the contents is changed.
    """
    def __init__(self, sourcebuffer, statusbar):
        self.sourcebuffer = sourcebuffer
        self.statusbar = statusbar
        
        # id of a message displayed in the status bar to be removed when
        # the contents of the source buffer is changed
        self.sourcebuffer_status_id = None
        self.sourcebuffer_changed_handler_id = None

    def set_status(self, message):
        """Set a message in the status bar to be removed when the contents
        of the source buffer is changed"""
        if self.sourcebuffer_status_id is not None:
            self.clear_status(None)
        self.sourcebuffer_status_id = self.statusbar.push(0, message)
        self.sourcebuffer_changed_handler_id = \
            self.sourcebuffer.connect('changed', self.clear_status)

    def clear_status(self, widget):
        self.statusbar.remove(0, self.sourcebuffer_status_id)
        self.sourcebuffer_status_id = None
        self.sourcebuffer.disconnect(self.sourcebuffer_changed_handler_id)
        self.sourcebuffer_changed_handler_id = None
        
