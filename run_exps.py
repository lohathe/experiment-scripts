#!/usr/bin/env python
from __future__ import print_function

import config.config as conf
import experiment.litmus_util as lu
import os
import re

from collections import defaultdict
from optparse import OptionParser
from experiment.executable.executable import Executable
from experiment.experiment import Experiment
from experiment.proc_entry import ProcEntry


def parse_args():
    parser = OptionParser();

    parser.add_option('-s', '--scheduler', dest='scheduler',
                      help='scheduler for all experiments')
    parser.add_option('-d', '--duration', dest='duration', type='int',
                      help='duration (seconds) of tasks')
    parser.add_option('-o', '--out-dir', dest='out_dir',
                      help='directory for data output', default=os.getcwd())
    parser.add_option('-p', '--params', dest='param_file',
                      help='file with experiment parameters')
    parser.add_option('-f', '--schedule-file', dest='sched_file',
                      help='name of schedule files',
                      default=conf.DEFAULTS['sched_file'])

    return parser.parse_args()


def convert_data(data):
    """Convert a non-python schedule file into the python format"""
    regex = re.compile(

    r"(?P<PROC>^"
          r"(?P<HEADER>/proc/\w+?/)?"
          r"(?P<ENTRY>[\w\/]+)"
          r"\s*{\s*(?P<CONTENT>.*?)\s*?}$)|"
        r"(?P<SPIN>^(?P<TYPE>\w+?spin)?\s*?"
          r"(?P<ARGS>\w[\s\w]*?)?\s*?$)",
        re.S|re.I|re.M)

    procs = []
    spins = []

    for match in regex.finditer(data):
        if match.group("PROC"):
            header = match.group("HEADER") or "/proc/litmus/"
            loc  = "{}{}".format(header, match.group("ENTRY"))
            proc = (loc, match.group("CONTENT"))
            procs.append(proc)
        else:
            prog = match.group("TYPE") or "rtspin"
            spin = (prog, match.group("ARGS"))
            spins.append(spin)

    return {'proc' : procs, 'spin' : spins}


def get_dirs(sched_file, out_base_dir):
    sched_leaf_dir  = re.findall(r".*/([\w_-]+)/.*?$", sched_file)[0]
    sched_full_dir = os.path.split(sched_file)[0]

    work_dir = "%s/tmp" % sched_full_dir

    if sched_full_dir == out_base_dir:
        out_dir = "%s/data" % sched_full_dir
    else:
        # Put it under the base output dir with the same directory name
        out_dir  = "%s/%s" % (out_base_dir, sched_leaf_dir)

    return (work_dir, out_dir)


def load_experiment(sched_file, scheduler, duration, param_file, out_base):
    if not os.path.isfile(sched_file):
        raise IOError("Cannot find schedule file: %s" % sched_file)

    dirname = os.path.split(sched_file)[0]

    if not scheduler or not duration:
        param_file = param_file or \
          "%s/%s" % (dirname, conf.DEFAULTS['params_file'])

        if os.path.isfile(param_file):
            params = load_params(param_file)
            scheduler = scheduler or params[conf.PARAMS['sched']]
            duration  = duration  or params[conf.PARAMS['dur']]

        duration = duration or conf.DEFAULTS['duration']

        if not scheduler:
            raise IOError("Parameter scheduler not specified")

    schedule = load_schedule(sched_file)
    (work_dir, out_dir) = get_dirs(sched_file, out_base)

    run_exp(sched_file, schedule, scheduler, duration, work_dir, out_dir)


def load_params(fname):
    params = defaultdict(int)
    with open(fname, 'r') as f:
        data = f.read()
    try:
        parsed = eval(data)
        for k in parsed:
            params[k] = parsed[k]
    except Exception as e:
        raise IOError("Invalid param file: %s\n%s" % (fname, e))

    return params


def load_schedule(fname):
    with open(fname, 'r') as f:
        data = f.read().strip()
    try:
        schedule = eval(data)
    except:
        schedule = convert_data(data)
    return schedule


def run_exp(name, schedule, scheduler, duration, work_dir, out_dir):
    proc_entries = []
    executables  = []

    # Parse values for proc entries
    for entry_conf in schedule['proc']:
        path = entry_conf[0]
        data = entry_conf[1]

        if not os.path.exists(path):
            raise IOError("Invalid proc path %s: %s" % (path, name))

        proc_entries += [ProcEntry(path, data)]

    # Parse spinners
    for spin_conf in schedule['spin']:
        if isinstance(spin_conf, str):
            # Just a string defaults to default spin
            (spin, args) = (conf.DEFAULTS['spin'], spin_conf)
        else:
            # Otherwise its a pair, the type and the args
            if len(spin_conf) != 2:
                raise IOError("Invalid spin conf %s: %s" % (spin_conf, name))
            (spin, args) = (spin_conf[0], spin_conf[1])

        if not conf.BINS[spin]:
            raise IndexError("No knowledge of program %s: %s" % (spin, name))

        real_spin = conf.BINS[spin]
        real_args = ['-w'] + args.split() + [duration]

        if not lu.is_executable(real_spin):
            raise OSError("Cannot run spin %s: %s" % (real_spin, name))

        executables += [Executable(real_spin, real_args)]

    exp = Experiment(name, scheduler, work_dir, out_dir,
                     proc_entries, executables)
    exp.run_exp()


def main():
    opts, args = parse_args()

    scheduler  = opts.scheduler
    duration   = opts.duration
    param_file = opts.param_file
    out_base   = os.path.abspath(opts.out_dir)

    args = args or [opts.sched_file]

    for exp in args:
        path = "%s/%s" % (os.getcwd(), exp)

        if not os.path.exists(path):
            raise IOError("Invalid experiment: %s" % path)

        if os.path.isdir(exp):
            path = "%s%s" % (path, opts.sched_file)

        load_experiment(path, scheduler, duration, param_file, out_base)


if __name__ == '__main__':
    main()
