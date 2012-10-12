#!/usr/bin/env python
from __future__ import print_function

from optparse import OptionParser

def parse_args():
    parser = OptionParser("usage: %prog [options] [csv_dir]...")

    parser.add_option('-o', '--out-dir', dest='out_dir',
                      help='directory for plot output', default='plot-data')
    parser.add_option('-f', '--force', action='store_true', default=False,
                      dest='force', help='overwrite existing data')

    return parser.parse_args()

def main():
    opts, args = parse_args()
    args = args or [os.getcwd()]

if __name__ == '__main__':
    main()
