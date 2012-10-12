"""
TODO: No longer very pythonic, lot of duplicate code
"""

import config.config as conf
import os
import re
import numpy as np
import subprocess

from collections import namedtuple,defaultdict
from point import Measurement,Type

PARAM_RECORD = r"(?P<RECORD>" +\
  r"PARAM *?(?P<PID>\d+)\/.*?" +\
  r"cost:\s+(?P<WCET>[\d\.]+)ms.*?" +\
  r"period.*?(?P<PERIOD>[\d.]+)ms.*?" +\
  r"part.*?(?P<CPU>\d+)[, ]*" +\
  r"(?:class=(?P<CLASS>\w+))?[, ]*" +\
  r"(?:level=(?P<LEVEL>\w+))?).*$"
EXIT_RECORD = r"(?P<RECORD>" +\
  r"TASK_EXIT *?(?P<PID>\d+)/.*?" +\
  r"Avg.*?(?P<AVG>\d+).*?" +\
  r"Max.*?(?P<MAX>\d+))"
TARDY_RECORD = r"(?P<RECORD>" +\
  r"TARDY.*?(?P<PID>\d+)/(?P<JOB>\d+).*?" +\
  r"Tot.*?(?P<TOTAL>[\d\.]+).*?ms.*?" +\
  r"(?P<MAX>[\d\.]+).*?ms.*?" +\
  r"(?P<MISSES>[\d\.]+))"
COMPLETION_RECORD = r"(?P<RECORD>" +\
  r"COMPLETION.*?(?P<PID>\d+)/.*?" +\
  r"(?P<EXEC>[\d\.]+)ms)"

TaskConfig = namedtuple('TaskConfig', ['cpu','wcet','period','type','level'])
Task = namedtuple('Task', ['pid', 'config'])

class LeveledArray(object):
    """
    Groups statistics by the level of the task to which they apply
    """
    def __init__(self, name):
        self.name = name
        self.vals = defaultdict(lambda:[])

    def add(self, task, value):
        self.vals[task.config.level] += [value]

    def write_measurements(self, result):
        for level, arr in self.vals.iteritems():
            name = "%s%s" % ("%s-" % level if level else "", self.name)
            result[name] = Measurement(name).from_array(arr)

def get_st_output(data_dir, out_dir, force=False):
    """
    Create and return files containing unpacked sched data
    """
    bin_files = conf.FILES['sched_data'].format(".*")
    bins = [f for f in os.listdir(data_dir) if re.match(bin_files, f)]

    output_file = "%s/out-st" % out_dir

    if os.path.isfile(output_file):
        if force:
            os.remove(output_file)
        else:
            print("st-output already exists for %s" % data_dir)
            return output_file

    if len(bins) != 0:
        cmd_arr = [conf.BINS['st_show']]
        cmd_arr.extend(bins)
        with open(output_file, "w") as f:
            subprocess.call(cmd_arr, cwd=data_dir, stdout=f)
    else:
        return None
    return output_file

def get_tasks(data):
    ret = []
    for match in re.finditer(PARAM_RECORD, data, re.M):
        try:
            t = Task( int(match.group('PID')),
                      TaskConfig( int(match.group('CPU')),
                                  float(match.group('WCET')),
                                  float(match.group('PERIOD')),
                                  match.group("CLASS"),
                                  match.group("LEVEL")))
            if not (t.config.period and t.pid):
                raise Exception()
            ret += [t]
        except Exception as e:
            raise Exception("Invalid task record: %s\nparsed:\n\t%s\n\t%s" %
                            (e, match.groupdict(), match.group('RECORD')))
    return ret

def get_task_dict(data):
    tasks_list = get_tasks(data)
    tasks_dict = {}
    for t in tasks_list:
        tasks_dict[t.pid] = t
    return tasks_dict

def get_task_exits(data):
    ret = []
    for match in re.finditer(EXIT_RECORD, data):
        try:
            m = Measurement( int(match.group('PID')),
                             {Type.Max : float(match.group('MAX')),
                              Type.Avg : float(match.group('AVG'))})
            for (type, value) in m:
                if not value: raise Exception()
        except:
                raise Exception("Invalid exit record, parsed:\n\t%s\n\t%s" %
                                (match.groupdict(), m.group('RECORD')))

        ret += [m]
    return ret


def extract_tardy_vals(task_dict, data, exp_point):
    ratios    = LeveledArray("miss-ratio")
    avg_tards = LeveledArray("avg-rel-tardiness")
    max_tards = LeveledArray("max-rel-tardiness")

    for match in re.finditer(TARDY_RECORD, data):
        try:
            pid  = int(match.group("PID"))
            jobs = int(match.group("JOB"))
            misses = int(match.group("MISSES"))
            total_tard = float(match.group("TOTAL"))
            max_tard   = float(match.group("MAX"))

            if not (jobs and pid): raise Exception()
        except:
            raise Exception("Invalid tardy record:\n\t%s\n\t%s" %
                            (match.groupdict(), match.group("RECORD")))

        if pid not in task_dict:
            raise Exception("Invalid pid '%d' in tardy record:\n\t%s" %
                            match.group("RECORD"))

        t = task_dict[pid]
        avg_tards.add(t, total_tard / (jobs * t.config.period))
        max_tards.add(t, max_tard / t.config.period)
        ratios.add(t, misses / jobs)

    ratios.write_measurements(exp_point)
    avg_tards.write_measurements(exp_point)
    max_tards.write_measurements(exp_point)

def extract_variance(task_dict, data, exp_point):
    varz = LeveledArray("exec-variance")
    completions = defaultdict(lambda: [])
    missed = defaultdict(lambda: int())

    for match in re.finditer(COMPLETION_RECORD, data):
        try:
            pid = int(match.group("PID"))
            duration = float(match.group("EXEC"))

            # Last (exit) record often has exec time of 0
            missed[pid] += not bool(duration)

            if missed[pid] > 1 or not pid: raise Exception()
        except:
            raise Exception("Invalid completion record, missed - %d:"
                            "\n\t%s\n\t%s" % (missed[pid], match.groupdict(),
                                              match.group("RECORD")))
        completions[pid] += [duration]

    for pid, durations in completions.iteritems():
        job_times = np.array(durations)

        # Coefficient of variation
        cv = job_times.std() / job_times.mean()
        # Correction, assuming normal distributions
        corrected = (1 + 1/(4 * len(job_times))) * cv

        varz.add(task_dict[pid], corrected)

    varz.write_measurements(exp_point)

def config_exit_stats(task_dict, file):
    with open(file, 'r') as f:
        data = f.read()

    # Dictionary of task exit measurements by pid
    exits = get_task_exits(data)
    exit_dict = dict((e.id, e) for e in exits)

    # Dictionary where keys are configurations, values are list
    # of tasks with those configuratino
    config_dict = defaultdict(lambda: [])
    for t in task_dict.itervalues():
        config_dict[t.config] += [t]

    for config in config_dict:
        task_list = sorted(config_dict[config])

        # Replace tasks with corresponding exit stats
        if not t.pid in exit_dict:
            raise Exception("Missing exit record for task '%s' in '%s'" %
                            (t, file))
        exit_list = [exit_dict[t.pid] for t in task_list]
        config_dict[config] = exit_list

    return config_dict

saved_stats = {}
def get_base_stats(base_file):
    if base_file in saved_stats:
        return saved_stats[base_file]
    with open(base_file, 'r') as f:
        data = f.read()
    result = config_exit_stats(data)
    saved_stats[base_file] = result
    return result

def extract_scaling_data(task_dict, data, result, base_file):
    # Generate trees of tasks with matching configurations
    data_stats = config_exit_stats(data)
    base_stats = get_base_stats(base_file)

    # Scaling factors are calculated by matching groups of tasks with the same
    # config, then comparing task-to-task exec times in order of PID within
    # each group
    max_scales = LeveledArray("max-scaling")
    avg_scales = LeveledArray("avg-scaling")

    for config in data_stats:
        if len(data_stats[config]) != len(base_stats[config]):
            # Quit, we are missing a record and can't guarantee
            # a task-to-task comparison
            continue
        for data_stat, base_stat in zip(data_stats[config],base_stats[config]):
            # How much larger is their exec stat than ours?
            avg_scale = float(base_stat[Type.Avg]) / float(base_stat[Type.Avg])
            max_scale = float(base_stat[Type.Max]) / float(base_stat[Type.Max])

            task = task_dict[data_stat.id]

            avg_scales.add(task, avg_scale)
            max_scales.add(task, max_scale)

    avg_scales.write_measurements(result)
    max_scales.write_measurements(result)

def extract_sched_data(data_file, result, base_file):
    with open(data_file, 'r') as f:
        data = f.read()

    task_dict = get_task_dict(data)

    extract_tardy_vals(task_dict, data, result)
    extract_variance(task_dict, data, result)

    if (base_file):
        extract_scaling_data(task_dict, data, result, base_file)
