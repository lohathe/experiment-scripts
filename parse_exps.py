#!/usr/bin/env python
from __future__ import print_function

import config.config as conf
import copy
import os
import parse.ft as ft
import parse.sched as st
import re

from collections import namedtuple
from common import load_params
from optparse import OptionParser
from parse.point import ExpPoint
from parse.tuple_table import ColMap,TupleTable

def parse_args():
    parser = OptionParser("usage: %prog [options] [data_dir]...")

    parser.add_option('-o', '--out-dir', dest='out_dir',
                      help='directory for data output', default=os.getcwd())
    parser.add_option('-s', '--scale-against', dest='scale_against',
                      metavar='PARAM=VALUE', default="",
                      help='calculate task scaling factors against these configs')

    return parser.parse_args()

ExpData   = namedtuple('ExpData', ['name', 'params', 'data_files'])
DataFiles = namedtuple('DataFiles', ['ft','st'])

def get_exp_params(data_dir, col_map):
    param_file = "%s/%s" % (data_dir, conf.DEFAULTS['params_file'])
    if not os.path.isfile:
        raise Exception("No param file '%s' exists!" % param_file)

    # Keep only params that uniquely identify the experiment
    params = load_params(param_file)
    for ignored in conf.PARAMS.itervalues():
        if ignored in params:
            params.pop(ignored)

    # Track all changed params
    for key in params.keys():
        col_map.try_add(key)

    return params


def gen_exp_data(exp_dirs, base_conf, col_map):
    plain_exps = []
    scaling_bases  = []

    for data_dir in exp_dirs:
        if not os.path.isdir(data_dir):
            raise IOError("Invalid experiment '%s'" % os.path.abspath(data_dir))

        tmp_dir = data_dir + "/tmp"
        if not os.path.exists(tmp_dir):
            os.mkdir(tmp_dir)

        # Read and translate exp output files
        params = get_exp_params(data_dir, col_map)
        st_output = st.get_st_output(data_dir, tmp_dir)
        ft_output = ft.get_ft_output(data_dir, tmp_dir)

        # Create experiment named after the data dir
        exp_data = ExpData(data_dir, params, DataFiles(ft_output, st_output))

        if base_conf and base_conf.viewitems() & params.viewitems():
            if not st_output:
                raise Exception("Scaling base '%s' useless without sched data!"
                                % data_dir)
            params.pop(base_conf.keys()[0])
            scaling_bases += [exp_data]
        else:
            plain_exps += [exp_data]

    return (plain_exps, scaling_bases)

def main():
    opts, args = parse_args()

    args = args or [os.getcwd()]

    # Configuration key for task systems used to calculate task
    # execution scaling factors
    base_conf = dict(re.findall("(.*)=(.*)", opts.scale_against))

    col_map = ColMap()

    (plain_exps, scaling_bases) = gen_exp_data(args, base_conf, col_map)

    if base_conf and base_conf.keys()[0] not in col_map:
        raise IOError("Base column '%s' not present in any parameters!" %
                      base_conf.keys()[0])

    base_table   = TupleTable(col_map)
    result_table = TupleTable(col_map)

    # Used to find matching scaling_base for each experiment
    for base in scaling_bases:
        base_table.add_exp(base.params, base)

    for exp in plain_exps:
        result = ExpPoint(exp.name)

        if exp.data_files.ft:
            # Write overheads into result
            ft.extract_ft_data(exp.data_files.ft, result, conf.BASE_EVENTS)

        if exp.data_files.st:
            base = None
            if base_conf:
                # Try to find a scaling base
                base_params = copy.deepcopy(exp.params)
                base_params.pop(base_conf.keys()[0])
                base = base_table.get_exps(base_params)[0]
            # Write deadline misses / tardiness into result
            st.extract_sched_data(exp.data_files.st, result,
                                  base.data_files.st if base else None)

        result_table.add_exp(exp.params, result)

        print(result)


    result_table.write_result(opts.out_dir)

if __name__ == '__main__':
    main()
