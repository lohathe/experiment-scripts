import litmus_util
import os
from operator import methodcaller
from executable.ftcat import FTcat,Executable
from config.config import FILES,BINS

class Tracer(object):
    def __init__(self, name, output_dir):
        self.name = name
        self.output_dir = output_dir
        self.bins = []

    def start_tracing(self):
        map(methodcaller("execute"), self.bins)

    def stop_tracing(self):
        map(methodcaller('terminate'), self.bins)
        map(methodcaller('wait'), self.bins)

        
class LinuxTracer(Tracer):
    EVENT_ROOT = "/sys/kernel/debug/tracing"
    LITMUS_EVENTS = "%s/events/litmus" % EVENT_ROOT

    def __init__(self, output_dir):
        super(LinuxTracer, self).__init__("trace-cmd", output_dir)
        
        extra_args = ["record", "-e", "sched:sched_switch",
                      "-e", "litmus:*",
                      "-o", "%s/%s" % (output_dir, FILES['linux_data'])]
        stdout = open('%s/trace-cmd-stdout.txt' % self.output_dir, 'w')
        stderr = open('%s/trace-cmd-stderr.txt' % self.output_dir, 'w')
        
        execute = Executable(BINS['trace-cmd'], extra_args, stdout, stderr)
        self.bins.append(execute)
        
    @staticmethod
    def enabled():
        return os.path.exists(LinuxTracer.LITMUS_EVENTS)

    def stop_tracing(self):
        map(methodcaller('interrupt'), self.bins)
        map(methodcaller('wait'), self.bins)

    
class LogTracer(Tracer):
    DEVICE_STR = '/dev/litmus/log'

    def __init__(self, output_dir):
        super(LogTracer, self).__init__("Logger", output_dir)
        
        out_file = open("%s/%s" % (self.output_dir, FILES['log_data']), 'w')

        cat = (Executable("/bin/cat", [LogTracer.DEVICE_STR]))
        cat.stdout_file = out_file

        self.bins.append(cat)

    @staticmethod
    def enabled():
        return litmus_util.is_device(LogTracer.DEVICE_STR)
    

class SchedTracer(Tracer):
    EVENTS = range(501, 510) # not including 511
    DEVICE_STR = '/dev/litmus/sched_trace'

    def __init__(self, output_dir):
        super(SchedTracer, self).__init__("Sched Trace", output_dir)

        if SchedTracer.enabled():
            for cpu in range(litmus_util.num_cpus()):
                # Executable will close the stdout/stderr files
                stdout_f = open('%s/st-%d.bin' % (self.output_dir, cpu), 'w')
                stderr_f = open('%s/st-%d-stderr.txt' % (self.output_dir, cpu), 'w')
                dev = '{0}{1}'.format(SchedTracer.DEVICE_STR, cpu)
                ftc = FTcat(BINS['ftcat'], stdout_f, stderr_f, dev, SchedTracer.EVENTS, cpu=cpu)

                self.bins.append(ftc)

    @staticmethod
    def enabled():
		return litmus_util.is_device("%s%d" % (SchedTracer.DEVICE_STR, 0))

    
class OverheadTracer(Tracer):
    DEVICE_STR = '/dev/litmus/ft_trace0'
    EVENTS = [# 'SCHED_START', 'SCHED_END', 'SCHED2_START', 'SCHED2_END',
            'RELEASE_START', 'RELEASE_END',
            'LVLA_RELEASE_START', 'LVLA_RELEASE_END',
            'LVLA_SCHED_START', 'LVLA_SCHED_END',
            'LVLB_RELEASE_START', 'LVLB_RELEASE_END',
            'LVLB_SCHED_START', 'LVLB_SCHED_END',
            'LVLC_RELEASE_START', 'LVLC_RELEASE_END',
            'LVLC_SCHED_START', 'LVLC_SCHED_END']

    def __init__(self, output_dir):
        super(OverheadTracer, self).__init__("Overhead Trace", output_dir)

        stdout_f = open('{0}/{1}'.format(self.output_dir, FILES['ft_data']), 'w')
        stderr_f = open('{0}/{1}.stderr.txt'.format(self.output_dir, FILES['ft_data']), 'w')
        ftc = FTcat(BINS['ftcat'], stdout_f, stderr_f,
                OverheadTracer.DEVICE_STR, OverheadTracer.EVENTS)

        self.bins.append(ftc)

    @staticmethod
    def enabled():
		return litmus_util.is_device(OverheadTracer.DEVICE_STR)


class PerfTracer(Tracer):
    def __init__(self, output_dir):
        super(PerfTracer, self).__init__("CPU perf counters", output_dir)

    @staticmethod
    def enabled():
        return False
