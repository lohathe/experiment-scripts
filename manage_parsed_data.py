#from config.config import FILES, MAX_CPUS
from sys import stderr
from os import path, mkdir, remove
from shutil import rmtree
#from collections import defaultdict
from pprint import pprint
from subprocess import call
#from prepare_exp import OUT_DIR

FILES = {'taskid_vs_pid': 'taskPID.log'}
MAX_CPUS = 8

OUT_DIR = "/home/luca/Documents/Workspace/newscript/experiment-scripts/exps/temp"
INPUT_DIR = "/home/luca/Documents/Workspace/newscript/experiment-scripts/KOKO"
OUTPUR_DIR = "/home/luca/Documents/Workspace/newscript/experiment-scripts/myplots"
DATAFILENAME= "/home/luca/Documents/Workspace/newscript/experiment-scripts/KAKA"
TASKSET_FILE = "/home/luca/Documents/Workspace/newscript/experiment-scripts/exps/temp/input3"

plotOutputPrologue="""
reset
set terminal {terminal}
set output "{fname}"
"""
plotOutputEpilogue="""
set output "delete.me"
"""

plotPalette="""
# SETTING STYLES
set style line 100 lt 3 lc rgb '#000000' lw 1 #black
set style line 101 lt 3 lc rgb '#902020' lw 2 #red
set style line 102 lt 3 lc rgb '#E07000' lw 2 #orange
set style line 103 lt 3 lc rgb '#F0A010' lw 2 #yellow
set style line 104 lt 3 lc rgb '#209020' lw 2 #green
set style line 105 lt 3 lc rgb '#90C0C0' lw 2 #water
set style line 106 lt 3 lc rgb '#203090' lw 2 #blue
set style line 107 lt 3 lc rgb '#808080' lw 2 #gray
set style line 109 lt 3 lc rgb '#702020' lw 3 #darkRed
set style line 110 lt 3 lc rgb '#808010' lw 3 #darkYellow
set style fill solid .90 border lt -1
set style rect fc lt -1 fs solid 0.15 noborder
set style arrow 1 head nofilled size screen 0.03,15 ls 109
set style arrow 2 head nofilled size screen 0.03,15 ls 110
set boxwidth 0.8 absolute
set bar .5
"""
plotFrameVertical="""
# SETTING VERTICAL FRAME
set border 3 front ls 107
set tics nomirror out scale 0.75
set format '%g'
set grid noxtics ytics
"""
plotFrameHorizontal="""
# SETTING HORIZONTAL FRAME
set border 9 front ls 107
set format '%g'
set grid noxtics noytics y2tics
unset ytics
unset y2tics
set xtic rotate right nomirror out scale .75
set xrange [-2:]
set y2tics rotate by 90 nomirror out scale .75
set y2range [0:]
set size 1, 1
set key outside top horizontal Right noreverse noenhanced autotitle nobox
set ylabel "{ylabel}"
"""
plotTaskBackground="""
# Task WCET + Period
set obj rect from graph 1, second 0 to graph 0, second {WCET} behind fc rgb'#902020' fs solid .4
set obj rect from graph 1, second {WCET} to graph 0, second {period} behind fc rgb'#F0A010' fs solid .4
set arrow 1 from -1, second ({ArrowLength}) to -1, second 0 as 1
set arrow 2 from -1, second ({WCET}-{ArrowLength}) to -1, second {WCET} as 1
set arrow 3 from -1, second ({Period}-{ArrowLength}) to -1, second {Period} as 2
set label "WCET" at -1, second ({WCET}-{ArrowLength}-{shift}) right rotate by 90 tc rgb'#702020'
set label "Period" at -1, second ({Period}-{ArrowLength}-{shift}) right rotate by 90 tc rgb'#809010'
"""
plotWordsVertical ="""
# SETTING HUMAN-READABLE INFO
set key inside {position} {orientation} Right noreverse noenhanced autotitle nobox
set title "{title}"
set xlabel "{xlabel}"
set ylabel "{ylabel}"
set yrange [-1:]
"""
plotClusteredHistogram="""
# PLOT TYPE
set style histogram clustered gap 3 title textcolor lt -1
set style data histograms
"""
plotErrorbarHistogram="""
# PLOT TYPE
set style histogram errorbars gap 3 lw 2
set style data histograms
"""

def findCPUs (parsedData, scheduler):
    result = []
    for key, _ in parsedData['rows'][(scheduler,)].iteritems():
        if (len(key)>12 and
            key[:24] == "filtered-preemptions-cpu"):
            result.append(key[24:])
    return sorted(result, key=lambda x: int(x))

def findTaskPID (parsedData, scheduler):
    result = []
    hasID = False
    filepath = INPUT_DIR+"/"+scheduler+"/"+FILES['taskid_vs_pid']
    if path.exists(filepath) and path.isfile(filepath):
        with open(filepath) as f:
            hasID = True
            for line in f:
                temp = line.split(":")
                result.append( (temp[0].strip(),
                                temp[1].strip()) ) # (PID, taskID)
    else :
        hasID = False
        for key, _ in parsedData['rows'][(scheduler,)].iteritems():
            if (len(key)>6 and
                key[:6] == "jitter"):
                result.append( (key[6:], "noID") ) # (PID, "noID")
    return hasID, result

def get_data(data, key1, key2="sum"):
    result = 0
    if key1 in data:
        result = data[key1][key2]
    return result

SCHOVH = 0
CXSOVH = 1
RELOVH = 2
PREOVH = 3
IN = 0
OUT = 1
YAXIS = 3
DataUtil = {SCHOVH: {IN: "sum", OUT: "scheduling overhead", YAXIS: "ms"},
            CXSOVH: {IN: "cxs", OUT: "context-switch overhead", YAXIS: "ms"},
            RELOVH: {IN: "release-latency", OUT: "max release latency", YAXIS: "ms"},
            PREOVH: {IN: "preemptions", OUT: "preemptions count", YAXIS: "count"}}

def prepare_perCPU_data(parsedData, scheduler):
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

    return perCPU

def plot_perCPU_data(parsedData):
    schedulers = ["RUN", "RUN2"] # TODO: get list from config file!

    easyData = {}
    for scheduler in schedulers:
        easyData[scheduler] = prepare_perCPU_data(parsedData, scheduler)

    # For each overhead:
    for overhead in [SCHOVH, CXSOVH, RELOVH, PREOVH]:
        # (1) print the histogram data file used by gnuplot
        datafile = OUTPUR_DIR + "/temp{}".format(overhead)
        try :
            f = open(datafile, "w")
            for scheduler in schedulers:
                k1 = scheduler + " "
                k2 = " ".join(map(str, easyData[scheduler][overhead]))
                f.write(scheduler+" "+" ".join(map(str, easyData[scheduler][overhead]))+"\n")
        except :
            stderr("Some problem (1) for perCPU overhead {}".format(overhead))
        finally:
            f.close()

        # (2) prepare the gnuplot script
        script = ""
        script += plotOutputPrologue.format(terminal = "pdf colour enhanced",
                                            fname = OUTPUR_DIR+"/Chart{}perCPU.pdf".format(overhead))
        script += plotPalette
        script += plotFrameVertical
        script += plotWordsVertical.format(position="right top",
                                           orientation="horizontal",
                                           title=DataUtil[overhead][OUT],
                                           xlabel="scheduler",
                                           ylabel=DataUtil[overhead][YAXIS])
        script += plotClusteredHistogram
        script += "plot '{infile}' u 2:xtic(1) ti 'CPU_i, i=(0 ... {n})' ls 107".format(
            infile=datafile, n=MAX_CPUS-1)
        for i in range (1, MAX_CPUS):
            script += ", '{infile}' u {cpu}:xtic(1) ls 107 noti ".format(infile=datafile, cpu=i+2)
        script += "\n"+plotOutputEpilogue

        # (3) print the gnuplot script
        try :
            f = open(datafile+".script", "w")
            f.write(script)
        except :
            stderr("Some problem (2) for perCPU overhead {}".format(overhead))
        finally:
            f.close()

        # (4) execute gnuplot on the script and remove temp files
        call(["gnuplot", datafile+".script"])
        remove(datafile)
        remove(datafile+".script")


def prepare_system_data(parsedData):
    return None


def read_task_set():
    result = {}
    with open(TASKSET_FILE, 'r') as f:
        for line in f:
            splitted = line.trim().split(" ")
            result[splitted[0]] = [splitted[1], splitted[2]]
    return result

def prepare_perTask_data(parsedData, tid, pids):
    result = {}
    for scheduler in parsedData['rows'].keys():
        sched =  scheduler[0]
        pid = str(pids[tid][sched])
        responseData = parsedData['rows'][scheduler]['response'+pid]
        jitterData = parsedData['rows'][scheduler]['jitter'+pid]
        result[sched] = [responseData['avg'],
                         responseData['min'],
                         responseData['max'],
                         jitterData['avg'],
                         jitterData['min'],
                         jitterData['max']]
    return result

def plot_perTask_data(data, pid):
    #schedulers = ["RUN", "RUN2"]# TODO: get list from config file!

    easyData = {}
    # regroup parsed data into an easier structure for this purpose
    for tid in pid.keys():
        easyData[tid] = prepare_perTask_data(data, tid, pid[tid])
    # read taskset file to determine WCET and period of each task
    taskSet = read_task_set()

    # For each task
    for tid in easyData.keys():
        # (1) print the histogram data file used by gnuplot
        datafile = OUTPUR_DIR + "/temp{}".format(tid)
        outfile = OUTPUR_DIR+"/temp{}.png".format(tid)
        datatask = taskSet[tid]
        try :
            f = open(datafile, "w")
            for scheduler in easyData[tid].keys():
                k1 = scheduler + " "
                k2 = " ".join(map(str, easyData[tid][scheduler]))
                f.write(scheduler+" "+" ".join(map(str, easyData[tid][scheduler]))+"\n")
        except :
            stderr("Some problem (1) for perTask info: {}".format(tid))
        finally:
            f.close()

        # (2) prepare the gnuplot script
        script = ""
        #script += plotOutputPrologue.format(terminal = "pdf colour enhanced size 5cm, 15cm",
        #                                    fname = OUTPUR_DIR+"/ChartTask-{}.pdf".format(tid))
        script += plotOutputPrologue.format(terminal = "png truecolor butt size 800,1800",
                                            fname = outfile)
        script += plotPalette
        script += plotFrameHorizontal.format(ylable = str(tid))
        script += plotTaskBackground.format(WCET=datatask[0],
                                            Period=datatask[1],
                                            ArrowLength=datatask[1]/12, #arrow is one 12th of the period
                                            shift=5 )
        script += plotErrorbarHistogram
        script += "plot "+\
            "'{infile}' u 2:3:4:xtic(1) axes x1y2 ls 104 ti 'response',"+\
            "'{infile}' u 5:6:7:xtic(1) axes x1y2 ls 105 ti 'jitter'".format(
            infile=datafile)

        # (3) print the gnuplot script
        try :
            f = open(datafile+".script", "w")
            f.write(script)
        except :
            stderr("Some problem (2) for perTask info: {}".format(tid))
        finally:
            f.close()

        # (4) execute gnuplot on the script, rotate image and remove temp files
        call(["gnuplot", datafile+".script"])
        call(["convert", outfile, "-rotate", "90", OUTPUR_DIR+"/Task-{}.png".format(tid) ])
        remove(datafile)
        remove(outfile)
        remove(datafile+".script")

    return None

# Remove old data if any and create output dir
if path.exists(OUTPUR_DIR):
    rmtree(OUTPUR_DIR)
mkdir(OUTPUR_DIR)

f = open(DATAFILENAME, "r")
data = eval(f.read().strip())
f2 = open(DATAFILENAME+".pid", "r")
data2 = eval(f2.read().strip())
pprint(prepare_perCPU_data(data, "RUN"))
plot_perCPU_data(data)