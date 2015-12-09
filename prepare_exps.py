#!/usr/bin/env python
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
from optparse import OptionParser

def parse_args():
    parser = OptionParser("usage: %prog [options]")

    parser.add_option('-o', '--out', default="",
                      dest='out',
                      help='directory for data output')
    parser.add_option('-i', '--input', default="",
                      dest='input',
                      help='file describing the task-set')
    parser.add_option('-c', '--cpucount', default=1, type='int',
                      dest='cpucount',
                      help='number cpu to use in the experiments')
    parser.add_option('-d', '--duration', default=10, type='int',
                      dest='duration',
                      help='how long each experiments must run (seconds)')
    return parser.parse_args()


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
    """
def prepare( generator, options, folderName, taskSet ):

    # minimal data structure required by generators.
    params = {'cpus': options.cpucount,
              'clusters': options.cpucount,
              'release_master': False,
              'durations': options.duration,
              'mutils': 0.0}

    finalPath = os.path.abspath(options.out) + "/" + folderName
    if os.path.isdir( finalPath ):
        sh.rmtree( finalPath )
    os.makedirs( finalPath )


    generator.out_dir = finalPath
    generator.tasks = taskSet

    generator._customize(taskSet, params)

    generator._write_schedule(dict(params.items() + [('task_set', taskSet)]))
    generator._write_params(params)

    return True


def main():
    opts, _ = parse_args()
    if opts.out == "" or opts.input == "":
        sys.stderr.write("Missing input or output folders.\n")
        return -1

    ts = parse_input( opts.input )

    # Folder names must be the same as config.AUTOMATE_SCHEDULER_LIST
    prepare(generators.PedfGenerator({}),
            opts, "PSN-EDF",
            deepcopy(ts))
    prepare(generators.GedfGenerator({}),
            opts, "GSN-EDF",
            deepcopy(ts))
    prepare(generators.RUNGenerator({}),
            opts, "RUN",
            deepcopy(ts))
    prepare(generators.QPSGenerator({}),
            opts, "QPS",
            deepcopy(ts))

    print "DONE PREPARING EXPERIMENTS."

if __name__ == '__main__':
    main()
