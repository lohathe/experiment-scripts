import os
import time
import litmus_util
from operator import methodcaller
from tracer import SchedTracer, LogTracer, PerfTracer, LinuxTracer, OverheadTracer

class ExperimentException(Exception):
    """Used to indicate when there are problems with an experiment."""
    def __init__(self, name):
        self.name = name

        
class ExperimentDone(ExperimentException):
    """Raised when an experiment looks like it's been run already."""
    def __str__(self):
        return "Experiment finished already: %d" % self.name

    
class ExperimentInterrupted(ExperimentException):
    """Raised when an experiment appears to be interrupted (partial results)."""
    def __str__(self):
        return "Experiment was interrupted in progress: %d" % self.name

    
class ExperimentFailed(ExperimentException):
    def __str__(self):
        return "Experiment failed during execution: %d" % self.name

    
class Experiment(object):
    """Execute one task-set and save the results. Experiments have unique IDs."""

    def __init__(self, name, scheduler, working_dir, finished_dir, proc_entries, executables):
        """Run an experiment, optionally wrapped in tracing."""

        self.name = name
        self.scheduler = scheduler
        self.working_dir  = working_dir
        self.finished_dir = finished_dir
        self.proc_entries = proc_entries
        self.executables  = executables

        self.__make_dirs()
        self.__assign_executable_cwds()

        self.tracers = []
        if SchedTracer.enabled():
            self.tracers.append( SchedTracer(working_dir) )
        if LinuxTracer.enabled():
            self.tracers.append( LinuxTracer(working_dir) )
        if LogTracer.enabled():
            self.tracers.append( LogTracer(working_dir) )
        if PerfTracer.enabled():
            self.tracers.append( PerfTracer(working_dir) )

        # Overhead trace must be handled seperately, see __run_tasks
        if OverheadTracer.enabled():
            self.overhead_trace = OverheadTracer(working_dir)
        else:
            self.overhead_trace = None

    def __make_dirs(self):
        if os.path.exists(self.finished_dir):
            raise ExperimentDone(self.name)
        if os.path.exists(self.working_dir):
            raise ExperimentInterrupted(self.name)
        
        os.mkdir(self.working_dir)

    def __assign_executable_cwds(self):
        def assign_cwd(executable):
            executable.cwd = self.working_dir
        map(assign_cwd, self.executables)

    def __run_tasks(self):
        exec_pause = 0.3
        self.log("Starting the program in ({0} seconds)".format(
            len(self.executables) * exec_pause))
        for e in self.executables:
            e.execute()
            time.sleep(exec_pause)

        sleep_time = 2
        self.log("Sleeping for %d seconds before release" % sleep_time)
        time.sleep(sleep_time)

        # Overhead tracer must be started right after release or overhead
        # measurements will be full of irrelevant records
        if self.overhead_trace:
            self.log("Starting overhead trace")
            self.overhead_trace.start_tracing()

        released = litmus_util.release_tasks()

        ret = True
        if released != len(self.executables):
            self.log("Failed to release %d tasks! Re-releasing and killing".format(
                len(self.experiments) - released))
            
            time.sleep(10)
            litmus_util.release_tasks()

            time.sleep(20)
            map(methodcaller('kill'), self.executables)

            ret = False

        self.log("Waiting for program to finish...")
        map(methodcaller('wait'), self.executables)

        # And it must be stopped here for the same reason
        if self.overhead_trace:
            self.log("Stopping overhead trace")
            self.overhead_trace.stop_tracing()

        if not ret:
            raise ExperimentFailed(self.name)

    def __save_results(self):
        os.rename(self.working_dir, self.finished_dir)

    def log(self, msg):
        print "[Exp %s]: %s" % (self.name, msg)

    def run_exp(self):
        self.setup()
        self.__run_tasks()
        self.teardown()

    def setup(self):
        self.log("Switching to %s" % self.scheduler)
        litmus_util.switch_scheduler(self.scheduler)

        self.log("Writing %d proc entries" % len(self.proc_entries))
        map(methodcaller('write_proc'), self.proc_entries)
        
        self.log("Starting %d tracers" % len(self.tracers))
        map(methodcaller('start_tracing'), self.tracers)

    def teardown(self):
        sleep_time = 5
        self.log("Sleeping %d seconds to allow buffer flushing" % sleep_time)
        time.sleep(sleep_time)

        self.log("Stopping tracers")
        map(methodcaller('stop_tracing'), self.tracers)

        self.log("Switching to Linux scheduler")
        litmus_util.switch_scheduler("Linux")

        self.log("Saving results in %s" % self.finished_dir)
        self.__save_results()
        self.log("Experiment done!")
