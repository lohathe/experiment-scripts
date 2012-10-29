#!/usr/bin/env python
from __future__ import print_function

import os
import re
import plot
import shutil as sh

from collections import defaultdict
from optparse import OptionParser
from gnuplot import Plot, curve
from random import randrange

class StyleMaker(object):
    LINE_WIDTH = 1.5
    POINT_SIZE = 0.6
    BEST_COLORS = [
            '#ff0000', # red
            '#000001', # black
            '#0000ff', # blue
            '#be00c4', # purple
            '#ffd700', # yellow
            ]

    def __init__(csvs):
        self.main_key, self.col_map = __find_columns(csvs)
        self.cur_style = 1

        # Use this for least-common varying attribute
        self.main_map = {}
        # Everything else is a color
        self.color_map = TupleTable(self.col_map)

    def __find_columns(csvs):
        vals = defaultdict(lambda:set)

        for csv in csvs:
            to_decode = os.path.splitext(csv_file)[0]
            params = plot.decode(to_decode)
            for k,v in params.iteritems:
                vals[k].add(v)

        try:
            main_key = min([(k,v) for (k,v) in thing.iteritems() if len(v) > 1],
                key=operator.itemgetter(1))[0]
        except ValueError:
            main_key = None

        col_map = ColMap()
        for k,v in vals.iterkeys():
            if k == self.main_key: continue
            for i in v:
                self.col_map.try_add(k, i)
        return (main_key, col_map)

    def __rand_color():
        return "#%s" % "".join([hex(randrange(0, 255))[2:] for i in range(3)])

    def get_style(csv):
        to_decode = os.path.splitext(csv_file)[0]
        params = plot.decode(to_decode)

        if kv not in self.color_map:
            color = best.pop() if BEST_COLORS else __rand_color()
            self.color_map.add_exp(params, color)

        if self.main_key in params:
            val = params[self.main_key]
            if val not in self.main_map:
                self.main_map[val] = self.cur_style
                self.cur_style += 1
            style = self.main_map[val]
        else:
            style = 1

def parse_args():
    parser = OptionParser("usage: %prog [options] [csv_dir]...")

    parser.add_option('-o', '--out-dir', dest='out_dir',
                      help='directory for plot output', default='plot-data')
    parser.add_option('-f', '--force', action='store_true', default=False,
                      dest='force', help='overwrite existing data')

    return parser.parse_args()

def get_label(kv):
    label = []
    for key, value in kv.iteritems():
        label += ["%s=%s" % (key.capitalize(), value)]
    return ", ".join(label)

def add_line(plot, csv_file):
    to_decode = os.path.splitext(csv_file)[0]
    params = plot.decode(to_decode)

def get_stat(path, name):
    full  = os.path.abspath(path)
    rstr  = r"(?P<STAT>[^/]+)/((max|min|var|avg)/)*(%s/?)?$" % name
    regex = re.compile(rstr, re.I | re.M)
    match = regex.search(full)
    return match.group("STAT")

def plot_exp(name, data_dir, out_dir):
    p = Plot()
    p.format = 'pdf'
    p.output = "%s/%s.pdf" % (out_dir, name)
    p.xlabel = name.replace("vary-", "")
    p.ylabel = get_stat(data_dir, name)
    p.font   = 'Helvetica'
    p.dashed_lines  = True
    p.enhanced_text = True
    p.size          = ('5.0cm', '5.0cm')
    p.font_size     = '6pt'
    p.key           = 'on bmargin center horizontal'

    csvs = [f for f in os.listdir(data_dir) if re.match("*.csv", f)]
    col_map = get_col_map(csvs)


def main():
    opts, args = parse_args()
    args = args or [os.getcwd()]

    # if opts.force and os.path.exists(opts.out_dir):
    #     sh.rmtree(opts.out_dir)
    # if not os.path.exists(opts.out_dir):
    #     os.mkdir(opts.out_dir)

    for exp in args:
        name = os.path.split(exp)[1]
        out_dir = "%s/%s" % (opts.out_dir, exp)

        plot_exp(name, exp, out_dir)

if __name__ == '__main__':
    main()
