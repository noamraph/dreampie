class VAdjToBottom(object):
    """
    Scroll automatically to the bottom of the VAdj if the height changes
    and it was at bottom
    """
    def __init__(self, vadj):
        self.vadj = vadj
        vadj.connect('changed', self.on_changed)
        vadj.connect('value-changed', self.on_value_changed)
        self.vadj_was_at_bottom = self.is_at_bottom()
        self.scroll_to_bottom()

    def is_at_bottom(self):
        return self.vadj.value == self.vadj.upper - self.vadj.page_size

    def scroll_to_bottom(self):
        self.vadj.set_value(self.vadj.upper - self.vadj.page_size)

    def on_changed(self, widget):
        if self.vadj_was_at_bottom and not self.is_at_bottom():
            self.scroll_to_bottom()
        self.vadj_was_at_bottom = self.is_at_bottom()

    def on_value_changed(self, widget):
        self.vadj_was_at_bottom = self.is_at_bottom()
