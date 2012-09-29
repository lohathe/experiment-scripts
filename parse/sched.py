"""
TODO: make regexes indexable by name

"""

import config.config as conf
import os
import re
import numpy as np
import subprocess

from collections import namedtuple,defaultdict
from point import Measurement,Type

TaskConfig = namedtuple('TaskConfig', ['cpu','wcet','period'])
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
    reg = r"PARAM *?(\d+)\/.*?cost:\s+([\d\.]+)ms.*?period.*?([\d.]+)ms.*?part.*?(\d+)"
    ret = []
    for match in re.findall(reg, data):
        t = Task(match[0], TaskConfig(match[3],match[1],match[2]))
        ret += [t]
    return ret

def get_task_exits(data):
    reg = r"TASK_EXIT *?(\d+)/.*?Avg.*?(\d+).*?Max.*?(\d+)"
    ret = []
    for match in re.findall(reg, data):
        m = Measurement(match[0], {Type.Max : match[2], Type.Avg : match[1]})
        ret += [m]
    return ret
        

def extract_tardy_vals(data, exp_point):
    ratios    = []
    avg_tards = []
    max_tards = []

    for t in get_tasks(data):
        reg = r"TARDY.*?" + t.pid + "/(\d+).*?Tot.*?([\d\.]+).*?ms.*?([\d\.]+).*?ms.*?([\d\.]+)"
        matches = re.findall(reg, data)
        if len(matches) != 0:
            jobs = float(matches[0][0])

            total_tard = float(matches[0][1])
            avg_tard = (total_tard / jobs) / float(t.config.period)
            max_tard = float(matches[0][2]) / float(t.config.period)

            misses = float(matches[0][3])
            if misses != 0:
                miss_ratio = (misses / jobs)
            else:
                miss_ratio = 0

            ratios    += [miss_ratio]
            avg_tards += [avg_tard]
            max_tards += [max_tard]

    exp_point["avg-rel-tard"] = Measurement().from_array(avg_tards)
    exp_point["max-rel-tard"] = Measurement().from_array(max_tards)
    exp_point["miss-ratio"] = Measurement().from_array(ratios)

def extract_variance(data, exp_point):
    varz = []
    for t in get_tasks(data):
        reg = r"COMPLETION.*?" + t.pid + r".*?([\d\.]+)ms"
        matches = re.findall(reg, data)

        if len(matches) == 0:
            return 0

        job_times = np.array(filter(lambda x: float(x) != 0, matches), dtype=np.float)

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
