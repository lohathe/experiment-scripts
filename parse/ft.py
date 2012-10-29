import config.config as conf
import os
import re
import shutil as sh
import subprocess

from point import Measurement,Type

def get_ft_output(data_dir, out_dir, force=False):
    """
    Create and return files containing sorted and analyzed overhead data
    """
    bin_file = conf.FILES['ft_data'] + "$"
    bins = [f for f in os.listdir(data_dir) if re.match(bin_file, f)]

    FT_DATA_NAME = "scheduler=x-ft"
    output_file  = "{}/out-ft".format(out_dir)

    if os.path.isfile(output_file):
        if force:
            os.remove(output_file)
        else:
            print("ft-output already exists for %s" % data_dir)
            return output_file

    if len(bins) != 0:
        err_file = open("%s/err-ft" % out_dir, 'w')
        # Need to make a copy of the original data file so scripts can change it
        sh.copyfile("{}/{}".format(data_dir, bins[0]),
                    "{}/{}".format(out_dir, FT_DATA_NAME))

        subprocess.call([conf.BINS['sort'], FT_DATA_NAME],
                        cwd=out_dir, stderr=err_file, stdout=err_file)
        subprocess.call([conf.BINS['split'], FT_DATA_NAME],
                        cwd=out_dir, stderr=err_file, stdout=err_file)

        # Previous subprocesses just spit out all these intermediate files
        bins = [f for f in os.listdir(out_dir) if re.match(".*overhead=.*bin", f)]
        bins = [f for f in bins if os.stat("%s/%s"%(out_dir, f)).st_size]

        # Analyze will summarize those
        # todo pass in f
        cmd_arr = [conf.BINS['analyze']]
        print("cmd arr: %s-%s" % (cmd_arr, bins))
        cmd_arr.extend(bins)
        with open(output_file, "w") as f:
            subprocess.call(cmd_arr, cwd=out_dir, stdout=f, stderr=err_file)
    else:
        return None
    return output_file

def extract_ft_data(data_file, result, overheads):
    rstr = r",(?:\s+[^\s]+){3}.*?([\d\.]+).*?([\d\.]+),(?:\s+[^\s]+){3}.*?([\d\.]+)"

    with open(data_file) as f:
        data = f.read()

    for ovh in overheads:
        measure = Measurement("%s-%s" % (data_file, ovh))
        vals = re.findall(r"\s+{}".format(ovh.replace('_','-')) + rstr, data);
        if len(vals) != 0:
            vals = vals[0]
            measure[Type.Max] = float(vals[0])
            measure[Type.Avg] = float(vals[1])
            measure[Type.Var] = float(vals[2])
            result[ovh] = measure

    return result
