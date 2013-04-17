import config.config as conf
import os
import re
import struct
import subprocess

from collections import defaultdict,namedtuple
from common import recordtype
from point import Measurement

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

# Map of event ids to corresponding class, binary format, and processing methods
RecordInfo = namedtuple('RecordInfo', ['clazz', 'fmt', 'method'])
record_map = [0]*10

# Common to all records
HEADER_FORMAT = '<bbhi'
HEADER_FIELDS = ['type', 'cpu', 'pid', 'job']
RECORD_SIZE   = 24

NSEC_PER_MSEC = 1000000

def register_record(name, id, method, fmt, fields):
    '''Create record description from @fmt and @fields and map to @id, using
    @method to process parsed record.'''
    # Format of binary data (see python struct documentation)
    rec_fmt = HEADER_FORMAT + fmt

    # Corresponding field data
    rec_fields = HEADER_FIELDS + fields
    if "when" not in rec_fields: # Force a "when" field for everything
        rec_fields += ["when"]

    # Create mutable class with the given fields
    field_class = recordtype(name, list(rec_fields))
    clazz = type(name, (field_class, object), {})

    record_map[id] = RecordInfo(clazz, rec_fmt, method)

def make_iterator(fname):
    '''Iterate over (parsed record, processing method) in a
    sched-trace file.'''
    if not os.path.getsize(fname):
        # Likely a release master CPU
        return

    f = open(fname, 'rb')
    max_type = len(record_map)

    while True:
        data = f.read(RECORD_SIZE)

        try:
            type_num = struct.unpack_from('b',data)[0]
        except struct.error:
            break

        rdata = record_map[type_num] if type_num <= max_type else 0
        if not rdata:
            continue

        try:
            values = struct.unpack_from(rdata.fmt, data)
        except struct.error:
            continue

        obj = rdata.clazz(*values)

        if obj.job != 1:
            yield (obj, rdata.method)
        else:
            # Results from the first job are nonsense
            pass

def read_data(task_dict, fnames):
    '''Read records from @fnames and store per-pid stats in @task_dict.'''
    buff = []

    def add_record(itera):
        # Ordered insertion into buff
        try:
            next_ret = itera.next()
        except StopIteration:
            return

        arecord, method = next_ret
        i = 0
        for (i, (brecord, m, t)) in enumerate(buff):
            if brecord.when > arecord.when:
                break
        buff.insert(i, (arecord, method, itera))

    for fname in fnames:
        itera = make_iterator(fname)
        add_record(itera)

    while buff:
        (record, method, itera) = buff.pop(0)

        add_record(itera)
        method(task_dict, record)

def process_completion(task_dict, record):
    task_dict[record.pid].misses.store_time(record)

def process_release(task_dict, record):
    data = task_dict[record.pid]
    data.jobs += 1
    if data.params:
        data.misses.start_time(record, record.when + data.params.period)

def process_param(task_dict, record):
    params = TaskParams(record.wcet, record.period, record.partition)
    task_dict[record.pid].params = params

def process_block(task_dict, record):
    task_dict[record.pid].blocks.start_time(record)

def process_resume(task_dict, record):
    task_dict[record.pid].blocks.store_time(record)

register_record('ResumeRecord', 9, process_resume, 'Q8x', ['when'])
register_record('BlockRecord', 8, process_block, 'Q8x', ['when'])
register_record('CompletionRecord', 7, process_completion, 'Q8x', ['when'])
register_record('ReleaseRecord', 3, process_release, 'QQ', ['when', 'release'])
register_record('ParamRecord', 2, process_param, 'IIIcc2x',
                          ['wcet','period','phase','partition', 'task_class'])

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
