#!/usr/bin/env python
from __future__ import print_function

import config.config as conf
import os

import parse.ft as ft
import parse.sched as st

from collections import namedtuple
from common import load_params
from optparse import OptionParser
from parse.tuple_table import ColMap,TupleTable
from parse.point import ExpPoint

def parse_args():
    parser = OptionParser("usage: %prog [options] [data_dir]...")

    parser.add_option('-o', '--out-dir', dest='out_dir',
                      help='directory for data output', default=os.getcwd())

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


def gen_exp_data(exp_dirs, col_map):
    exps = []
    for data_dir in exp_dirs:
        if not os.path.isdir(data_dir):
            raise IOError("Invalid experiment '%s'" % os.path.abspath(data_dir))
        
        tmp_dir = data_dir + "/tmp"
        if not os.path.exists(tmp_dir):
            os.mkdir(tmp_dir)

        params = get_exp_params(data_dir, col_map)
        st_output = st.get_st_output(data_dir, tmp_dir)
        ft_output = ft.get_ft_output(data_dir, tmp_dir)

        exp_data = ExpData(data_dir, params, DataFiles(ft_output, st_output))
        exps += [exp_data]

    return exps

def main():
    opts, args = parse_args()

    args = args or [os.getcwd()]
    col_map = ColMap()
    exps = gen_exp_data(args, col_map)

    table = TupleTable(col_map)

    for exp in exps:
        result = ExpPoint(exp.name)
        if exp.data_files.ft:
            ft.get_ft_data(exp.data_files.ft, result, conf.BASE_EVENTS)
        if exp.data_files.st:
            st.get_sched_data(exp.data_files.st, result)

        table.add_exp(exp.params, result)

    table.write_result(opts.out_dir)
    
if __name__ == '__main__':
    main()
