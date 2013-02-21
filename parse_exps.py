#!/usr/bin/env python
from __future__ import print_function

import config.config as conf
import os
import parse.ft as ft
import parse.sched as st
import pickle
import shutil as sh
import sys
import traceback

from collections import namedtuple
from common import load_params
from optparse import OptionParser
from parse.point import ExpPoint
from parse.tuple_table import TupleTable
from parse.col_map import ColMapBuilder
from multiprocessing import Pool, cpu_count

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

def get_exp_params(data_dir, cm_builder):
    param_file = "%s/%s" % (data_dir, conf.DEFAULTS['params_file'])
    if not os.path.isfile:
        raise Exception("No param file '%s' exists!" % param_file)

    params = load_params(param_file)

    # Store parameters in cm_builder, which will track which parameters change
    # across experiments
    for key, value in params.iteritems():
        cm_builder.try_add(key, value)

    # Cycles must be present for feather-trace measurement parsing
    if conf.PARAMS['cycles'] not in params:
        params[conf.PARAMS['cycles']] = conf.DEFAULTS['cycles']

    return params


def load_exps(exp_dirs, cm_builder, clean):
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

        params = get_exp_params(data_dir, cm_builder)

        exps += [ ExpData(data_dir, params, work_dir) ]

    return exps

def parse_exp(exp_force):
    # Tupled for multiprocessing
    exp, force  = exp_force

    result_file = exp.work_dir + "/exp_point.pkl"
    should_load = not force and os.path.exists(result_file)

    result = None
    if should_load:
        with open(result_file, 'rb') as f:
            try:
                # No need to go through this work twice
                result = pickle.load(f)
            except:
                pass

    if not result:
        try:
            result = ExpPoint(exp.path)
            cycles = exp.params[conf.PARAMS['cycles']]

            # Write overheads into result
            ft.extract_ft_data(result, exp.path, exp.work_dir, cycles)

            # Write scheduling statistics into result
            st.extract_sched_data(result, exp.path, exp.work_dir)

            with open(result_file, 'wb') as f:
                pickle.dump(result, f)
        except:
            traceback.print_exc()

    return (exp, result)

def main():
    opts, args = parse_args()

    args = args or [os.getcwd()]

    # Load exp parameters into a ColMap
    builder = ColMapBuilder()
    exps = load_exps(args, builder, opts.force)

    # Don't track changes in ignored parameters
    if opts.ignore:
        for param in opts.ignore.split(","):
            builder.try_remove(param)

    col_map = builder.build()
    result_table = TupleTable(col_map)

    sys.stderr.write("Parsing data...\n")

    procs = min(len(exps), cpu_count()/2)
    pool = Pool(processes=procs)
    pool_args = zip(exps, [opts.force]*len(exps))
    enum = pool.imap_unordered(parse_exp, pool_args, 1)

    try:
        for i, (exp, result) in enumerate(enum):
            if opts.verbose:
                print(result)
            else:
                sys.stderr.write('\r {0:.2%}'.format(float(i)/len(exps)))
                result_table[exp.params] += [result]
        pool.close()
    except:
        pool.terminate()
        traceback.print_exc()
        raise Exception("Failed parsing!")
    finally:
        pool.join()

    sys.stderr.write('\n')

    if opts.force and os.path.exists(opts.out):
        sh.rmtree(opts.out)

    result_table = result_table.reduce()

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
