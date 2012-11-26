import sys
from collections import defaultdict
from textwrap import dedent

def get_executable(prog, hint, optional=False):
    import os
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
                         "of '%s' which should be added to PATH to run." %
                         (prog, hint))
        sys.exit(1)
    else:
        return None

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
    except SyntaxError, e:
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
        parsed = eval(data)
        # Convert to defaultdict
        for k in parsed:
            params[k] = str(parsed[k])
    except Exception as e:
        raise IOError("Invalid param file: %s\n%s" % (fname, e))

    return params
