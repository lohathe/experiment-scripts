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

def get_st_output(data_dir, out_dir):
    bin_files = conf.FILES['sched_data'].format(".*")
    bins = [f for f in os.listdir(data_dir) if re.match(bin_files, f)]

    output_file = "%s/out-st" % out_dir

    if os.path.isfile(output_file):
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

def get_tasks_dict(data):
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
        

def extract_tardy_vals(data, exp_point):
    ratios    = []
    avg_tards = []
    max_tards = []

    tasks = get_tasks_dict(data)

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

        if pid not in tasks:
            raise Exception("Invalid pid '%d' in tardy record:\n\t%s" %
                            match.group("RECORD"))
        
        t = tasks[pid]
        avg_tards  += [ total_tard / (jobs * t.config.period) ]
        max_tards  += [ max_tard / t.config.period ]
        ratios     += [ misses / jobs ]

    exp_point["avg-rel-tard"] = Measurement().from_array(avg_tards)
    exp_point["max-rel-tard"] = Measurement().from_array(max_tards)
    exp_point["miss-ratio"]   = Measurement().from_array(ratios)

def extract_variance(data, exp_point):
    varz = []
    completions = defaultdict(lambda: [])

    for match in re.finditer(COMPLETION_RECORD, data):
        try:
            pid = int(match.group("PID"))
            duration = float(match.group("EXEC"))

            if not (duration and pid): raise Exception()
        except:
            raise Exception("Invalid completion record:\n\t%s\n\t%s" %
                            (match.groupdict(), match.group("RECORD")))
        completions[pid] += [duration]

    for (pid, durations) in completions:
        job_times = np.array(durations)

        # Coefficient of variation
        cv = job_times.std() / job_times.mean()
        # Correction, assuming normal distributions
        corrected = (1 + 1/(4 * len(job_times))) * cv

        varz.append(corrected)

    exp_point['exec-var'] = Measurement().from_array(varz)

def extract_sched_data(data_file, result):
    with open(data_file, 'r') as f:
        data = f.read()

    extract_tardy_vals(data, result)
    extract_variance(data, result)

def config_exit_stats(file):
    with open(file, 'r') as f:
        data = f.read()
        
    tasks = get_tasks(data)

    # Dictionary of task exit measurements by pid
    exits = get_task_exits(data)

    exit_dict = dict((e.id, e) for e in exits)

    # Dictionary where keys are configurations, values are list
    # of tasks with those configuratino
    config_dict = defaultdict(lambda: [])
    for t in tasks:
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
    result = config_exit_stats(base_file)
    saved_stats[base_file] = result
    return result

def extract_scaling_data(data_file, base_file, result):
    # Generate trees of tasks with matching configurations
    data_stats = config_exit_stats(data_file)
    base_stats = get_base_stats(base_file)

    # Scaling factors are calculated by matching groups of tasks with the same
    # config, then comparing task-to-task exec times in order of PID within
    # each group
    max_scales = []
    avg_scales = []

    for config in data_stats:
        if len(data_stats[config]) != len(base_stats[config]):
            # Quit, we are missing a record and can't guarantee
            # a task-to-task comparison
            continue
        for data_stat, base_stat in zip(data_stats[config],base_stats[config]):
            # How much larger is their exec stat than ours?
            avg_scale = float(base_stat[Type.Avg]) / float(base_stat[Type.Avg])
            max_scale = float(base_stat[Type.Max]) / float(base_stat[Type.Max])

            avg_scales += [avg_scale]
            max_scales += [max_scale]

    result['max-scale'] = Measurement().from_array(max_scales)
    result['avg-scale'] = Measurement().from_array(avg_scales)
