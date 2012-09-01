# vim: sw=4 ts=4:
#
# (c) 2003 Gustavo J A M Carneiro gjc at inescporto.pt
#     2004-2005 Filip Van Raemdonck
#
# http://www.daa.com.au/pipermail/pygtk/2003-August/005775.html
# Message-ID: <1062087716.1196.5.camel@emperor.homelinux.net>
#     "The license is whatever you want."

import inspect, linecache, sys, traceback
from repr import repr as safe_repr
from cStringIO import StringIO
from gettext import gettext as _
#from smtplib import SMTP

import gtk
import pango

from .bug_report import bug_report

#def analyse (exctyp, value, tb):
#    trace = StringIO()
#    traceback.print_exception (exctyp, value, tb, None, trace)
#    return trace.getvalue()

def lookup (name, frame, lcls):
    '''Find the value for a given name in the given frame'''
    if name in lcls:
        return 'local', lcls[name]
    elif name in frame.f_globals:
        return 'global', frame.f_globals[name]
    elif '__builtins__' in frame.f_globals:
        builtins = frame.f_globals['__builtins__']
        if type (builtins) is dict:
            if name in builtins:
                return 'builtin', builtins[name]
        else:
            if hasattr (builtins, name):
                return 'builtin', getattr (builtins, name)
    return None, []

def analyse (exctyp, value, tb):
    import tokenize, keyword

    trace = StringIO()
    nlines = 1
    frecs = inspect.getinnerframes (tb, nlines)
    trace.write ('Variables:\n')
    for frame, fname, lineno, funcname, _context, _cindex in frecs:
        trace.write ('  File "%s", line %d, ' % (fname, lineno))
        args, varargs, varkw, lcls = inspect.getargvalues (frame)

        def readline (lno=[lineno], *args):
            if args: print args
            try: return linecache.getline (fname, lno[0])
            finally: lno[0] += 1
        all, prev, name, scope = {}, None, '', None
        for ttype, tstr, _stup, _etup, _line in tokenize.generate_tokens (readline):
            if ttype == tokenize.NAME and tstr not in keyword.kwlist:
                if name:
                    if name[-1] == '.':
                        try:
                            val = getattr (prev, tstr)
                        except AttributeError:
                            # XXX skip the rest of this identifier only
                            break
                        name += tstr
                else:
                    assert not name and not scope
                    scope, val = lookup (tstr, frame, lcls)
                    name = tstr
                if val is not None:
                    prev = val
                #print '  found', scope, 'name', name, 'val', val, 'in', prev, 'for token', tstr
            elif tstr == '.':
                if prev:
                    name += '.'
            else:
                if name:
                    all[name] = prev
                prev, name, scope = None, '', None
                if ttype == tokenize.NEWLINE:
                    break

        trace.write (funcname +
          inspect.formatargvalues (args, varargs, varkw, lcls, formatvalue=lambda v: '=' + safe_repr (v)) + '\n')
        if len (all):
            trace.write ('    %s\n' % str (all))

    trace.write('\n')
    traceback.print_exception (exctyp, value, tb, None, trace)
    
    return trace.getvalue()

def _info (exctyp, value, tb):
    # First output the exception to stderr
    orig_excepthook(exctyp, value, tb)
    
    try:
        import pdb
    except ImportError:
        # py2exe
        pdb = None
        
    if exctyp is KeyboardInterrupt:
        sys.exit(1)
    trace = None
    dialog = gtk.MessageDialog (parent=None, flags=0, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_NONE)
    dialog.set_title (_("Bug Detected"))
    if gtk.check_version (2, 4, 0) is not None:
        dialog.set_has_separator (False)

    primary = _("<big><b>A programming error has been detected.</b></big>")
    secondary = _("Please report it by clicking the 'Report' button. Thanks!")

    dialog.set_markup (primary)
    dialog.format_secondary_text (secondary)

    dialog.add_button (_("Report..."), 3)
        
    dialog.add_button (_("Details..."), 2)
    if pdb:
        dialog.add_button (_("Debug..."), 4)
    dialog.add_button (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)

    while True:
        resp = dialog.run()
        if resp == 4:
            pdb.post_mortem(tb)
            
        if resp == 3:
            if trace == None:
                trace = analyse (exctyp, value, tb)
            
            bug_report(dialog, _gladefile, trace)

        elif resp == 2:
            if trace == None:
                trace = analyse (exctyp, value, tb)

            # Show details...
            details = gtk.Dialog (_("Bug Details"), dialog,
              gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
              (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE, ))
            details.set_property ("has-separator", False)

            textview = gtk.TextView(); textview.show()
            textview.set_editable (False)
            textview.modify_font (pango.FontDescription ("Monospace"))

            sw = gtk.ScrolledWindow(); sw.show()
            sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            sw.add (textview)
            details.vbox.add (sw)
            textbuffer = textview.get_buffer()
            textbuffer.set_text (trace)

            monitor = gtk.gdk.screen_get_default ().get_monitor_at_window (dialog.window)
            area = gtk.gdk.screen_get_default ().get_monitor_geometry (monitor)
            w = area.width // 1.6
            h = area.height // 1.6
            details.set_default_size (int (w), int (h))

            details.run()
            details.destroy()

        else:
            break

    dialog.destroy()

def install(gladefile):
    global orig_excepthook, _gladefile
    _gladefile = gladefile
    orig_excepthook = sys.excepthook
    sys.excepthook = _info

if __name__ == '__main__':
    class X (object):
        pass
    x = X()
    x.y = 'Test'
    x.z = x
    w = ' e'
    1, x.z.y, w
    raise Exception (x.z.y + w)

