from __future__ import print_function
import os
import sys
import itertools

'''
These are paths to repository directories.

'''
REPOS = {'liblitmus'   : '/home/hermanjl/git/liblitmus',
         'sched_trace' : '/home/hermanjl/git/sched_trace',
         'ft_tools'    : '/home/hermanjl/git/feather-trace-tools',
         'trace-cmd'   : '/home/hermanjl/git/trace-cmd'}

BINS = {'rtspin'    : '{}/rtspin'.format(REPOS['liblitmus']),
        'release'   : '{}/release_ts'.format(REPOS['liblitmus']),
        'ftcat'     : '{}/ftcat'.format(REPOS['ft_tools']),
        'ftsplit'   : '{}/ft2csv'.format(REPOS['ft_tools']),
        'ftsort'    : '{}/ftsort'.format(REPOS['ft_tools']),
        'st_trace'  : '{}/st_trace'.format(REPOS['ft_tools']),
        'trace-cmd' : '{}/trace-cmd'.format(REPOS['trace-cmd']),
        'st_show'   : '{}/st_show'.format(REPOS['sched_trace'])}

DEFAULTS = {'params_file' : 'params.py',
            'sched_file'  : 'sched.py',
            'exps_file'   : 'exps.py',
            'duration'    : 10,
            'spin'		  : 'rtspin',
            'cycles'      : 2000}

FILES = {'ft_data'    : 'ft.bin',
         'linux_data' : 'trace.dat',
         'sched_data' : 'st-{}.bin',
         'log_data'   : 'trace.slog',}

PARAMS = {'sched' : 'scheduler',
          'dur'   : 'duration',
          'kernel': 'uname',
          'cycles' : 'cpu-frequency'}

SCHED_EVENTS = range(501, 513)
BASE_EVENTS  = ['SCHED', 'RELEASE', 'SCHED2', 'TICK', 'CXS']
ALL_EVENTS   = ["%s_%s" % (e, t) for (e,t) in
                itertools.product(BASE_EVENTS, ["START","END"])]
ALL_EVENTS  += ['RELEASE_LATENCY']
BASE_EVENTS += ['RELEASE_LATENCY']

valid = True
for repo, loc in REPOS.items():
    if not os.path.isdir(loc):
        valid = False
        print("Cannot access repo '%s' at '%s'" % (repo, loc), file=sys.stderr)
for prog, loc in BINS.items():
    if not os.path.isfile(loc):
        valid = False
        print("Cannot access program '%s' at '%s'" % (prog, loc), file=sys.stderr)
if not valid:
    print("Errors in config file", file=sys.stderr)
