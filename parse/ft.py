import config.config as conf
import numpy as np
import os
import re
import shutil as sh
import subprocess

from point import Measurement,Type

SPLIT_DATA_NAME = "overhead={}.bin"
FT_DATA_NAME    = "sorted-ft.bin"
FIELDS = ["Overhead", "samples", "max", "avg", "min", "med", "std", "var"]

def get_ft_output(data_dir, cycles, out_dir, force=False):
    """
    Create and return file containing analyzed overhead data
    """
    freg = conf.FILES['ft_data'] + "$"
    bins = [f for f in os.listdir(data_dir) if re.match(freg, f)]

    output_file  = "{}/out-ft".format(out_dir)

    if os.path.isfile(output_file):
        if force:
            os.remove(output_file)
        else:
            return output_file

    if len(bins) != 0:
        bin_file = "{}/{}".format(data_dir, bins[0])
        err_file = open("%s/err-ft" % out_dir, 'w')

        sorted_bin = sort_ft(bin_file, err_file, out_dir)
        make_data_file(sorted_bin, cycles, output_file, err_file, out_dir)

        os.remove(sorted_bin)

        return output_file
    else:
        return None
    return output_file

def fmt_cell(x):
    if type(x) == str:
        return "%15s" % x
    if type(x) == int:
        return "%15d" % x
    else:
        return "%15.3f" % x

def make_data_file(sorted_bin, cycles, out_fname, err_file, out_dir):
    """
    Create file containing all overhead information.
    """
    base_name = "{}/{}".format(out_dir, SPLIT_DATA_NAME)

    with open(out_fname, "w") as f:
        f.write("#%s" % ", ".join(fmt_cell(x) for x in FIELDS))
        f.write("\n")

        for event in conf.BASE_EVENTS:
                ovh_fname = base_name.format(event.replace("_", "-"))

                if os.path.exists(ovh_fname):
                    os.remove(ovh_fname)
                ovh_file = open(ovh_fname, 'w')

                # Extract matching overhead events into a seperate file
                cmd = [conf.BINS["split"], "-r", "-b", event, sorted_bin]
                ret = subprocess.call(cmd, cwd=out_dir,
                                      stderr=err_file, stdout=ovh_file)
                size = os.stat(ovh_fname).st_size

                if ret:
                    err_file.write("Failed with command: %s" % " ".join(cmd))
                if not size:
                    os.remove(ovh_fname)
                if not size or ret:
                    continue

                # Map and sort file for stats
                data = np.memmap(ovh_fname, dtype="float32", mode='c')
                data /= float(cycles) # Scale for processor speed
                data.sort()

                stats = [event, len(data), data[-1], np.mean(data), data[0],
                         np.median(data), np.std(data, ddof=1), np.var(data)]
                f.write(", ".join([fmt_cell(x) for x in stats]))
                f.write("\n")

                os.remove(ovh_fname)

def sort_ft(ft_file, err_file, out_dir):
    """
    Create and return file with sorted overheads from @ft_file.
    """
    out_fname = "{}/{}".format(out_dir, FT_DATA_NAME)

    # Sort happens in-place
    sh.copyfile(ft_file, out_fname)
    cmd = [conf.BINS['ftsort'], out_fname]
    ret = subprocess.call(cmd, cwd=out_dir, stderr=err_file, stdout=err_file)

    if ret:
        raise Exception("Sort failed with command: %s" % " ".join(cmd))

    return out_fname

def extract_ft_data(data_file, result, overheads):
    """
    Return exp point with overhead measurements from data_file
    """
    with open(data_file) as f:
        data = f.read()

    for ovh in overheads:
        regex = r"({}[^\n]*)".format(ovh)
        line = re.search(regex, data)

        if not line:
            continue

        vals = re.split(r"[,\s]+", line.groups(1)[0])

        measure = Measurement("%s-%s" % (data_file, ovh))
        measure[Type.Max] = float(vals[FIELDS.index("max")])
        measure[Type.Avg] = float(vals[FIELDS.index("avg")])
        measure[Type.Var] = float(vals[FIELDS.index("var")])

        result[ovh] = measure

    return result
