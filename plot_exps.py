#!/usr/bin/env python
from __future__ import print_function

import matplotlib.pyplot as plot
import os
import shutil as sh
import sys
from collections import namedtuple
from optparse import OptionParser
from parse.col_map import ColMap
from parse.dir_map import DirMap
from parse.tuple_table import ReducedTupleTable
from plot.style import StyleMap

def parse_args():
    parser = OptionParser("usage: %prog [options] [csv_dir]...")

    parser.add_option('-o', '--out-dir', dest='out_dir',
                      help='directory for plot output', default='plot-data')
    parser.add_option('-f', '--force', action='store_true', default=False,
                      dest='force', help='overwrite existing data')

    return parser.parse_args()

ExpDetails = namedtuple('ExpDetails', ['variable', 'value', 'title', 'out'])
OUT_FORMAT = 'pdf'

def get_details(path, out_dir):
    '''Decode a @path into details about a single experiment.'''
    out = "_".join(path) if path else "plot"
    out = "%s/%s.%s" % (out_dir, out, OUT_FORMAT)

    value = path.pop(0) if path else None
    variable = path.pop(0) if path else None

    title  = value.capitalize() if value else ""
    title += " by %s" % variable if variable else ""
    title += " (%s)" % (", ".join(path)) if path else ""

    return ExpDetails(variable, value, title, out)

def plot_by_variable(plot_node, col_map, details):
    '''Plot each .csv files under @plot_node as a line on a shared plot.'''

    # Generate mapping of (column)=>(line property to vary) for consistently
    # formatted plots
    columns = list(col_map.columns())
    if details.variable and details.variable in columns:
        columns.remove(details.variable)
    style_map = StyleMap(columns, col_map.get_values())

    figure = plot.figure()
    axes = figure.add_subplot(111)

    # Create a line for each file node
    for line_path, line_node in plot_node.children.iteritems():
        # Create line style to match this configuration
        encoded = line_path[:line_path.index(".csv")]
        config  = ColMap.decode(encoded)
        style   = style_map.get_style(config)

        values = sorted(line_node.values, key=lambda tup: tup[0])
        xvalues, yvalues = zip(*values)

        plot.plot(xvalues, yvalues, style.fmt())

    axes.set_title(details.title)

    lines, labels = zip(*style_map.get_key())
    axes.legend(tuple(lines), tuple(labels), prop={'size':10})

    axes.set_ylabel(details.value)
    axes.set_xlabel(details.variable)
    axes.set_xlim(0, axes.get_xlim()[1] + 1)
    axes.set_ylim(0, axes.get_ylim()[1] + 1)

    plot.savefig(details.out, format=OUT_FORMAT)

def plot_dir(data_dir, out_dir, force):
    sys.stderr.write("Reading data...\n")
    dir_map = DirMap.read(data_dir)

    sys.stderr.write("Creating column map...\n")
    tuple_table = ReducedTupleTable.from_dir_map(dir_map)
    col_map = tuple_table.get_col_map()

    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

    sys.stderr.write("Plotting...\n")

    # Count total plots for % counter
    num_plots = len([x for x in dir_map.leafs(1)])
    plot_num  = 0

    for plot_path, plot_node in dir_map.leafs(1):
        details = get_details(plot_path, out_dir)

        if force or not os.path.exists(details.out):
            plot_by_variable(plot_node, col_map, details)

        plot_num += 1

        sys.stderr.write('\r {0:.2%}'.format(float(plot_num)/num_plots))
        sys.stderr.write('\n')

def main():
    opts, args = parse_args()
    args = args or [os.getcwd()]

    if opts.force and os.path.exists(opts.out_dir):
        sh.rmtree(opts.out_dir)
    if not os.path.exists(opts.out_dir):
        os.mkdir(opts.out_dir)

    for dir in args:
        plot_dir(dir, opts.out_dir, opts.force)

if __name__ == '__main__':
    main()
