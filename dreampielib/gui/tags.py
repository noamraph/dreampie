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

"""
Tags for the textview and sourceview.
"""

import os
import tempfile

from gtk import gdk
import gtksourceview2

# DEFAULT is not really a tag, but it means the default text colors
DEFAULT = 'default'

# Tags for marking output
OUTPUT = 'output'
STDIN = 'stdin'; STDOUT = 'stdout'; STDERR = 'stderr'; EXCEPTION = 'exception'
RESULT_IND = 'result-ind'; RESULT = 'result'

# Tags for marking commands
PROMPT = 'prompt'; COMMAND = 'command'; COMMAND_DEFS='command-defs'
COMMAND_SEP = 'commandsep'

# Folding tags
FOLDED = 'folded'
FOLD_MESSAGE = 'fold-message'

# The MESSAGE tag
MESSAGE = 'message'

# Tags for syntax highlighting
KEYWORD = 'keyword'; BUILTIN = 'builtin'; STRING = 'string'
NUMBER = 'number'; COMMENT = 'comment'; BRACKET_MATCH = 'bracket-match'
BRACKET_1 = 'bracket-1'; BRACKET_2 = 'bracket-2'; BRACKET_3 = 'bracket-3'
ERROR = 'error'

# Constants to retrieve data from a theme. A theme is just a dict which maps
# tuples to strings, and is used like this: 
# theme[KEYWORD, FG, COLOR], theme[COMMENT, BG, ISSET]
FG = 'fg'; BG = 'bg'
COLOR = 'color'; ISSET = 'isset'

# Add this string to theme names to get the config section
THEME_POSTFIX = ' theme'

# Tags which affect appearence
tag_desc = [
    (DEFAULT, 'Default'),

    (KEYWORD, 'Keyword'),
    (BUILTIN, 'Builtin'),
    (STRING, 'String'),
    (NUMBER, 'Number'),
    (COMMENT, 'Comment'),
    (BRACKET_MATCH, 'Bracket Match'),
    (BRACKET_1, 'Bracket 1'),
    (BRACKET_2, 'Bracket 2'),
    (BRACKET_3, 'Bracket 3'),
    (ERROR, 'Error'),
    
    (STDIN, 'Standard Input'),
    (STDOUT, 'Standard Output'),
    (STDERR, 'Standard Error'),
    (RESULT, 'Result'),
    (RESULT_IND, 'Result Index'),
    (EXCEPTION, 'Exception'),
    (PROMPT, 'Prompt'),
    (MESSAGE, 'Messages'),
    (FOLD_MESSAGE, 'Folded Text'),
    ]

"""
Some documentation about what's going on in the text buffer
-----------------------------------------------------------

The text buffer has two purposes: to show the user what he expects, and to
store all the information needed about the history. So here I try to document
what's going on there.

Most tags can be considered to only affect the highlight color. Here only the
tags which affect the data model are described.

The COMMAND tag is applied to code segments. The last newline is also tagged.
After it comes a '\r' char marked with COMMAND_SEP, so it's invisible. It's
used to separate two code segments even if there was no output in
between. The prompt is marked with both the COMMAND and the PROMPT tag, so the
Copy Code Only action copies only text which is marked by COMMAND and not by
PROMPT (and adds a trailing newline.) lines inside def and class blocks are
also marked with COMMAND_DEFS, so they can be hidden if the user wants to.

STDIN is marked as STDIN, COMMAND and OUTPUT. It always ends with a \n. It is
marked with COMMAND so that it will be history-searched. It is marked with
OUTPUT so that it will be considered as output for folding purposes.

The MESSAGE tag tags a message which is displayed at the beginning of each
session (that is, subprocess). It's either the welcome message (Python version),
a "New Session" message or a "History Discarded" message. When you discard
previous sessions, the MESSAGE tag is used to understand what are the previous
sessions.

Text marked with OUTPUT was written by output.py. It includes stdout, stderr,
result and exception. This text is written at the *output mark*, which means
that if an output is produced after the code execution was finished (for
example, by another thread), it will appear before the prompt. Also, ANSI
escapes are removed. '\r' (carriage return) is handled (to a point - there's
no support for having a part of a line overwritten - after a line starts to be
overwritten, it's completely removed). When lines are too long (too many chars
without a '\n', they are broken to a certain maximum length by '\r' chars.
Original '\r' chars will never pass to the text buffer. These '\r' chars are
treated by the text buffer just like '\n' chars, but are not copied, because
they are not real chars - they were only inserted so that the text buffer won't
become unresponsive. If there are enough lines in an output section, it gets
automatically collapsed. There's always a '\n' after the output section which
is marked as OUTPUT (unless nothing was written, which is not really an
output section.)

Folded output/code sections look like this:

First few characters of the output/code section, which are truncated somewhe
(The rest of the section, tagged with FOLDED so invisible)
[About n more lines. Double-click to unfold]

* From some point (which will be a '\n' if the first line isn't too long), the
  output is marked with FOLDED, so it is invisible.
* The '\n' which always comes at the end of the output is also invisible. It
  doesn't make a lot of sense, because that way no newline is visible, but it
  turns out that if it's visible, you get an extra empty line.
* Afterwards comes the FOLD_MESSAGE, which includes a '\n' at the end so that
  the background color is behind the entire line.
"""

def get_theme_names(config):
    for section in config.sections():
        if section.endswith(THEME_POSTFIX):
            if config.get_bool('is-active', section):
                yield section[:-len(THEME_POSTFIX)]

def get_theme(config, theme_name):
    """
    Get a theme description (a dict of tuples, see above) from a config object.
    """
    section = theme_name + THEME_POSTFIX
    if not config.get_bool('is-active', section):
        raise ValueError("Theme %s is not active" % theme_name)
    theme = {}
    for tag, _desc in tag_desc:
        theme[tag, FG, COLOR] = config.get('%s-fg' % tag, section)
        theme[tag, BG, COLOR] = config.get('%s-bg' % tag, section)
        if tag != DEFAULT:
            theme[tag, FG, ISSET] = config.get_bool('%s-fg-set' % tag, section)
            theme[tag, BG, ISSET] = config.get_bool('%s-bg-set' % tag, section)
    return theme

def set_theme(config, theme_name, theme):
    """
    Write a theme description to a config object.
    """
    section = theme_name + THEME_POSTFIX
    if not config.has_section(section):
        config.add_section(section)
    config.set_bool('is-active', True, section)
    for tag, _desc in tag_desc:
        config.set('%s-fg' % tag, theme[tag, FG, COLOR], section)
        config.set('%s-bg' % tag, theme[tag, BG, COLOR], section)
    for tag, _desc in tag_desc:
        if tag != DEFAULT:
            config.set_bool('%s-fg-set' % tag, theme[tag, FG, ISSET], section)
            config.set_bool('%s-bg-set' % tag, theme[tag, BG, ISSET], section)

def remove_themes(config):
    """
    Remove all themes.
    """
    for name in get_theme_names(config):
        # We replace the section with a section with 'is-active = False', so
        # that if the section is updated from default configuration values
        # it will not reappear.
        section = name + THEME_POSTFIX
        config.remove_section(section)
        config.add_section(section)
        config.set_bool('is-active', False, section)

def get_actual_color(theme, tag, fg_or_bg):
    """
    Get the actual color that will be displayed - taking ISSET into account.
    """
    if tag == DEFAULT or theme[tag, fg_or_bg, ISSET]:
        return theme[tag, fg_or_bg, COLOR]
    else:
        return theme[DEFAULT, fg_or_bg, COLOR]

def add_tags(textbuffer):
    """
    Add the needed tags to a textbuffer
    """
    for tag, _desc in tag_desc:
        if tag != DEFAULT:
            textbuffer.create_tag(tag)
    textbuffer.create_tag(OUTPUT)
    textbuffer.create_tag(COMMAND)
    textbuffer.create_tag(COMMAND_DEFS)
    tag = textbuffer.create_tag(COMMAND_SEP)
    tag.props.invisible = True
    tag = textbuffer.create_tag(FOLDED)
    tag.props.invisible = True

def apply_theme_text(textview, textbuffer, theme):
    """
    Apply the theme to the textbuffer. add_tags should have been called
    previously.
    """
    for tag, _desc in tag_desc:
        if tag == DEFAULT:
            textview.modify_base(0, gdk.color_parse(theme[tag, BG, COLOR]))
            textview.modify_text(0, gdk.color_parse(theme[tag, FG, COLOR]))
        else:
            tt = textbuffer.get_tag_table().lookup(tag)
            tt.props.foreground = theme[tag, FG, COLOR]
            tt.props.foreground_set = theme[tag, FG, ISSET]
            tt.props.background = theme[tag, BG, COLOR]
            tt.props.background_set = theme[tag, BG, ISSET]
            tt.props.paragraph_background = theme[tag, BG, COLOR]
            tt.props.paragraph_background_set = theme[tag, BG, ISSET]

def _make_style_scheme(spec):
    # Quite stupidly, there's no way to create a SourceStyleScheme without
    # reading a file from a search path. So this function creates a file in
    # a directory, to get you your style scheme.
    #
    # spec should be a dict of dicts, mapping style names to (attribute, value)
    # pairs. Color values will be converted using gdk.color_parse().
    # Boolean values will be handled correctly.
    dir = tempfile.mkdtemp()
    filename = os.path.join(dir, 'scheme.xml')
    f = open(filename, 'w')
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<style-scheme id="scheme" _name="Scheme" version="1.0">\n')
    for name, attributes in spec.iteritems():
        f.write('<style name="%s" ' % name)
        for attname, attvalue in attributes.iteritems():
            if attname in ('foreground', 'background'):
                attvalue = gdk.color_parse(attvalue).to_string()
            elif attname in ('italic', 'bold', 'underline', 'strikethrough',
                             'foreground-set', 'background-set'):
                attvalue = 'true' if attvalue else 'false'
            f.write('%s="%s" ' % (attname, attvalue))
        f.write('/>\n')
    f.write('</style-scheme>\n')
    f.close()
    
    ssm = gtksourceview2.StyleSchemeManager()
    ssm.set_search_path([dir])
    scheme = ssm.get_scheme('scheme')

    os.remove(filename)
    os.rmdir(dir)

    return scheme

def _get_style_scheme_spec(theme):
    mapping = {
        'text': DEFAULT,
        
        'def:keyword': KEYWORD,
        'def:preprocessor': KEYWORD,

        'def:builtin': BUILTIN,
        'def:special-constant': BUILTIN,
        'def:type': BUILTIN,

        'def:string': STRING,
        'def:number': NUMBER,
        'def:comment': COMMENT,

        'bracket-match': BRACKET_MATCH,
        'python:bracket-1': BRACKET_1,
        'python:bracket-2': BRACKET_2,
        'python:bracket-3': BRACKET_3,
        'def:error': ERROR,
        }

    res = {}
    for key, value in mapping.iteritems():
        res[key] = dict(foreground=get_actual_color(theme, value, FG),
                        background=get_actual_color(theme, value, BG))
    return res

def apply_theme_source(sourcebuffer, theme):
    sourcebuffer.set_style_scheme(
        _make_style_scheme(_get_style_scheme_spec(theme)))


