import config.config as conf
import os
import re
import struct
import subprocess

from collections import defaultdict,namedtuple
from common import recordtype
from point import Measurement
from ctypes import *

class TimeTracker:
    '''Store stats for durations of time demarcated by sched_trace records.'''
    def __init__(self):
        self.begin = self.avg = self.max = self.num = self.job = 0

    def store_time(self, record):
        '''End duration of time.'''
        dur = record.when - self.begin

        if self.job == record.job and dur > 0:
            self.max  = max(self.max, dur)
            self.avg *= float(self.num / (self.num + 1))
            self.num += 1
            self.avg += dur / float(self.num)

            self.begin = 0
            self.job   = 0

    def start_time(self, record, time = None):
        '''Start duration of time.'''
        if not time:
            self.begin = record.when
        else:
            self.begin = time
        self.job = record.job

# Data stored for each task
TaskParams = namedtuple('TaskParams',  ['wcet', 'period', 'cpu'])
TaskData   = recordtype('TaskData',    ['params', 'jobs', 'blocks', 'misses'])

# Map of event ids to corresponding class and format
record_map = {}

RECORD_SIZE   = 24
NSEC_PER_MSEC = 1000000

def register_record(id, clazz):
    fields = clazz.FIELDS

    fsize = lambda fields : sum([sizeof(list(f)[1]) for f in fields])
    diff  = RECORD_SIZE - fsize(SchedRecord.FIELDS) - fsize(fields)

    # Create extra padding fields to make record the proper size
    # Creating one big field of c_uint64 and giving it a size of 8*diff
    # _shoud_ work, but doesn't. This is an uglier way of accomplishing
    # the same goal
    for d in range(diff):
        fields += [("extra%d" % d, c_char)]

    # Create structure with fields and methods of clazz
    clazz2 = type("Dummy%d" % id, (LittleEndianStructure,clazz),
                  {'_fields_': SchedRecord.FIELDS + fields,
                   '_pack_'  : 1})
    record_map[id] = clazz2

def make_iterator(fname):
    '''Iterate over (parsed record, processing method) in a
    sched-trace file.'''
    if not os.path.getsize(fname):
        # Likely a release master CPU
        return

    f = open(fname, 'rb')

    while True:
        data = f.read(RECORD_SIZE)

        try:
            type_num = struct.unpack_from('b',data)[0]
        except struct.error:
            break

        if type_num not in record_map:
            continue

        clazz = record_map[type_num]
        obj = clazz()
        obj.fill(data)

        if obj.job != 1:
            yield obj
        else:
            # Results from the first job are nonsense
            pass

def read_data(task_dict, fnames):
    '''Read records from @fnames and store per-pid stats in @task_dict.'''
    buff = []

    def get_time(record):
        return record.when if hasattr(record, 'when') else 0

    def add_record(itera):
        # Ordered insertion into buff
        try:
            arecord = itera.next()
        except StopIteration:
            return

        i = 0
        for (i, (brecord, _)) in enumerate(buff):
            if get_time(brecord) > get_time(arecord):
                break
        buff.insert(i, (arecord, itera))

    for fname in fnames:
        itera = make_iterator(fname)
        add_record(itera)

    while buff:
        record, itera = buff.pop(0)

        add_record(itera)
        record.process(task_dict)

class SchedRecord(object):
    # Subclasses will have their FIELDs merged into this one
    FIELDS = [('type', c_uint8),  ('cpu', c_uint8),
              ('pid',  c_uint16), ('job', c_uint32)]

    def fill(self, data):
        memmove(addressof(self), data, RECORD_SIZE)

    def process(self, task_dict):
        raise NotImplementedError()

class ParamRecord(SchedRecord):
    FIELDS = [('wcet', c_uint32),  ('period', c_uint32),
              ('phase', c_uint32), ('partition', c_uint8)]

    def process(self, task_dict):
        params = TaskParams(self.wcet, self.period, self.partition)
        task_dict[self.pid].params = params

class ReleaseRecord(SchedRecord):
    FIELDS = [('when', c_uint64), ('release', c_uint64)]

    def process(self, task_dict):
        data = task_dict[self.pid]
        data.jobs += 1
        if data.params:
            data.misses.start_time(self, self.when + data.params.period)

class CompletionRecord(SchedRecord):
    FIELDS = [('when', c_uint64)]

    def process(self, task_dict):
        task_dict[self.pid].misses.store_time(self)

class BlockRecord(SchedRecord):
    FIELDS = [('when', c_uint64)]

    def process(self, task_dict):
        task_dict[self.pid].blocks.start_time(self)

class ResumeRecord(SchedRecord):
    FIELDS = [('when', c_uint64)]

    def process(self, task_dict):
        task_dict[self.pid].blocks.store_time(self)

# Map records to sched_trace ids (see include/litmus/sched_trace.h
register_record(2, ParamRecord)
register_record(3, ReleaseRecord)
register_record(7, CompletionRecord)
register_record(8, BlockRecord)
register_record(9, ResumeRecord)

def create_task_dict(data_dir, work_dir = None):
    '''Parse sched trace files'''
    bin_files   = conf.FILES['sched_data'].format(".*")
    output_file = "%s/out-st" % work_dir

    task_dict = defaultdict(lambda :
                            TaskData(None, 1, TimeTracker(), TimeTracker()))

    bin_names = [f for f in os.listdir(data_dir) if re.match(bin_files, f)]
    if not len(bin_names):
        return task_dict

    # Save an in-english version of the data for debugging
    # This is optional and will only be done if 'st_show' is in PATH
    if conf.BINS['st_show']:
        cmd_arr = [conf.BINS['st_show']]
        cmd_arr.extend(bin_names)
        with open(output_file, "w") as f:
            subprocess.call(cmd_arr, cwd=data_dir, stdout=f)

    # Gather per-task values
    bin_paths = ["%s/%s" % (data_dir,f) for f in bin_names]
    read_data(task_dict, bin_paths)

    return task_dict

def extract_sched_data(result, data_dir, work_dir):
    task_dict = create_task_dict(data_dir, work_dir)
    stat_data = defaultdict(list)

    # Group per-task values
    for tdata in task_dict.itervalues():
        if not tdata.params:
            # Currently unknown where these invalid tasks come from...
            continue

        miss_ratio = float(tdata.misses.num) / tdata.jobs
        stat_data["miss-ratio"].append(float(tdata.misses.num) / tdata.jobs)

        stat_data["max-tard"  ].append(tdata.misses.max / tdata.params.wcet)
        # Scale average down to account for jobs with 0 tardiness
        avg_tard = tdata.misses.avg * miss_ratio
        stat_data["avg-tard"  ].append(avg_tard / tdata.params.wcet)

        stat_data["avg-block" ].append(tdata.blocks.avg / NSEC_PER_MSEC)
        stat_data["max-block" ].append(tdata.blocks.max / NSEC_PER_MSEC)

    # Summarize value groups
    for name, data in stat_data.iteritems():
        if not data or not sum(data):
            continue
        result[name] = Measurement(str(name)).from_array(data)
