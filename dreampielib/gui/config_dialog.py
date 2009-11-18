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

import gtk

from .SimpleGladeApp import SimpleGladeApp

class ConfigDialog(SimpleGladeApp):
    def __init__(self, config, gladefile):
        SimpleGladeApp.__init__(self, gladefile, 'config_dialog')
        
        self.config = config
        
        self.fontsel.props.font_name = config.get('font')
        
        self.pprint_chk.props.active = config.get_bool('pprint')
        
        self.cache_chk.props.active = config.get_bool('use-cache')
        self.on_cache_chk_toggled(self.cache_chk)
        self.cache_spin.props.value = config.get_int('cache-size')
        
        self.leave_code_chk.props.active = config.get_bool('leave-code')
        
        self.hide_defs_chk.props.active = config.get_bool('hide-defs')
    
    def run(self):
        r = self.config_dialog.run()
        if r != gtk.RESPONSE_OK:
            return r
        
        config = self.config

        config.set('font', self.fontsel.props.font_name)
        
        config.set_bool('pprint', self.pprint_chk.props.active)
        
        config.set_bool('use-cache', self.cache_chk.props.active)
        config.set_int('cache-size', self.cache_spin.props.value)
        
        config.set_bool('leave-code', self.leave_code_chk.props.active)
        
        config.set_bool('hide-defs', self.hide_defs_chk.props.active)
        
        config.save()
        return r # gtk.RESPONSE_OK
    
    def destroy(self):
        self.config_dialog.destroy()
    
    def on_cache_chk_toggled(self, widget):
        self.cache_spin.props.sensitive = self.cache_chk.props.active
    
