import config.config as conf
import os
import re
import struct
import subprocess
import numpy as np

from collections import defaultdict,namedtuple
from common import recordtype,log_once
from point import Measurement
from ctypes import *
from heapq import *
from config.config import PREEMPTION_THRESHOLD

class JobInfo:
    def __init__(self):
        self.releasetime = 0
        self.deadlinetime = 0
        self.completiontime = 0
        self.starttime = 0

class EventTraker:
    def __init__(self, sync_release_time = 0, systeminfo = None):
        self.sync_release_time = sync_release_time
        self.filtered_preemptions= {}
        self.preemptions = {}
        self.migrations = {}
        self.switch_buffer = []
        self.delay_buffer_size = 1
        self.system = systeminfo

    def add_event(self, record, time):
        if len(self.switch_buffer) == self.delay_buffer_size:
            to_queue = self.switch_buffer.pop(0)
            if to_queue[0].job == record.job:
                if to_queue[0].type == 6 and record.type == 5:
                    self.preemptions[to_queue[0].job] += 1
                    # consider preemption where the switch_to event happens!
                    self.system[record.cpu]["preemptions"] += 1
                    if time - to_queue[1] > PREEMPTION_THRESHOLD:
                        self.filtered_preemptions[to_queue[0].job] += 1
                        self.system[record.cpu]["filtered_preemptions"] += 1
                    if to_queue[0].cpu != record.cpu:
                        self.migrations[to_queue[0].job] += 1

        if not record.job in self.preemptions.keys():
            self.preemptions[record.job] = 0
            self.filtered_preemptions[record.job] = 0
            self.migrations[record.job] = 0
        self.switch_buffer.append((record, time))

    def get_preemptions(self):
        sum = 0
        for job in self.preemptions.keys():
            sum += self.preemptions[job]
        return sum

    def get_filtered_preemptions(self):
        sum = 0
        for job in self.filtered_preemptions.keys():
            sum += self.filtered_preemptions[job]
        return sum

    def get_migrations(self):
        sum = 0
        for job in self.migrations.keys():
            sum += self.migrations[job]
        return sum

    def get_jobs(self):
        return len(self.preemptions.keys())

class TimeTracker:
    '''Store stats for durations of time demarcated by sched_trace records.'''
    def __init__(self, is_valid_duration = lambda x: x > 0,
                 capper = lambda x: x, delay_buffer_size = 1,
                 max_pending = -1, sync_release_time = 0):
        self.validator = is_valid_duration
        self.capper = capper
        self.avg = self.max = self.num = 0
        self.all_measurements = []
        self.all_measurements_arr = None

        self.matches = 0

        self.max_pending = max_pending
        self.discarded = 0

        self.delay_buffer_size = delay_buffer_size
        self.start_delay_buffer = []
        self.end_delay_buffer = []
        self.start_records = {}
        self.end_records = {}
        self.sync_release_time = sync_release_time

    def disjoints(self):
        unmatched = len(self.start_records) + len(self.end_records)
        return self.discarded + unmatched

    def stdev(self):
        if self.all_measurements_arr is None:
            self.all_measurements_arr = np.asarray(self.all_measurements)
            self.all_measurements_arr.sort()
        return np.std(self.all_measurements_arr)

    def percentile(self, which):
        raise Exception("Percentile unimplemented")

    def process_completed(self):
        completed = self.start_records.viewkeys() & self.end_records.viewkeys()
        self.matches += len(completed)
        for c in completed:
            _, stime = self.start_records[c]
            _, etime = self.end_records[c]
            del self.start_records[c]
            del self.end_records[c]

            dur = self.capper(etime - stime)
            if self.validator(dur):
                self.max = max(self.max, dur)
                old_avg = self.avg * self.num
                self.num += 1
                self.avg = (old_avg + dur) / float(self.num)
                self.all_measurements.append(dur)

        # Give up on some jobs if they've been hanging around too long.
        # While not strictly needed, it helps improve performance and
        # it is unlikey to cause too much trouble.
        if(self.max_pending >= 0 and len(self.start_records) > self.max_pending):
            to_discard = len(self.start_records) - self.max_pending
            for _ in range(to_discard):
                # pop off the oldest jobs
                del self.start_records[self.start_records.iterkeys().next()]
            self.discarded += to_discard
        if(self.max_pending >= 0 and len(self.end_records) > self.max_pending):
            to_discard = len(self.end_records) - self.max_pending
            for _ in range(to_discard):
                # pop off the oldest jobs
                del self.end_records[self.end_records.iterkeys().next()]
            self.discarded += to_discard

    def end_time(self, record, time):
        '''End duration of time.'''
        if len(self.end_delay_buffer) == self.delay_buffer_size:
            to_queue = self.end_delay_buffer.pop(0)
            self.end_records[to_queue[0].job] = to_queue
        self.end_delay_buffer.append((record, time))
        self.process_completed()

    def start_time(self, record, time):
        '''Start duration of time.'''
        if len(self.start_delay_buffer) == self.delay_buffer_size:
            to_queue = self.start_delay_buffer.pop(0)
            self.start_records[to_queue[0].job] = to_queue
        self.start_delay_buffer.append((record, time))
        self.process_completed()

# Data stored for each task
TaskParams = namedtuple('TaskParams',  ['wcet', 'period', 'cpu'])
TaskData   = recordtype('TaskData',    ['params', 'jobs', 'blocks', 'misses',
                                        'preemptions', 'responsetime', 'system'])

# Map of event ids to corresponding class and format
record_map = {}

RECORD_SIZE   = 24
NSEC_PER_MSEC = 1000000

def bits_to_bytes(bits):
    '''Includes padding'''
    return bits / 8 + (1 if bits%8 else 0)

def field_bytes(fields):
    fbytes = 0
    fbits  = 0
    for f in fields:
        flist = list(f)

        if len(flist) > 2:
            # Specified a bitfield
            fbits += flist[2]
        else:
            # Only specified a type, use types size
            fbytes += sizeof(list(f)[1])

            # Bitfields followed by a byte will cause any incomplete
            # bytes to be turned into full bytes
            fbytes += bits_to_bytes(fbits)
            fbits   = 0

    fbytes += bits_to_bytes(fbits)
    return fbytes + fbits

def register_record(id, clazz):
    fields = clazz.FIELDS
    diff = RECORD_SIZE - field_bytes(SchedRecord.FIELDS) - field_bytes(fields)

    # Create extra padding fields to make record the proper size
    # Creating one big field of c_uint64 and giving it a size of 8*diff
    # _should_ work, but doesn't. This is an uglier way of accomplishing
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

    # A time-stamp ordered heap
    q = []

    # Number of trace records to q from each stream/file. A heap
    # of this size is maintained in order to deal with events that
    # were recorded out-of-order.
    window_size = 500

    def get_time(record):
        return record.when if hasattr(record, 'when') else 0

    def add_record(itera):
        try:
            arecord = itera.next()
        except StopIteration:
            return
        sort_key = (get_time(arecord), arecord.job, arecord.pid)
        heappush(q, (sort_key, arecord, itera))

    for fname in fnames:
        itera = make_iterator(fname)
        for _ in range(window_size):
            add_record(itera)

    while q:
        _, record, itera = heappop(q)
        # fetch another recrod
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
              ('phase', c_uint32), ('partition', c_uint8),
              ('class', c_uint8)]

    def process(self, task_dict):
        params = TaskParams(self.wcet, self.period, self.partition)
        task_dict[self.pid].params = params
        #TODO task_dict[self.pid].responsetime = {}

class ReleaseRecord(SchedRecord):
    # 'when' is actually 'release' in sched_trace
    FIELDS = [('when', c_uint64), ('deadline', c_uint64)]

    def process(self, task_dict):
        data = task_dict[self.pid]
        data.jobs += 1
        if data.params and self.when >= task_dict[self.pid].misses.sync_release_time:
            data.misses.start_time(self, self.deadline)
            data.responsetime[self.job].releasetime = self.when
            data.responsetime[self.job].deadlinetime = self.deadline

class CompletionRecord(SchedRecord):
    FIELDS = [('when', c_uint64)]

    def process(self, task_dict):
        if self.when >= task_dict[self.pid].misses.sync_release_time:
            task_dict[self.pid].misses.end_time(self, self.when)
            task_dict[self.pid].responsetime[self.job].completiontime = self.when

class BlockRecord(SchedRecord):
    FIELDS = [('when', c_uint64)]

    def process(self, task_dict):
        task_dict[self.pid].blocks.start_time(self, self.when)

class ResumeRecord(SchedRecord):
    FIELDS = [('when', c_uint64)]

    def process(self, task_dict):
        task_dict[self.pid].blocks.end_time(self, self.when)

class SwitchToRecord(SchedRecord):
    FIELDS = [('when', c_uint64)]

    def process(self, task_dict):
        if (task_dict[self.pid].params and
            self.when >= task_dict[self.pid].preemptions.sync_release_time) :
            task_dict[self.pid].preemptions.add_event(self, self.when)
            jobdata = task_dict[self.pid].responsetime[self.job]
            if  jobdata.starttime == 0:
                jobdata.starttime = self.when

class SwitchAwayRecord(SchedRecord):
    FIELDS = [('when', c_uint64)]

    def process(self, task_dict):
        if (task_dict[self.pid].params and
            self.when >= task_dict[self.pid].preemptions.sync_release_time) :
            task_dict[self.pid].preemptions.add_event(self, self.when)

class SysReleaseRecord(SchedRecord):
    FIELDS = [('when', c_uint64), ('at', c_uint64)]

    def process(self, task_dict):
        for k in task_dict:
            task_dict[k].misses.sync_release_time = self.at
            task_dict[k].preemptions.sync_release_time = self.at

# Map records to sched_trace ids (see include/litmus/sched_trace.h
register_record(2, ParamRecord)
register_record(3, ReleaseRecord)
register_record(5, SwitchToRecord)
register_record(6, SwitchAwayRecord)
register_record(7, CompletionRecord)
register_record(8, BlockRecord)
register_record(9, ResumeRecord)
register_record(11, SysReleaseRecord)


def create_task_dict(data_dir, work_dir = None):
    '''Parse sched trace files'''
    bin_files   = conf.FILES['sched_data'].format(".*")
    output_file = "%s/out-st" % work_dir

    systemData = defaultdict(lambda: {"preemptions": 0, "filtered_preemptions": 0})

    task_dict = defaultdict(lambda :
                            TaskData(None, 1,
                                TimeTracker(is_valid_duration = lambda x: x > 0),
                                TimeTracker(capper = lambda x: max(x, 0)),
                                EventTraker(systeminfo = systemData),
                                defaultdict(JobInfo),
                                systemData))

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

    return (systemData, task_dict)

LOSS_MSG = """Found task missing more than %d%% of its scheduling records.
These won't be included in scheduling statistics!"""%(100*conf.MAX_RECORD_LOSS)
SKIP_MSG = """Measurement '%s' has no non-zero values.
Measurements like these are not included in scheduling statistics.
If a measurement is missing, this is why."""

def extract_sched_data(result, data_dir, work_dir):
    system, task_dict = create_task_dict(data_dir, work_dir)
    stat_data = defaultdict(list)

    # Group per-task values
    #for tdata in task_dict.itervalues():
    for pid, tdata in task_dict.iteritems():
        if not tdata.params:
            # Currently unknown where these invalid tasks come from...
            continue

        miss = tdata.misses

        record_loss = float(miss.disjoints())/(miss.matches + miss.disjoints())
        stat_data["record-loss"].append(record_loss)

        if record_loss > conf.MAX_RECORD_LOSS:
            log_once("dir = {2}, miss.disjoints = {0}, miss.matches = {1}"+
                     " ratio= {3}%".format(unicode(miss.disjoints()),
                                           unicode(miss.matches),
                                           unicode(data_dir),
                                           unicode(100*record_loss)))

        if record_loss > conf.MAX_RECORD_LOSS:
            log_once(LOSS_MSG)
            continue

        miss_ratio = float(miss.num) / miss.matches
        avg_tard = miss.avg * miss_ratio

        stat_data["miss-ratio" ].append(miss_ratio)

        stat_data["tard-max"].append(float(miss.max) / tdata.params.period)
        stat_data["tard-avg"].append(avg_tard / tdata.params.period)

        stat_data["block-avg"].append(tdata.blocks.avg / NSEC_PER_MSEC)
        stat_data["block-max"].append(tdata.blocks.max / NSEC_PER_MSEC)

        preemptions = tdata.preemptions.get_preemptions()
        filtered_preemptions = tdata.preemptions.get_filtered_preemptions()
        migrations = tdata.preemptions.get_migrations()
        jobs = tdata.preemptions.get_jobs()
        stat_data["jobs"].append(jobs)
        stat_data["preemptions"].append(preemptions)
        stat_data["filtered-preemptions"].append(filtered_preemptions)
        stat_data["migrations"].append(migrations)
        stat_data["preemptions-per-job"].append(float(preemptions)/jobs)
        stat_data["migrations-per-job"].append(float(migrations)/jobs)
        stat_data["filtered-preemptions-per-job"].append(float(filtered_preemptions)/jobs)

        # Manage per task data
        tempJitter = []
        tempResponse = []
        error = 0
        lastJob = tdata.responsetime[max(tdata.responsetime.keys())]
        for job in tdata.responsetime.itervalues() :
            if job == lastJob :
                # Last job data is garbage! Experiment terminates without
                # knowing the state of each job!!!
                continue
            if ( (job.releasetime < job.starttime) and
                 (job.starttime < job.completiontime) ):
                tempJitter.append(float(job.starttime - job.releasetime)/NSEC_PER_MSEC)
                tempResponse.append(float(job.completiontime - job.starttime)/NSEC_PER_MSEC)
            else :
                error += 1

        name = "jitter{}".format(pid)
        result[name] = Measurement(name).from_array(tempJitter)
        name = "response{}".format(pid)
        result[name] = Measurement(name).from_array(tempResponse)

    # Manage system-wide data
    for key, data in system.iteritems():
        name = "preemp-cpu{}".format(key)
        result[name] = Measurement(name).from_array([data["preemptions"]])
        name = "f_preemp-cpu{}".format(key)
        result[name] = Measurement(name).from_array([data["filtered_preemptions"]])

    # Summarize value groups
    for name, data in stat_data.iteritems():
        if not data:
            log_once(SKIP_MSG, SKIP_MSG % name)
            continue
        result[name] = Measurement(str(name)).from_array(data)
