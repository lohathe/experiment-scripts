import os
import re
import stat
import subprocess
import sys

from collections import defaultdict
from textwrap import dedent

def get_executable(prog, hint, optional=False):
    '''Search for @prog in system PATH. Print @hint if no binary is found.'''

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(prog)
    if fpath:
        if is_exe(prog):
            return prog
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, prog)
            if is_exe(exe_file):
                return exe_file

    if not optional:
        sys.stderr.write("Cannot find executable '%s' in PATH. This is a part "
                         "of '%s' which should be added to PATH to run.\n" %
                         (prog, hint))
        sys.exit(1)
    else:
        return None

def get_config_option(option):
    '''Search for @option in installed kernel config (if present).
    Raise an IOError if the kernel config isn't found in /boot/.'''
    uname = subprocess.check_output(["uname", "-r"]).strip()
    fname = "/boot/config-%s" % uname

    if os.path.exists(fname):
        config_regex = "^CONFIG_{}=(?P<val>.*)$".format(option)
        with open(fname, 'r') as f:
            data = f.read()
        match = re.search(config_regex, data, re.M)
        if not match:
            return None
        else:
            return match.group("val")

    else:
        raise IOError("No config file exists!")

def try_get_config_option(option, default):
    try:
        get_config_option(option)
    except:
        return default

def recordtype(typename, field_names, default=0):
    ''' Mutable namedtuple. Recipe from George Sakkis of MIT.'''
    field_names = tuple(map(str, field_names))
    # Create and fill-in the class template
    numfields = len(field_names)
    argtxt = ', '.join(field_names)
    reprtxt = ', '.join('%s=%%r' % f for f in field_names)
    dicttxt = ', '.join('%r: self.%s' % (f,f) for f in field_names)
    tupletxt = repr(tuple('self.%s' % f for f in field_names)).replace("'",'')
    inittxt = '; '.join('self.%s=%s' % (f,f) for f in field_names)
    itertxt = '; '.join('yield self.%s' % f for f in field_names)
    eqtxt   = ' and '.join('self.%s==other.%s' % (f,f) for f in field_names)
    template = dedent('''
        class %(typename)s(object):
            '%(typename)s(%(argtxt)s)'

            __slots__  = %(field_names)r

            def __init__(self, %(argtxt)s):
                %(inittxt)s

            def __len__(self):
                return %(numfields)d

            def __iter__(self):
                %(itertxt)s

            def __getitem__(self, index):
                return getattr(self, self.__slots__[index])

            def __setitem__(self, index, value):
                return setattr(self, self.__slots__[index], value)

            def todict(self):
                'Return a new dict which maps field names to their values'
                return {%(dicttxt)s}

            def __repr__(self):
                return '%(typename)s(%(reprtxt)s)' %% %(tupletxt)s

            def __eq__(self, other):
                return isinstance(other, self.__class__) and %(eqtxt)s

            def __ne__(self, other):
                return not self==other

            def __getstate__(self):
                return %(tupletxt)s

            def __setstate__(self, state):
                %(tupletxt)s = state
    ''') % locals()
    # Execute the template string in a temporary namespace
    namespace = {}
    try:
        exec template in namespace
    except SyntaxError as e:
        raise SyntaxError(e.message + ':\n' + template)
    cls = namespace[typename]

    # Setup defaults
    init_defaults = tuple(default for f in field_names)
    cls.__init__.im_func.func_defaults = init_defaults

    # For pickling to work, the __module__ variable needs to be set to the frame
    # where the named tuple is created.  Bypass this step in environments where
    # sys._getframe is not defined (Jython for example).
    if hasattr(sys, '_getframe') and sys.platform != 'cli':
        cls.__module__ = sys._getframe(1).f_globals['__name__']

    return cls

def load_params(fname):
    params = defaultdict(int)
    with open(fname, 'r') as f:
        data = f.read()
    try:
        params = eval(data)
    except Exception as e:
        raise IOError("Invalid param file: %s\n%s" % (fname, e))

    return params


def num_cpus():
    '''Return the number of CPUs in the system.'''

    lnx_re = re.compile(r'^(processor|online)')
    cpus = 0

    with open('/proc/cpuinfo', 'r') as f:
        for line in f:
            if lnx_re.match(line):
                cpus += 1
    return cpus

def ft_freq():
    umachine = subprocess.check_output(["uname", "-m"])

    if re.match("armv7", umachine):
        # Arm V7s use a millisecond timer
        freq = 1000.0
    elif re.match("x86", umachine):
        # X86 timer is equal to processor clock
        reg = re.compile(r'^cpu MHz\s*:\s*(?P<FREQ>\d+)', re.M)
        with open('/proc/cpuinfo', 'r') as f:
            data = f.read()

        match = re.search(reg, data)
        if not match:
            raise Exception("Cannot parse CPU frequency from x86 CPU!")
        freq = int(match.group('FREQ'))
    else:
        # You're on your own
        freq = 0
    return freq


def uname_matches(reg):
    data = subprocess.check_output(["uname", "-r"])
    return bool( re.match(reg, data) )

def is_executable(fname):
    '''Return whether the file passed in is executable'''
    mode = os.stat(fname)[stat.ST_MODE]
    return mode & stat.S_IXUSR and mode & stat.S_IRUSR

def is_device(dev):
    if not os.path.exists(dev):
        return False
    mode = os.stat(dev)[stat.ST_MODE]
    return not (not mode & stat.S_IFCHR)
