#!/usr/bin/env python
from __future__ import print_function

import common as com
import os
import pprint
import re
import shutil
import sys
import run.tracer as trace

from config.config import PARAMS,DEFAULTS
from collections import namedtuple
from optparse import OptionParser
from parse.enum import Enum
from run.executable.executable import Executable
from run.experiment import Experiment,ExperimentDone,SystemCorrupted
from run.proc_entry import ProcEntry

'''Maximum times an experiment will be retried'''
MAX_RETRY = 5

'''Customizable experiment parameters'''
ExpParams = namedtuple('ExpParams', ['scheduler', 'duration', 'tracers',
                                     'kernel', 'config_options', 'file_params',
                                     'pre_script', 'post_script'])
'''Tracked with each experiment'''
ExpState = Enum(['Failed', 'Succeeded', 'Invalid', 'Done', 'None'])
ExpData  = com.recordtype('ExpData', ['name', 'params', 'sched_file', 'out_dir',
                                      'retries', 'state'])
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
                      help='directory for data output',
                      default=DEFAULTS['out-run'])
    parser.add_option('-p', '--params', dest='param_file',
                      help='file with experiment parameters')
    parser.add_option('-c', '--schedule-file', dest='sched_file',
                      help='name of schedule files within directories',
                      default=DEFAULTS['sched_file'])
    parser.add_option('-f', '--force', action='store_true', default=False,
                      dest='force', help='overwrite existing data')
    parser.add_option('-j', '--jabber', metavar='username@domain',
                      dest='jabber', default=None,
                      help='send a jabber message when an experiment completes')
    parser.add_option('-e', '--email', metavar='username@server',
                      dest='email', default=None,
                      help='send an email when all experiments complete')
    parser.add_option('-r', '--retry', dest='retry',
                      action='store_true', default=False,
                      help='retry failed experiments')

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
            prog = match.group("PROG") or DEFAULTS['prog']
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
                sys.stderr.write("WARNING: non-existent file '%s' " % arg +
                                 "may be referenced:\n\t%s" % sched_file)

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


def run_script(script_params, exp, exp_dir, out_dir):
    '''Run an executable (arguments optional)'''
    if not script_params:
        return

    # Split into arguments and program name
    if type(script_params) != type([]):
        script_params = [script_params]

    exp.log("Running %s" % script_params.join(" "))

    script_name = script_params.pop(0)
    script = com.get_executable(script_name, cwd=exp_dir)

    out  = open('%s/%s-out.txt' % (out_dir, script_name), 'w')
    prog = Executable(script, script_params, cwd=out_dir,
                      stderr_file=out, stdout_file=out)

    prog.execute()
    prog.wait()

    out.close()


def make_exp_params(cmd_scheduler, cmd_duration, sched_dir, param_file):
    '''Return ExpParam with configured values of all hardcoded params.'''
    kernel = copts = ""

    # Load parameter file
    param_file = param_file or "%s/%s" % (sched_dir, DEFAULTS['params_file'])
    if os.path.isfile(param_file):
        fparams = com.load_params(param_file)
    else:
        fparams = {}

    scheduler = cmd_scheduler or fparams[PARAMS['sched']]
    duration  = cmd_duration  or fparams[PARAMS['dur']] or\
                DEFAULTS['duration']

    # Experiments can specify required kernel name
    if PARAMS['kernel'] in fparams:
        kernel = fparams[PARAMS['kernel']]

    # Or required config options
    if PARAMS['copts'] in fparams:
        copts = fparams[PARAMS['copts']]

    # Or required tracers
    requested = []
    if PARAMS['trace'] in fparams:
        requested = fparams[PARAMS['trace']]
    tracers = trace.get_tracer_types(requested)

    # Or scripts to run before and after experiments
    def get_script(name):
        return fparams[name] if name in fparams else None
    pre_script  = get_script('pre')
    post_script = get_script('post')

    # But only these two are mandatory
    if not scheduler:
        raise IOError("No scheduler found in param file!")
    if not duration:
        raise IOError("No duration found in param file!")

    return ExpParams(scheduler=scheduler, kernel=kernel, duration=duration,
                     config_options=copts, tracers=tracers, file_params=fparams,
                     pre_script=pre_script, post_script=post_script)

def run_experiment(data, start_message, ignore, jabber):
    '''Load and parse data from files and run result.'''
    if not os.path.isfile(data.sched_file):
        raise IOError("Cannot find schedule file: %s" % data.sched_file)

    dir_name, fname = os.path.split(data.sched_file)
    work_dir = "%s/tmp" % dir_name

    procs, execs = load_schedule(data.name, data.sched_file, data.params.duration)

    exp = Experiment(data.name, data.params.scheduler, work_dir,
                     data.out_dir, procs, execs, data.params.tracers)

    exp.log(start_message)

    if not ignore:
        verify_environment(data.params)

    run_script(data.params.pre_script, exp, dir_name, work_dir)

    exp.run_exp()

    run_script(data.params.post_script, exp, dir_name, data.out_dir)

    if jabber:
        jabber.send("Completed '%s'" % data.name)

    # Save parameters used to run dataeriment in out_dir
    out_params = dict([(PARAMS['sched'],  data.params.scheduler),
                       (PARAMS['tasks'],  len(execs)),
                       (PARAMS['dur'],    data.params.duration)] +
                       data.params.file_params.items())

    # Feather-trace clock frequency saved for accurate overhead parsing
    ft_freq = com.ft_freq()
    if ft_freq:
        out_params[PARAMS['cycles']] = ft_freq

    out_param_f = "%s/%s" % (data.out_dir, DEFAULTS['params_file'])
    with open(out_param_f, 'w') as f:
        pprint.pprint(out_params, f)


def make_paths(exp, opts, out_base_dir):
    '''Translate experiment name to (schedule file, output directory) paths'''
    path = "%s/%s" % (os.getcwd(), exp)
    out_dir = "%s/%s" % (out_base_dir, os.path.split(exp.strip('/'))[1])

    if not os.path.exists(path):
        raise IOError("Invalid experiment: %s" % path)

    if opts.force and os.path.exists(out_dir):
        shutil.rmtree(out_dir)

    if os.path.isdir(path):
        sched_file = "%s/%s" % (path, opts.sched_file)
    else:
        sched_file = path

    return sched_file, out_dir


def get_common_header(args):
    common = ""
    done = False

    if len(args) == 1:
        return common

    while not done:
        common += args[0][len(common)]
        for path in args:
            if path.find(common, 0, len(common)):
                done = True
                break

    return common[:len(common)-1]


def get_exps(opts, args, out_base_dir):
    '''Return list of ExpDatas'''

    if not args:
        if os.path.exists(opts.sched_file):
            # Default to sched_file in current directory
            sys.stderr.write("Reading schedule from %s.\n" % opts.sched_file)
            args = [opts.sched_file]
        elif os.path.exists(DEFAULTS['out-gen']):
            # Then try experiments created by gen_exps
            sys.stderr.write("Reading schedules from %s/*.\n" % DEFAULTS['out-gen'])
            sched_dirs = os.listdir(DEFAULTS['out-gen'])
            args = ['%s/%s' % (DEFAULTS['out-gen'], d) for d in sched_dirs]
        else:
            sys.stderr.write("Run with -h to view options.\n");
            sys.exit(1)

    # Part of arg paths which is identical for each arg
    common = get_common_header(args)

    exps = []
    for path in args:
        sched_file, out_dir = make_paths(path, opts, out_base_dir)
        name = path[len(common):]

        sched_dir  = os.path.split(sched_file)[0]
        exp_params = make_exp_params(opts.scheduler, opts.duration,
                                     sched_dir, opts.param_file)

        exps += [ExpData(name, exp_params, sched_file, out_dir,
                         0, ExpState.None)]

    return exps


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


def run_exps(exps, opts):
    jabber = setup_jabber(opts.jabber) if opts.jabber else None

    exps_remaining = list(enumerate(exps))
    while exps_remaining:
        i, exp = exps_remaining.pop(0)

        verb = "Loading" if exp.state == ExpState.None else "Re-running failed"
        start_message = "%s experiment %d of %d." % (verb, i+1, len(exps))

        try:
            run_experiment(exp, start_message, opts.ignore, jabber)
            exp.state = ExpState.Succeeded
        except KeyboardInterrupt:
            sys.stderr.write("Keyboard interrupt, quitting\n")
            break
        except ExperimentDone:
            sys.stderr.write("Experiment already completed at '%s'\n" % exp.out_dir)
            exp.state = ExpState.Done
        except (InvalidKernel, InvalidConfig) as e:
            sys.stderr.write("Invalid environment for experiment '%s'\n" % exp.name)
            sys.stderr.write("%s\n" % e)
            exp.state = ExpState.Invalid
        except SystemCorrupted as e:
            sys.stderr.write("System is corrupted! Fix state before continuing.\n")
            sys.stderr.write("%s\n" % e)
            exp.state = ExpState.Failed
            if not opts.retry:
                break
            else:
                sys.stderr.write("Remaining experiments may fail\n")
        except Exception as e:
            sys.stderr.write("Failed experiment %s\n" % exp.name)
            sys.stderr.write("%s\n" % e)
            exp.state = ExpState.Failed

        if exp.state is ExpState.Failed and opts.retry:
            if exp.retries < MAX_RETRY:
                exps_remaining += [(i, exp)]
                exp.retries += 1
            else:
                sys.stderr.write("Hit maximum retries of %d\n" % MAX_RETRY)

def main():
    opts, args = parse_args()

    email = setup_email(opts.email) if opts.email else None

    out_base = os.path.abspath(opts.out_dir)
    created  = False
    if not os.path.exists(out_base):
        created = True
        os.mkdir(out_base)

    exps = get_exps(opts, args, out_base)

    run_exps(exps, opts)

    def state_count(state):
        return len(filter(lambda x: x.state is state, exps))

    ran  = len(filter(lambda x: x.state is not ExpState.None, exps))
    succ = state_count(ExpState.Succeeded)

    message = "Experiments ran:\t%d of %d" % (ran, len(exps)) +\
      "\n  Successful:\t\t%d" % succ +\
      "\n  Failed:\t\t%d" % state_count(ExpState.Failed) +\
      "\n  Already Done:\t\t%d" % state_count(ExpState.Done) +\
      "\n  Invalid Environment:\t%d" % state_count(ExpState.Invalid)

    print(message)

    if email:
        email.send(message)
        email.close()

    if succ:
        sys.stderr.write("Successful experiment data saved in %s.\n" %
                         opts.out_dir)
    elif not os.listdir(out_base) and created:
        # Remove directory if no data was put into it
        os.rmdir(out_base)


if __name__ == '__main__':
    main()
