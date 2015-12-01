

DATAFILENAME= "/home/luca/Documents/Workspace/newscript/experiment-scripts/KAKA"

def findCPUs (parsedData):
    result = []
    for key, _ in parsedData['rows'][('RUN',)].iteritems():
        if (len(key)>12 and
            key[:12] == "f-preemp-cpu"):
            result.append(key[12:])
    return sorted(result, key=lambda x: int(x))

def findTaskId (parsedData, scheduler):
    result = []
    for key, _ in parsedData['rows'][('RUN',)].iteritems():
        if (len(key)>12 and
            key[:12] == "f-preemp-cpu"):
            result.append(key[12:])
    return sorted(result, key=lambda x: int(x))

def prepare_perCPU_data(parsedData, scheduler):
    perCPU = {}
    for e in parsedData[(scheduler,)]:
        perCPU['preemptions']['sum']
    return None

def prepare_system_data(parsedData):
    return None

def prepare_perTask_data(parsedData, scheduler):
    return None

f = open(DATAFILENAME, "r")
data = eval(f.read().strip())
cpus = findCPUs(data)
print cpus