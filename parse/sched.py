import config.config as conf
import os
import re
import numpy as np
import subprocess

from collections import namedtuple
from point import Measurement

Task = namedtuple('Task', ['pid', 'period'])

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
    reg = r"PARAM.*?(\d+).*?cost:\s+[\d\.]+ms.*?period.*?([\d.]+)"
    return [Task(x[0], x[1]) for x in re.findall(reg, data)]

def extract_tardy_vals(data, exp_point):
    ratios = []
    tards = []

    for t in get_tasks(data):
        reg = r"TARDY.*?" + t.pid + "/(\d+).*?Tot.*?([\d.]+).*?ms.*([\d.]+).*?ms.*?([\d.]+)"
        matches = re.findall(reg, data)
        if len(matches) != 0:
            jobs = float(matches[0][0])
            total_tard = float(matches[0][1])
            # max_tard = float(matches[0][2])
            misses = float(matches[0][3])
            rel_tard = (total_tard / jobs) / float(t.period)
            if misses != 0:
                miss_ratio = (misses / jobs)
            else:
                miss_ratio = 0

            ratios.append(miss_ratio)
            tards.append(rel_tard)

    for (array, name) in ((tards, "rel-tard"), (ratios, "miss-ratio")):
        exp_point[name] = Measurement().from_array(array)

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

    exp_point['var'] = Measurement().from_array(varz)

def get_sched_data(data_file, result):
    with open(data_file, 'r') as f:
        data = f.read()

        # if conf != BASE:
        #     (our_values, their_values) = extract_exec_vals(our_data, their_data)
        #     conf_result = get_stats(our_values, their_values)
        #     for key in conf_result.keys():
        #         result[key][conf] = conf_result[key]

        extract_tardy_vals(data, result)
        extract_variance(data, result)
