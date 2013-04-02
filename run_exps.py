#!/usr/bin/env python
from __future__ import print_function

import common as com
import config.config as conf
import os
import re
import shutil
import traceback

from collections import namedtuple
from optparse import OptionParser
from run.executable.executable import Executable
from run.experiment import Experiment,ExperimentDone
from run.proc_entry import ProcEntry

class InvalidKernel(Exception):
    def __init__(self, kernel):
        self.kernel = kernel

    def __str__(self):
        return "Kernel name does not match '%s'." % self.kernel

ConfigResult = namedtuple('ConfigResult', ['param', 'wanted', 'actual'])
class InvalidConfig(Exception):
    def __init__(self, results):
        self.results = results

    def __str__(self):
        rstr = "'%s'%swanted: '%s', found: %s"
        messages = []
        for r in self.results:
            # For pretty alignment
            tabs = (3 - len(r.param)/8)
            messages += [rstr % (r.param, '\t'*tabs, r.wanted, r.actual)]

        return "Invalid kernel configuration " +\
               "(ignore configuration with -i option).\n" + "\n".join(messages)

def parse_args():
    parser = OptionParser("usage: %prog [options] [sched_file]... [exp_dir]...")

    parser.add_option('-s', '--scheduler', dest='scheduler',
                      help='scheduler for all experiments')
    parser.add_option('-i', '--ignore-environment', dest='ignore',
                      action='store_true', default=False,
                      help='run experiments even in invalid environments ')
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
            r"(?:(?P<TYPE>[^\d\-\s]\w*?) )?\s*"
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
            elif re.match(r'.*\w+\.[a-zA-Z]\w*', arg):
                print("WARNING: non-existent file '%s' may be referenced:\n\t%s"
                      % (arg, sched_file))

        schedule['spin'][idx] = (spin, args)

def verify_environment(kernel, copts):
    if kernel and not com.uname_matches(kernel):
        raise InvalidKernel(kernel)

    if copts:
        results = []
        for param, wanted in copts.iteritems():
            try:
                actual = com.get_config_option(param)
            except IOError:
                actual = None
            if not str(wanted) == str(actual):
                results += [ConfigResult(param, wanted, actual)]

        if results:
            raise InvalidConfig(results)

def load_experiment(sched_file, scheduler, duration,
                    param_file, out_dir, ignore):
    if not os.path.isfile(sched_file):
        raise IOError("Cannot find schedule file: %s" % sched_file)

    dir_name, fname = os.path.split(sched_file)
    exp_name = os.path.split(dir_name)[1] + "/" + fname

    params = {}
    kernel = copts = ""

    param_file = param_file or \
      "%s/%s" % (dir_name, conf.DEFAULTS['params_file'])

    if os.path.isfile(param_file):
        params = com.load_params(param_file)
        scheduler = scheduler or params[conf.PARAMS['sched']]
        duration  = duration  or params[conf.PARAMS['dur']]

        # Experiments can specify required kernel name
        if conf.PARAMS['kernel'] in params:
            kernel = params[conf.PARAMS['kernel']]
        # Or required config options
        if conf.PARAMS['copts'] in params:
            copts = params[conf.PARAMS['copts']]

    duration = duration or conf.DEFAULTS['duration']

    if not scheduler:
        raise IOError("Parameter scheduler not specified in %s" % (param_file))

    # Parse schedule file's intentions
    schedule = load_schedule(sched_file)
    work_dir = "%s/tmp" % dir_name

    fix_paths(schedule, os.path.split(sched_file)[0], sched_file)

    if not ignore:
        verify_environment(kernel, copts)

    run_exp(exp_name, schedule, scheduler, kernel, duration, work_dir, out_dir)

    # Save parameters used to run experiment in out_dir
    out_params = dict(params.items() +
                      [(conf.PARAMS['sched'],  scheduler),
                       (conf.PARAMS['tasks'],  len(schedule['spin'])),
                       (conf.PARAMS['dur'],    duration)])

    # Feather-trace clock frequency saved for accurate overhead parsing
    ft_freq = com.ft_freq()
    if ft_freq:
        out_params[conf.PARAMS['cycles']] = ft_freq

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

        real_spin = com.get_executable(spin, "")
        real_args = args.split()
        if re.match(".*spin", real_spin):
            real_args = ['-w'] + real_args + [duration]

        if not com.is_executable(real_spin):
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
            load_experiment(path, scheduler, duration, param_file,
                            out_dir, opts.ignore)
            succ += 1
        except ExperimentDone:
            done += 1
            print("Experiment '%s' already completed at '%s'" % (exp, out_base))
        except (InvalidKernel, InvalidConfig) as e:
            invalid += 1
            print("Invalid environment for experiment '%s'" % exp)
            print(e)
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
    print("  Invalid Environment:\t%d" % invalid)


if __name__ == '__main__':
    main()
