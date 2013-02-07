#!/usr/bin/env python
from __future__ import print_function

import config.config as conf
import os
import parse.ft as ft
import parse.sched as st
import shutil as sh
import sys

from collections import namedtuple
from common import load_params
from optparse import OptionParser
from parse.point import ExpPoint
from parse.tuple_table import ColMap,TupleTable

def parse_args():
    # TODO: convert data-dir to proper option, clean 'dest' options
    parser = OptionParser("usage: %prog [options] [data_dir]...")

    print("default to no params.py")

    parser.add_option('-o', '--out', dest='out',
                      help='file or directory for data output', default='parse-data')
    parser.add_option('-c', '--clean', action='store_true', default=False,
                      dest='clean', help='do not output single-point csvs')
    parser.add_option('-i', '--ignore', metavar='[PARAM...]', default="",
                      help='ignore changing parameter values')
    parser.add_option('-f', '--force', action='store_true', default=False,
                      dest='force', help='overwrite existing data')
    parser.add_option('-v', '--verbose', action='store_true', default=False,
                      dest='verbose', help='print out data points')
    parser.add_option('-m', '--write-map', action='store_true', default=False,
                      dest='write_map',
                      help='Output map of values instead of csv tree')

    return parser.parse_args()

ExpData = namedtuple('ExpData', ['path', 'params', 'work_dir'])

def get_exp_params(data_dir, col_map):
    param_file = "%s/%s" % (data_dir, conf.DEFAULTS['params_file'])
    if not os.path.isfile:
        raise Exception("No param file '%s' exists!" % param_file)

    params = load_params(param_file)

    # Store parameters in col_map, which will track which parameters change
    # across experiments
    for key, value in params.iteritems():
        col_map.try_add(key, value)

    # Cycles must be present for feather-trace measurement parsing
    if conf.PARAMS['cycles'] not in params:
        params[conf.PARAMS['cycles']] = conf.DEFAULTS['cycles']

    return params


def load_exps(exp_dirs, col_map, clean):
    exps = []

    sys.stderr.write("Loading experiments...\n")

    for data_dir in exp_dirs:
        if not os.path.isdir(data_dir):
            raise IOError("Invalid experiment '%s'" % os.path.abspath(data_dir))

        # Used to store error output and debugging info
        work_dir = data_dir + "/tmp"

        if os.path.exists(work_dir) and clean:
            sh.rmtree(work_dir)
        if not os.path.exists(work_dir):
            os.mkdir(work_dir)

        params = get_exp_params(data_dir, col_map)

        exps += [ ExpData(data_dir, params, work_dir) ]

    return exps

def main():
    opts, args = parse_args()

    args = args or [os.getcwd()]

    # Load exp parameters into col_map
    col_map = ColMap()
    exps = load_exps(args, col_map, opts.force)

    # Don't track changes in ignored parameters
    if opts.ignore:
        for param in opts.ignore.split(","):
            col_map.try_remove(param)

    result_table = TupleTable(col_map)

    sys.stderr.write("Parsing data...\n")
    for i,exp in enumerate(exps):
        result = ExpPoint(exp.path)
        cycles = exp.params[conf.PARAMS['cycles']]

        # Write overheads into result
        ft.extract_ft_data(result, exp.path, exp.work_dir, cycles)

        # Write scheduling statistics into result
        st.extract_sched_data(result, exp.path, exp.work_dir)

        if opts.verbose:
            print(result)
        else:
            sys.stderr.write('\r {0:.2%}'.format(float(i)/len(exps)))

        result_table.add_exp(exp.params, result)

    sys.stderr.write('\n')

    if opts.force and os.path.exists(opts.out):
        sh.rmtree(opts.out)

    result_table.reduce()

    sys.stderr.write("Writing result...\n")
    if opts.write_map:
        # Write summarized results into map
        result_table.write_map(opts.out)
    else:
        # Write out csv directories for all variable params
        dir_map = result_table.to_dir_map()
        dir_map.write(opts.out)

if __name__ == '__main__':
    main()
