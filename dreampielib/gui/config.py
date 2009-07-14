__all__ = ['Config']

import os
from ConfigParser import RawConfigParser
from StringIO import StringIO

default_config = """
[DreamPie]
font=Courier New 10
"""

class Config(object):
    """
    Manage configuration.
    config.get(key) - gets a value from the loaded file.
    config.set(key, value) - stores a value, and saves.
    """
    def __init__(self):
        self.filename = os.path.join(os.path.expanduser('~'), '.dreampie')
        self.parser = RawConfigParser()
        f = StringIO(default_config)
        self.parser.readfp(f)
        self.parser.read(self.filename)
        f = open(self.filename, 'w')
        self.parser.write(f)
        f.close()
    
    def get(self, key):
        return self.parser.get('DreamPie', key)
    
    def set(self, key, value):
        self.parser.set('DreamPie', key, value)
        f = open(self.filename, 'w')
        self.parser.write(f)
        f.close()

