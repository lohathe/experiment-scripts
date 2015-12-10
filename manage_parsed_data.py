#!/usr/bin/env python
from sys import stderr, stdout
from os import path, makedirs, remove
from shutil import rmtree
from subprocess import call
from plot.snippets import *
from optparse import OptionParser
import re

def parse_args():
    parser = OptionParser("usage: %prog [options]")

    parser.add_option('-o', '--out', dest='out',
                      help='root directory for data output',
                      default='')
    parser.add_option('-i', '--input', dest='input',
                      help='mapped file produced by parse_exps',
                      default='')
    parser.add_option('-s', '--system', dest='system',
                      help='file describing the task-set',
                      default='')
    parser.add_option('-c', '--cpucount', default=1, type='int',
                      dest='cpucount',
                      help='number cpu to use in the experiments')
    parser.add_option('-d', '--duration', default=1, type='int',
                      dest='duration',
                      help='how long each experiments must run (seconds)')
    return parser.parse_args()

def findSchedulers (parsedData):
    result = []
    for element in parsedData['rows']:
        result.append(element[0])
    return result

def findCPUs (parsedData, scheduler):
    result = []
    for key, _ in parsedData['rows'][(scheduler,)].iteritems():
        if (len(key)>12 and
            key[:24] == "filtered-preemptions-cpu"):
            result.append(key[24:])
    return sorted(result, key=lambda x: int(x))

def get_data(data, key1, key2="sum"):
    result = 0
    if key1 in data:
        result = data[key1][key2]
    return result

SCHOVH = 0
CXSOVH = 1
RELOVH = 2
PREOVH = 3
MIGOVH = 4
MISOVH = 5
IN = 0
OUT = 1
YAXIS = 2
DataUtil = {SCHOVH: {IN: "sum", OUT: "scheduling overhead", YAXIS: "ms"},
            CXSOVH: {IN: "cxs", OUT: "context-switch overhead", YAXIS: "ms"},
            RELOVH: {IN: "release-latency", OUT: "max release latency", YAXIS: "ms"},
            PREOVH: {IN: "preemptions", OUT: "preemptions count", YAXIS: "count"},
            MIGOVH: {IN: "migrations", OUT: "migrations count", YAXIS: "count"},
            MISOVH: {IN: "miss-ratio", OUT: "deadline misses", YAXIS: "percentage"}}

def prepare_perCPU_data(parsedData, scheduler, cpuCount):
    perCPU = {SCHOVH: [],
              CXSOVH: [],
              RELOVH: [],
              PREOVH: []}
    cpus = findCPUs(parsedData, scheduler)
    data = parsedData['rows'][(scheduler,)]
    prefix = ""
    if scheduler == "QPS":
        prefix = "filtered-"
    else :
        prefix = ""
    for cpu in cpus:
        target = "-cpu{}".format(cpu)
        perCPU[SCHOVH].append( get_data(data, DataUtil[SCHOVH][IN]+target, "sum"))
        perCPU[CXSOVH].append( get_data(data, DataUtil[CXSOVH][IN]+target, "sum"))
        perCPU[RELOVH].append( get_data(data, DataUtil[RELOVH][IN]+target, "max"))
        perCPU[PREOVH].append( get_data(data, prefix+DataUtil[PREOVH][IN]+target, "sum"))

    # in case some CPUs were not used in the experiments (because of slack)
    for _ in range(0, cpuCount - len(cpus)):
        perCPU[SCHOVH].append(0)
        perCPU[CXSOVH].append(0)
        perCPU[RELOVH].append(0)
        perCPU[PREOVH].append(0)

    return perCPU

def plot_perCPU_data(opts, parsedData):
    #schedulers = AUTOMATE_SCHEDULER_LIST
    schedulers = findSchedulers(parsedData)
    cpuCount = opts.cpucount

    easyData = {}
    outputDir = path.abspath(opts.out) + "/charts"
    for scheduler in schedulers:
        easyData[scheduler] = prepare_perCPU_data(parsedData, scheduler, cpuCount)

    # For each overhead:
    for overhead in [SCHOVH, CXSOVH, RELOVH, PREOVH]:
        ymax = 0

        # (1) print the histogram data file used by gnuplot
        datafile = outputDir + "/temp{}".format(overhead)
        try :
            f = open(datafile, "w")
            for scheduler in schedulers:
                f.write(scheduler+" " +
                        " ".join(map(str,easyData[scheduler][overhead]))+"\n")
                ymax = max(easyData[scheduler][overhead]+[ymax])
        except :
            stderr.write("Problem (1) for perCPU overhead {}\n".format(overhead))
        finally:
            f.close()

        # (2) prepare the gnuplot script
        script = ""
        script += plotOutputPrologue.format(terminal = "png truecolor butt",
                    fname = outputDir+"/Chart{}perCPU.png".format(overhead))
        script += plotPalette
        script += plotFrameVertical
        script += plotWordsVertical.format(position="right top",
                    orientation="horizontal",
                    title=DataUtil[overhead][OUT]+" (per CPU)",
                    xlabel="scheduler",
                    ylabel=DataUtil[overhead][YAXIS],
                    ymax=1.1*ymax)
        script += plotClusteredHistogram
        script += "plot '{infile}' u 2:xtic(1) ti 'CPU_i, i=(0 ... {n})' ls 107".format(
            infile=datafile, n=cpuCount-1)
        for i in range (1, cpuCount):
            script += ", '{infile}' u {cpu}:xtic(1) ls 107 noti ".format(
                infile=datafile, cpu=i+2)
        script += "\n"+plotOutputEpilogue

        # (3) print the gnuplot script
        try :
            f = open(datafile+".script", "w")
            f.write(script)
        except :
            stderr.write("Problem (2) for perCPU overhead {}\n".format(overhead))
        finally:
            f.close()

        # (4) execute gnuplot on the script and remove temp files
        scriptFile = datafile+".script"
        call(["gnuplot", scriptFile])
        remove(datafile)
        remove(datafile+".script")


def prepare_system_data(parsedData, schedulers):
    system = {SCHOVH: [],
              CXSOVH: [],
              RELOVH: [],
              PREOVH: [],
              MIGOVH: [],
              MISOVH: []}

    for scheduler in schedulers:
        data = parsedData['rows'][(scheduler,)]
        prefix = ""
        if scheduler == "QPS":
            prefix = "filtered-"
        else :
            prefix = ""
        system[SCHOVH].append( get_data(data, DataUtil[SCHOVH][IN], "sum"))
        system[CXSOVH].append( get_data(data, DataUtil[CXSOVH][IN], "sum"))
        system[RELOVH].append( get_data(data, DataUtil[RELOVH][IN], "max"))
        system[PREOVH].append( get_data(data, prefix+DataUtil[PREOVH][IN], "sum"))
        system[MIGOVH].append( get_data(data, DataUtil[MIGOVH][IN], "sum"))
        system[MISOVH].append( get_data(data, DataUtil[MISOVH][IN], "sum"))

    return system

def plot_system_data(opts, parsedData):
    #schedulers = AUTOMATE_SCHEDULER_LIST
    schedulers = findSchedulers(parsedData)

    easyData = prepare_system_data(parsedData, schedulers)
    outputDir = path.abspath(opts.out) + "/charts"

    # For each overhead:
    for overhead in [SCHOVH, CXSOVH, RELOVH, PREOVH, MIGOVH, MISOVH]:
        # (1) print the histogram data file used by gnuplot
        datafile = outputDir + "/temp{}".format(overhead)
        try :
            f = open(datafile, "w")
            f.write("OVH " + " ".join(schedulers) + "\n")
            f.write("{} ".format(overhead) +
                    " ".join(map(str, easyData[overhead])) + "\n" )
        except :
            stderr.write("Problem (1) for system overhead {}\n".format(overhead))
        finally:
            f.close()

        # (2) prepare the gnuplot script
        suffix = " (cumulative)"
        if overhead == RELOVH:
            suffix = ""
        script = ""
        script += plotOutputPrologue.format(terminal = "png truecolor butt",
                      fname = outputDir+"/Chart{}system.png".format(overhead))
        script += plotPalette
        script += plotFrameVertical
        script += plotWordsVertical.format(position="right top",
                    orientation="horizontal",
                    title=DataUtil[overhead][OUT] + suffix,
                    xlabel="",
                    ylabel=DataUtil[overhead][YAXIS],
                    ymax=max([1.1, 1.1*max(easyData[overhead])]))
        script += plotClusteredHistogram
        script += "unset xtics\n"
        script += "plot"
        for scheduler in schedulers:
            script += " '{infile}' u {pos}:xtic(1) ti col ls {style}".format(
                infile=datafile,
                pos=2+schedulers.index(scheduler),
                style=102+schedulers.index(scheduler))
            if scheduler != schedulers[-1]:
                script+=","
        script += "\n"+plotOutputEpilogue

        # (3) print the gnuplot script
        try :
            f = open(datafile+".script", "w")
            f.write(script)
        except :
            stderr.write("Problem (2) for system overhead {}\n".format(overhead))
        finally:
            f.close()

        # (4) execute gnuplot on the script and remove temp files
        call(["gnuplot", datafile+".script"])
        remove(datafile)
        remove(datafile+".script")



def read_task_set(opts):
    result = {}
    with open(opts.system, 'r') as f:
        for line in f:
            splitted = line.strip().split(" ")
            result[splitted[0]] = [splitted[1], splitted[2]]
    return result

def prepare_perTask_data(parsedData, parsedPid):
    result = {}
    for scheduler in parsedData['rows'].keys():
        sched =  scheduler[0]
        pid = str(parsedPid[sched])
        responseData = parsedData['rows'][scheduler]#['response'+pid]
        jitterData = parsedData['rows'][scheduler]#['jitter'+pid]
        result[sched] = [get_data(responseData, 'response'+pid, 'avg'),
                         get_data(responseData, 'response'+pid, 'min'),
                         get_data(responseData, 'response'+pid,'max'),
                         get_data(jitterData, 'jitter'+pid,'avg'),
                         get_data(jitterData, 'jitter'+pid,'min'),
                         get_data(jitterData, 'jitter'+pid,'max')]
    return result

def plot_perTask_data(opts, parsedData, parsedPid, taskSet):
    #schedulers = ["RUN", "RUN2"]# TODO: get list from config file!

    easyData = {}
    outputDir = path.abspath(opts.out) + "/charts"
    # regroup parsed data into an easier structure for this purpose
    for tid in parsedPid.keys():
        easyData[tid] = prepare_perTask_data(parsedData, parsedPid[tid])

    # For each task
    for tid in easyData.keys():
        # (1) print the histogram data file used by gnuplot
        datafile = outputDir + "/temp{}".format(tid)
        datatask = taskSet[tid]
        ymax = float(datatask[1])*1.05
        try :
            f = open(datafile, "w")
            for scheduler in easyData[tid].keys():
                f.write(scheduler+" " +
                        " ".join(map(str, easyData[tid][scheduler]))+"\n")
                if max(easyData[tid][scheduler]) > ymax:
                    ymax = max(easyData[tid][scheduler])
        except :
            stderr.write("Problem (1) for perTask info: {}\n".format(tid))
        finally:
            f.close()

        # (2) prepare the gnuplot script
        script = ""
        script += plotOutputPrologue.format(fname = datafile+".png",
                      terminal = "png truecolor butt size 500,1300")
        script += plotPalette
        script += plotFrameHorizontal.format(ymax = ymax,
                                             ylabel = str(tid))
        # Arrow length is good to be 1/15th of the period????
        script += plotTaskBackground.format(WCET=datatask[0],
                                            Period=datatask[1],
                                            ArrowLength=int(datatask[1])/15,
                                            shift=2 )
        script += plotErrorbarHistogram
        script += """plot \
            '{infile}' u 2:3:4:xtic(1) axes x1y2 ls 104 ti 'response', \
            '{infile}' u 5:6:7:xtic(1) axes x1y2 ls 105 ti 'jitter'""".format(
            infile=datafile)

        # (3) print the gnuplot script
        try :
            f = open(datafile+".script", "w")
            f.write(script)
        except :
            stderr.write("Problem (2) for perTask info: {}\n".format(tid))
        finally:
            f.close()

        # (4) execute gnuplot on the script, rotate image and remove temp files
        call(["gnuplot", datafile+".script"])
        call(["convert", datafile+".png", "-rotate", "90",
              outputDir+"/Task-{}.png".format(tid) ])
        remove(datafile)
        remove(datafile+".png")
        remove(datafile+".script")

    return None

def create_html(opts, taskSet):
    table=""
    tasks=""
    chartsDir = path.abspath(opts.out)+"/charts"
    htmlFile = path.abspath(opts.out) + "/automate.html"
    naturalsort = lambda s: [int(t) if t.isdigit() else t.lower()
                             for t in re.split('(\d+)', s)]
    for tid in sorted(taskSet.keys(), key=naturalsort):
        table+="<tr><td>{name}</td><td>{wcet}</td><td>{period}</td></tr>\n".format(
            name=tid, wcet=taskSet[tid][0], period=taskSet[tid][1])
        tasks+=("<div class='task'><img class='chart' "+
                "src='{folder}/Task-{name}.png' /></div>\n".format(
                    folder=chartsDir, name=tid))
    with open(htmlFile, "w") as f:
        f.write(html.format(cpuCount=opts.cpucount,
                            taskCount=len(taskSet),
                            duration=opts.duration,
                            plotFolder=chartsDir,
                            taskTable=table,
                            taskStats=tasks))
    return None

def main():
    opts, _ = parse_args()
    if opts.out == "" or opts.input == "" or opts.system == "":
        stderr.write("Missing some options.\n")
        return -1

    outputDir = path.abspath(opts.out)
    # Remove old data if any and create output dir
    if path.exists(outputDir):
        rmtree(outputDir)
    makedirs(outputDir)
    makedirs(outputDir+"/charts")

    try:
        fData = open(opts.input, 'r')
        parsedData = eval(fData.read().strip())
        fData.close()

        fPid = open(opts.input+".pid", 'r')
        parsedPid = eval(fPid.read().strip())
        fPid.close()

        taskSet = read_task_set(opts)
    except :
        stderr.write("Something wrong while opening input files.\n")

    stdout.write("Plotting perCPU charts...\n")
    plot_perCPU_data(opts, parsedData)
    stdout.write("Plotting system-wide charts...\n")
    plot_system_data(opts, parsedData)
    stdout.write("Plotting perTask charts...\n")
    plot_perTask_data(opts, parsedData, parsedPid, taskSet)

    stdout.write("Creating HTML file...\n")
    create_html(opts, taskSet)
    remove("delete.me")
    stdout.write("AUTOMATE has finished!\n")
    return None

if __name__ == '__main__':
    main()
