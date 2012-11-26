import os
import stat

from executable import Executable

class FTcat(Executable):
    '''Used to wrap the ftcat binary in the Experiment object.'''

    def __init__(self, ft_cat_bin, stdout_file, stderr_file, dev, events, cpu=None):
        '''Extends the Executable initializer method with ftcat attributes.'''

        # hack to run FTCat at higher priority
        chrt_bin = '/usr/bin/chrt'

        super(FTcat, self).__init__(chrt_bin)
        self.stdout_file = stdout_file
        self.stderr_file = stderr_file

        mode = os.stat(dev)[stat.ST_MODE]
        if not mode & stat.S_IFCHR:
            raise Exception("%s is not a character device" % dev)

        if events is None:
            raise Exception('No events!')

        # hack to run FTCat at higher priority
        self.extra_args = ['-f', '40']
        if cpu is not None:
            # and bind it to a CPU
            self.extra_args.extend(['/usr/bin/taskset', '-c', str(cpu)])
        events_str_arr = map(str, events)
        self.extra_args.extend([ft_cat_bin, dev] + events_str_arr)

