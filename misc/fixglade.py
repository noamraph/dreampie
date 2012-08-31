#!/usr/bin/env python

import os
from os.path import abspath, dirname, join

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Fix glade file to avoid warnings.')
    args = parser.parse_args()

    fn = join(dirname(dirname(abspath(__file__))), 'dreampielib', 'data', 'dreampie.glade')
    s = open(fn).read()
    fixed = s.replace(' swapped="no"', '')
    fn_new = fn + '.new'
    f = open(fn_new, 'w')
    f.write(fixed)
    f.close()
    os.rename(fn_new, fn)

if __name__ == '__main__':
    main()

