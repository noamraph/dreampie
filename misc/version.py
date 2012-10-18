#!/usr/bin/env python

from os.path import abspath, join, dirname
import time

def main():
    import argparse
    parser = argparse.ArgumentParser(description="update DreamPie version")
    parser.add_argument("version", help="Version (eg. '1.2', '1.2.1')")
    args = parser.parse_args()
    ints = map(int, args.version.split('.'))
    assert args.version == '.'.join(map(str, ints))
    assert len(ints) <= 4
    fn = join(dirname(dirname(abspath(__file__))), 'dreampielib', '__init__.py')
    t = int(time.time())
    tt = time.gmtime(t)
    f = open(fn, 'w')
    f.write("""\
__version__ = "{version}"
release_timestamp = {t} # calendar.timegm(({tt.tm_year}, {tt.tm_mon}, {tt.tm_mday}, {tt.tm_hour}, {tt.tm_min}, {tt.tm_sec}))
""".format(version=args.version, t=t, tt=tt))
    f.close()
    print "Wrote", fn

if __name__ == '__main__':
    main()
