import litmus_util
import os
import config.config as conf

from operator import methodcaller
from executable.ftcat import FTcat,Executable


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
        
        extra_args = ["record", # "-e", "sched:sched_switch",
                      "-e", "litmus:*",
                      "-o", "%s/%s" % (output_dir, conf.FILES['linux_data'])]
        stdout = open('%s/trace-cmd-stdout.txt' % self.output_dir, 'w')
        stderr = open('%s/trace-cmd-stderr.txt' % self.output_dir, 'w')
        
        execute = Executable(conf.BINS['trace-cmd'], extra_args, stdout, stderr)
        execute.cwd = output_dir
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
        
        out_file = open("%s/%s" % (self.output_dir, conf.FILES['log_data']), 'w')

        cat = (Executable("/bin/cat", [LogTracer.DEVICE_STR]))
        cat.stdout_file = out_file

        self.bins.append(cat)

    @staticmethod
    def enabled():
        return litmus_util.is_device(LogTracer.DEVICE_STR)
    

class SchedTracer(Tracer):
    DEVICE_STR = '/dev/litmus/sched_trace'

    def __init__(self, output_dir):
        super(SchedTracer, self).__init__("Sched Trace", output_dir)

        if SchedTracer.enabled():
            for cpu in range(litmus_util.num_cpus()):
                # Executable will close the stdout/stderr files
                stdout_f = open('%s/st-%d.bin' % (self.output_dir, cpu), 'w')
                stderr_f = open('%s/st-%d-stderr.txt' % (self.output_dir, cpu), 'w')
                dev = '{0}{1}'.format(SchedTracer.DEVICE_STR, cpu)
                ftc = FTcat(conf.BINS['ftcat'], stdout_f, stderr_f, dev, conf.SCHED_EVENTS, cpu=cpu)

                self.bins.append(ftc)

    @staticmethod
    def enabled():
		return litmus_util.is_device("%s%d" % (SchedTracer.DEVICE_STR, 0))

    
class OverheadTracer(Tracer):
    DEVICE_STR = '/dev/litmus/ft_trace0'

    def __init__(self, output_dir):
        super(OverheadTracer, self).__init__("Overhead Trace", output_dir)

        stdout_f = open('{0}/{1}'.format(self.output_dir, conf.FILES['ft_data']), 'w')
        stderr_f = open('{0}/{1}.stderr.txt'.format(self.output_dir, conf.FILES['ft_data']), 'w')
        ftc = FTcat(conf.BINS['ftcat'], stdout_f, stderr_f,
                OverheadTracer.DEVICE_STR, conf.ALL_EVENTS)

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
