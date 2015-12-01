"""
    Skipping the "gen_exps.py" script.
    Assuming the input are provided in a text file in the form:

    $Task1Name $Task1WCET $Task1Period
    $Task2Name $Task2WCET $Task2Period
    ...
    $TasknName $TasknWCET $TasknPeriod

    Parameters must be 3 per line, white-space separated.
    WCET and Period must be expressed in microseconds.

    Output is a folder that can directly be used by "run_exps.py" script.
    """

import sys
import os
import shutil as sh
import schedcat.model.tasks as tasks
import gen.edf_generators as generators
from copy import deepcopy

CPU_COUNT = 16
DURATION = 10
OUT_DIR = "/home/luca/Documents/Workspace/newscript/experiment-scripts/exps/temp"
IN_DIR = "/home/luca/Documents/Workspace/newscript/experiment-scripts/exps/temp"
INPUT_FILE = "input2"

params = {'cpus': CPU_COUNT,
          'clusters': CPU_COUNT,
          'release_master': False,
          'durations': DURATION,
          'mutils': 0.0}

def parse_input( fname ):
    taskSet = []
    try:
        f = open(fname, "r")
        for line in f:
            splitted = line.split(" ")
            taskSet.append(tasks.SporadicTask(id=splitted[0],
                                              exec_cost=int(splitted[1]),
                                              period=int(splitted[2]),
                                              deadline=int(splitted[2])) )
    except Exception, e:
        sys.stderr.write("Error opening/parsing the file {}\n".format(fname))
        sys.stderr.write(str(e)+"\n")
    finally:
        f.close()
    return taskSet


""" assume:
    1) rootFolder exists (without trailing separator)
    2) taskSet is a list of SporadicTasks as created by "parse_input"
    3) params['mutil'] = total utilization of the taskset
    """
def prepare( generator, rootFolder, taskSet ):

    if os.path.isdir( rootFolder ):
        sh.rmtree( rootFolder )
    os.mkdir( rootFolder )


    generator.out_dir = rootFolder
    generator.tasks = taskSet

    generator._customize(taskSet, params)

    generator._write_schedule(dict(params.items() + [('task_set', taskSet)]))
    generator._write_params(params)

    return True


def prepare_all():
    ts = parse_input( IN_DIR + "/" + INPUT_FILE )

    prepare(generators.PedfGenerator({}),
            OUT_DIR + "/PEDF",
            deepcopy(ts))
    prepare(generators.GedfGenerator({}),
            OUT_DIR + "/GEDF",
            deepcopy(ts))
    prepare(generators.RUNGenerator({}),
            OUT_DIR + "/RUN",
            deepcopy(ts))
    prepare(generators.QPSGenerator({}),
            OUT_DIR + "/QPS",
            deepcopy(ts))

    print "DONE PREPARING EXPERIMENTS."

prepare_all()

"""
PARAMS = {"autils": 0.0, "clusters": CPU_COUNT, "cpus": CPU_COUNT,
          "duration": DURATION, "release_master": False, "scheduler": "LINUX"}

def write_param_file( folder, autils, scheduler ):
    try:
        PARAMS["scheduler"] = scheduler
        PARAMS["autils"] = autils
        f = open( folder+"/params.py", "w" )
        pprint.pprint( PARAMS, f )
    except:
        sys.stderr.write("Error creating 'param.py' in folder {} for {}"+
                        "\n".format(folder, scheduler))
    finally:
        PARAMS["scheduler"] = "LINUX"
        PARAMS["autils"] = 0.0
        f.close()

def write_sched_file( folder, content ):
    try:
        f = open( folder+"/sched.py", "w" )
        f.write( content )
    except:
        sys.stderr.write("Error creating 'sched.py' in folder {}"+
                        "\n".format(folder))
    finally:
        f.close()
"""