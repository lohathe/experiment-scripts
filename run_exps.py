#!/usr/bin/env python
from __future__ import print_function

import common as com
import config.config as conf
import os
import re
import shutil
import sys
import run.tracer as trace

from collections import namedtuple
from optparse import OptionParser
from run.executable.executable import Executable
from run.experiment import Experiment,ExperimentDone,ExperimentFailed,SystemCorrupted
from run.proc_entry import ProcEntry

'''Customizable experiment parameters'''
ExpParams = namedtuple('ExpParams', ['scheduler', 'duration', 'tracers',
                                     'kernel', 'config_options'])
'''Comparison of requested versus actual kernel compile parameter value'''
ConfigResult = namedtuple('ConfigResult', ['param', 'wanted', 'actual'])

class InvalidKernel(Exception):
    def __init__(self, kernel):
        self.kernel = kernel

    def __str__(self):
        return "Kernel name does not match '%s'." % self.kernel


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
    parser.add_option('-j', '--jabber', metavar='username@domain',
                      dest='jabber', default=None,
                      help='send a jabber message when an experiment completes')
    parser.add_option('-e', '--email', metavar='username@server',
                      dest='email', default=None,
                      help='send an email when all experiments complete')

    return parser.parse_args()


def convert_data(data):
    '''Convert a non-python schedule file into the python format'''
    regex = re.compile(
        r"(?P<PROC>^"
            r"(?P<HEADER>/proc/[\w\-]+?/)?"
            r"(?P<ENTRY>[\w\-\/]+)"
              r"\s*{\s*(?P<CONTENT>.*?)\s*?}$)|"
        r"(?P<TASK>^"
            r"(?:(?P<PROG>[^\d\-\s][\w\.]*?) )?\s*"
            r"(?P<ARGS>[\w\-_\d\. \=]+)\s*$)",
        re.S|re.I|re.M)

    procs = []
    tasks = []

    for match in regex.finditer(data):
        if match.group("PROC"):
            header = match.group("HEADER") or "/proc/litmus/"
            loc  = "{}{}".format(header, match.group("ENTRY"))
            proc = (loc, match.group("CONTENT"))
            procs.append(proc)
        else:
            prog = match.group("PROG") or conf.DEFAULTS['prog']
            spin = (prog, match.group("ARGS"))
            tasks.append(spin)

    return {'proc' : procs, 'task' : tasks}


def fix_paths(schedule, exp_dir, sched_file):
    '''Replace relative paths of command line arguments with absolute ones.'''
    for (idx, (task, args)) in enumerate(schedule['task']):
        for arg in re.split(" +", args):
            abspath = "%s/%s" % (exp_dir, arg)
            if os.path.exists(abspath):
                args = args.replace(arg, abspath)
                break
            elif re.match(r'.*\w+\.[a-zA-Z]\w*', arg):
                print("WARNING: non-existent file '%s' may be referenced:\n\t%s"
                      % (arg, sched_file))

        schedule['task'][idx] = (task, args)


def load_schedule(name, fname, duration):
    '''Turn schedule file @fname into ProcEntry's and Executable's which execute
    for @duration time.'''
    with open(fname, 'r') as f:
        data = f.read().strip()
    try:
        schedule = eval(data)
    except:
        schedule = convert_data(data)

    sched_dir = os.path.split(fname)[0]

    # Make paths relative to the file's directory
    fix_paths(schedule, sched_dir, fname)

    proc_entries = []
    executables  = []

    # Create proc entries
    for entry_conf in schedule['proc']:
        proc_entries += [ProcEntry(*entry_conf)]

    # Create executables
    for task_conf in schedule['task']:
        if len(task_conf) != 2:
            raise Exception("Invalid task conf %s: %s" % (task_conf, name))

        (task, args) = (task_conf[0], task_conf[1])

        real_task = com.get_executable(task, sched_dir)

        # Last argument must always be duration
        real_args = args.split() + [duration]

        # All spins take a -w flag
        if re.match(".*spin$", real_task) and '-w' not in real_args:
            real_args = ['-w'] + real_args

        executables += [Executable(real_task, real_args)]

    return proc_entries, executables


def verify_environment(exp_params):
    '''Raise an exception if the current system doesn't match that required
    by @exp_params.'''
    if exp_params.kernel and not re.match(exp_params.kernel, com.kernel()):
        raise InvalidKernel(exp_params.kernel)

    if exp_params.config_options:
        results = []
        for param, wanted in exp_params.config_options.iteritems():
            try:
                actual = com.get_config_option(param)
            except IOError:
                actual = None
            if not str(wanted) == str(actual):
                results += [ConfigResult(param, wanted, actual)]

        if results:
            raise InvalidConfig(results)


def run_parameter(exp_dir, out_dir, params, param_name):
    '''Run an executable (arguments optional) specified as a configurable
    @param_name in @params.'''
    if conf.PARAMS[param_name] not in params:
        return

    script_params = params[conf.PARAMS[param_name]]

    # Split into arguments and program name
    if type(script_params) != type([]):
        script_params = [script_params]
    script_name = script_params.pop(0)

    script = com.get_executable(script_name, cwd=exp_dir)

    out  = open('%s/%s-out.txt' % (out_dir, param_name), 'w')
    prog = Executable(script, script_params,
                      stderr_file=out, stdout_file=out)
    prog.cwd = out_dir

    prog.execute()
    prog.wait()

    out.close()


def get_exp_params(cmd_scheduler, cmd_duration, file_params):
    '''Return ExpParam with configured values of all hardcoded params.'''
    kernel = copts = ""

    scheduler = cmd_scheduler or file_params[conf.PARAMS['sched']]
    duration  = cmd_duration  or file_params[conf.PARAMS['dur']] or\
                conf.DEFAULTS['duration']

    # Experiments can specify required kernel name
    if conf.PARAMS['kernel'] in file_params:
        kernel = file_params[conf.PARAMS['kernel']]

    # Or required config options
    if conf.PARAMS['copts'] in file_params:
        copts = file_params[conf.PARAMS['copts']]

    # Or required tracers
    requested = []
    if conf.PARAMS['trace'] in file_params:
        requested = file_params[conf.PARAMS['trace']]
    tracers = trace.get_tracer_types(requested)

    # But only these two are mandatory
    if not scheduler:
        raise IOError("No scheduler found in param file!")
    if not duration:
        raise IOError("No duration found in param file!")

    return ExpParams(scheduler=scheduler, kernel=kernel, duration=duration,
                     config_options=copts, tracers=tracers)


def load_experiment(sched_file, cmd_scheduler, cmd_duration,
                    param_file, out_dir, ignore, jabber):
    '''Load and parse data from files and run result.'''
    if not os.path.isfile(sched_file):
        raise IOError("Cannot find schedule file: %s" % sched_file)

    dir_name, fname = os.path.split(sched_file)
    exp_name = os.path.split(dir_name)[1] + "/" + fname
    work_dir = "%s/tmp" % dir_name

    # Load parameter file
    param_file = param_file or \
      "%s/%s" % (dir_name, conf.DEFAULTS['params_file'])
    if os.path.isfile(param_file):
        file_params = com.load_params(param_file)
    else:
        file_params = {}

    # Create input needed by Experiment
    exp_params = get_exp_params(cmd_scheduler, cmd_duration, file_params)
    procs, execs = load_schedule(exp_name, sched_file, exp_params.duration)

    exp = Experiment(exp_name, exp_params.scheduler, work_dir, out_dir,
                     procs, execs, exp_params.tracers)

    if not ignore:
        verify_environment(exp_params)

    run_parameter(dir_name, work_dir, file_params, 'pre')

    exp.run_exp()

    run_parameter(dir_name, out_dir, file_params, 'post')

    if jabber:
        jabber.send("Completed '%s'" % exp_name)

    # Save parameters used to run experiment in out_dir
    out_params = dict(file_params.items() +
                      [(conf.PARAMS['sched'],  exp_params.scheduler),
                       (conf.PARAMS['tasks'],  len(execs)),
                       (conf.PARAMS['dur'],    exp_params.duration)])

    # Feather-trace clock frequency saved for accurate overhead parsing
    ft_freq = com.ft_freq()
    if ft_freq:
        out_params[conf.PARAMS['cycles']] = ft_freq

    with open("%s/%s" % (out_dir, conf.DEFAULTS['params_file']), 'w') as f:
        f.write(str(out_params))


def setup_jabber(target):
    try:
        from run.jabber import Jabber

        return Jabber(target)
    except ImportError:
        sys.stderr.write("Failed to import jabber. Is python-xmpp installed? " +
                         "Disabling instant messages.\n")
        return None

def setup_email(target):
    try:
        from run.emailer import Emailer

        return Emailer(target)
    except ImportError:
        message = "Failed to import email. Is smtplib installed?"
    except IOError:
        message = "Failed to create email. Is an smtp server active?"

    sys.stderr.write(message + " Disabling email message.\n")
    return None

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

    ran  = 0
    done = 0
    succ = 0
    failed = 0
    invalid = 0

    jabber = setup_jabber(opts.jabber) if opts.jabber else None
    email  = setup_email(opts.email) if opts.email else None

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
                            out_dir, opts.ignore, jabber)
            succ += 1
        except ExperimentDone:
            done += 1
            print("Experiment '%s' already completed at '%s'" % (exp, out_base))
        except (InvalidKernel, InvalidConfig) as e:
            invalid += 1
            print("Invalid environment for experiment '%s'" % exp)
            print(e)
        except KeyboardInterrupt:
            print("Keyboard interrupt, quitting")
            break
        except SystemCorrupted as e:
            print("System is corrupted! Fix state before continuing.")
            print(e)
            break
        except ExperimentFailed:
            print("Failed experiment %s" % exp)
            failed += 1

        ran += 1

    if not os.listdir(out_base) and created and not succ:
        os.rmdir(out_base)

    message = "Experiments ran:\t%d of %d" % (ran, len(args)) +\
      "\n  Successful:\t\t%d" % succ +\
      "\n  Failed:\t\t%d" % failed +\
      "\n  Already Done:\t\t%d" % done +\
      "\n  Invalid Environment:\t%d" % invalid

    print(message)

    if email:
        email.send(message)
        email.close()

if __name__ == '__main__':
    main()
