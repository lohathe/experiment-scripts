#!/usr/bin/env python
from __future__ import print_function

import os
import shutil as sh
import sys
from optparse import OptionParser
from parse.dir_map import DirMap
from parse.tuple_table import ReducedTupleTable
from parse.col_map import ColMap
from collections import namedtuple,defaultdict
import matplotlib.pyplot as plot

def parse_args():
    parser = OptionParser("usage: %prog [options] [csv_dir]...")

    parser.add_option('-o', '--out-dir', dest='out_dir',
                      help='directory for plot output', default='plot-data')
    parser.add_option('-f', '--force', action='store_true', default=False,
                      dest='force', help='overwrite existing data')

    return parser.parse_args()


ExpDetails = namedtuple('ExpDetails', ['variable', 'value', 'title', 'out'])
OUT_FORMAT = 'pdf'

def get_details(path):
    out = "_".join(path) if path else "plot"

    value = path.pop() if path else None
    variable = path.pop() if path else None

    title  = value.capitalize() if value else ""
    title += " by %s" % variable if variable else ""
    title += " (%s)" % (", ".join(path)) if path else ""

    return ExpDetails(variable, value, title, out)



class StyleMap(object):
    COLORS  = list('bgrcmyk')
    LINES   = ['-', ':', '--']
    MARKERS = list('.,ov^<>1234sp*hH+xDd|_')
    ORDER   = [MARKERS, COLORS, LINES]
    DEFAULT = ["k", "-", "k"]

    def __init__(self, col_list, col_values):
        self.prop_map = dict(zip(col_list, StyleMap.ORDER))

        # Store 1 style per value
        self.value_map = defaultdict(dict)
        for column, styles in self.prop_map.iteritems():
            value_styles = self.value_map[column]
            for value in sorted(col_values[column]):
                value_styles[value] = styles.pop(0)
                styles += [value_styles[value]]

    def get_style(self, kv):
        style = ''
        for k,v in kv.iteritems():
            if k in self.value_map:
                style += self.value_map[k][v]
        return style

    def get_key(self):
        key = []
        for column, properties in self.prop_map.iteritems():
            idx = StyleMap.ORDER.index(properties)
            prop_string = StyleMap.DEFAULT[idx] + "%s"
            for value, prop in self.value_map[column].iteritems():
                style = plot.plot([],[], prop_string%prop)[0]
                key += [(style, "%s:%s" % (column, value))]
        return sorted(key, key=lambda x:x[1])

def plot_by_variable(dir_map, col_map, out_dir, force):
    num_plots = 0
    id = 0
    for _,_ in dir_map.leafs(1):
        num_plots += 1
    sys.stderr.write("Plotting by variable...")

    for plot_path, plot_node in dir_map.leafs(1):
        id += 1
        details = get_details(plot_path)
        out_fname = "%s/%s.%s" % (out_dir, details.out, OUT_FORMAT)
        if os.path.exists(out_fname) and not force:
            continue

        # Kinda bad...
        first_csv = plot_node.children.keys()[0]
        first_config = ColMap.decode(first_csv[:first_csv.index('.csv')])
        columns = filter(lambda c: c in first_config, col_map.columns())

        style_map = StyleMap(columns, col_map.get_values())

        figure = plot.figure()
        axes = figure.add_subplot(111)

        for line_path, line_node in plot_node.children.iteritems():
            encoded = line_path[:line_path.index(".csv")]
            config  = ColMap.decode(encoded)
            style = style_map.get_style(config)

            values = sorted(line_node.values, key=lambda tup: tup[0])
            xvalues, yvalues = zip(*values)

            plot.plot(xvalues, yvalues, style)

        lines, labels = zip(*style_map.get_key())

        axes.legend(tuple(lines), tuple(labels), prop={'size':10})
        axes.set_ylabel(details.value)
        axes.set_xlabel(details.variable)
        axes.set_xlim(0, axes.get_xlim()[1] + 1)
        axes.set_ylim(0, axes.get_ylim()[1] + 1)

        axes.set_title(details.title)

        plot.savefig(out_fname, format=OUT_FORMAT)

        sys.stderr.write('\r {0:.2%}'.format(float(id)/num_plots))
        sys.stderr.write('\n')

def plot_exp(data_dir, out_dir, force):
    print("Reading data...")
    dir_map = DirMap.read(data_dir)
    print("Sorting configs...")
    tuple_table = ReducedTupleTable.from_dir_map(dir_map)
    col_map = tuple_table.get_col_map()

    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

    print("Plotting data...")
    plot_by_variable(dir_map, col_map, out_dir, force)
    # plot_by_config(tuple_table, out_dir)

def main():
    opts, args = parse_args()
    args = args or [os.getcwd()]

    if opts.force and os.path.exists(opts.out_dir):
        sh.rmtree(opts.out_dir)
    if not os.path.exists(opts.out_dir):
        os.mkdir(opts.out_dir)

    for exp in args:
        name = os.path.split(exp)[1]
        if exp != os.getcwd():
            out_dir = "%s/%s" % (opts.out_dir, name)
        else:
            out_dir = os.getcwd()
        plot_exp(exp, out_dir, opts.force)

if __name__ == '__main__':
    main()
