#!/usr/bin/env python
from __future__ import print_function

import config.config as conf
import run.litmus_util as lu
import os
import re
import shutil
import traceback

from common import load_params
from optparse import OptionParser
from run.executable.executable import Executable
from run.experiment import Experiment,ExperimentDone
from run.proc_entry import ProcEntry

def InvalidKernel(Exception):
    def __init__(self, kernel):
        self.kernel = kernel

def parse_args():
    parser = OptionParser("usage: %prog [options] [sched_file]... [exp_dir]...")

    parser.add_option('-s', '--scheduler', dest='scheduler',
                      help='scheduler for all experiments')
    parser.add_option('-d', '--duration', dest='duration', type='int',
                      help='duration (seconds) of tasks')
    parser.add_option('-o', '--out-dir', dest='out_dir',
                      help='directory for data output', default=("%s/run-data"%os.getcwd()))
    parser.add_option('-p', '--params', dest='param_file',
                      help='file with experiment parameters')
    parser.add_option('-c', '--schedule-file', dest='sched_file',
                      help='name of schedule files within directories',
                      default=conf.DEFAULTS['sched_file'])
    parser.add_option('-f', '--force', action='store_true', default=False,
                      dest='force', help='overwrite existing data')

    return parser.parse_args()


def convert_data(data):
    '''Convert a non-python schedule file into the python format'''
    regex = re.compile(
        r"(?P<PROC>^"
            r"(?P<HEADER>/proc/[\w\-]+?/)?"
            r"(?P<ENTRY>[\w\-\/]+)"
              r"\s*{\s*(?P<CONTENT>.*?)\s*?}$)|"
        r"(?P<SPIN>^"
            r"(?P<TYPE>\w+?spin)?\s*"
            r"(?P<ARGS>[\w\-_\d\. \=]+)\s*$)",
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

def fix_paths(schedule, exp_dir, sched_file):
    '''Replace relative paths of command line arguments with absolute ones.'''
    for (idx, (spin, args)) in enumerate(schedule['spin']):
        for arg in re.split(" +", args):
            abspath = "%s/%s" % (exp_dir, arg)
            if os.path.exists(abspath):
                args = args.replace(arg, abspath)
                break
            elif re.match(r'.*\w+\.\w+', arg):
                print("WARNING: non-existent file '%s' may be referenced:\n\t%s"
                      % (arg, sched_file))

        schedule['spin'][idx] = (spin, args)

def load_experiment(sched_file, scheduler, duration, param_file, out_dir):
    if not os.path.isfile(sched_file):
        raise IOError("Cannot find schedule file: %s" % sched_file)

    dirname = os.path.split(sched_file)[0]

    params = {}
    kernel = ""

    param_file = param_file or \
      "%s/%s" % (dirname, conf.DEFAULTS['params_file'])

    if os.path.isfile(param_file):
        params = load_params(param_file)
        scheduler = scheduler or params[conf.PARAMS['sched']]
        duration  = duration  or params[conf.PARAMS['dur']]

        # Experiments can specify required kernel name
        if conf.PARAMS['kernel'] in params:
            kernel = params[conf.PARAMS['kernel']]

    duration = duration or conf.DEFAULTS['duration']

    if not scheduler:
        raise IOError("Parameter scheduler not specified in %s" % (param_file))

    # Parse schedule file's intentions
    schedule = load_schedule(sched_file)
    work_dir = "%s/tmp" % dirname
    fix_paths(schedule, os.path.split(sched_file)[0], sched_file)

    run_exp(sched_file, schedule, scheduler, kernel, duration, work_dir, out_dir)

    # Save parameters used to run experiment in out_dir
    # Cycles is saved here for accurate overhead calculations later
    out_params = dict(params.items() +
                      [(conf.PARAMS['sched'],  scheduler),
                       (conf.PARAMS['dur'],    duration),
                       (conf.PARAMS['cycles'], lu.cpu_freq())])
    with open("%s/%s" % (out_dir, conf.DEFAULTS['params_file']), 'w') as f:
        f.write(str(out_params))

def load_schedule(fname):
    with open(fname, 'r') as f:
        data = f.read().strip()
    try:
        schedule = eval(data)
    except:
        schedule = convert_data(data)
    return schedule


def run_exp(name, schedule, scheduler, kernel, duration, work_dir, out_dir):
    proc_entries = []
    executables  = []

    if kernel and not lu.uname_matches(kernel):
        raise InvalidKernel(kernel)

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

        # if not conf.BINS[spin]:
        #     raise IndexError("No knowledge of program %s: %s" % (spin, name))

        real_spin = get_executable(spin, "")
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

    created = False
    if not os.path.exists(out_base):
        created = True
        os.mkdir(out_base)

    done = 0
    succ = 0
    failed = 0
    invalid = 0

    for exp in args:
        path = "%s/%s" % (os.getcwd(), exp)
        out_dir = "%s/%s" % (out_base, os.path.split(exp.strip('/'))[1])

        if not os.path.exists(path):
            raise IOError("Invalid experiment: %s" % path)

        if opts.force and os.path.exists(out_dir):
            shutil.rmtree(out_dir)

        if os.path.isdir(exp):
            path = "%s/%s" % (path, opts.sched_file)

        try:
            load_experiment(path, scheduler, duration, param_file, out_dir)
            succ += 1
        except ExperimentDone:
            done += 1
            print("Experiment '%s' already completed at '%s'" % (exp, out_base))
        except InvalidKernel:
            invalid += 1
        except:
            print("Failed experiment %s" % exp)
            traceback.print_exc()
            failed += 1

    if not os.listdir(out_base) and created and not succ:
        os.rmdir(out_base)

    print("Experiments run:\t%d" % len(args))
    print("  Successful:\t\t%d" % succ)
    print("  Failed:\t\t%d" % failed)
    print("  Already Done:\t\t%d" % done)
    print("  Wrong Kernel:\t\t%d" % invalid)


if __name__ == '__main__':
    main()
