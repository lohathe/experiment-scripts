from __future__ import print_function
import os
import sys

"""
These are paths to repository directories.

"""
REPOS = {'liblitmus'   : '/home/hermanjl/git/liblitmus',
         'sched_trace' : '/home/hermanjl/git/sched_trace',
         'analysis'    : '/home/hermanjl/git/overhead-analysis-cjk',
         'ft_tools'    : '/home/hermanjl/git/feather-trace-tools',
         'trace-cmd'   : '/home/hermanjl/git/trace-cmd'}

BINS = {'bespin'    : '{}/bespin'.format(REPOS['liblitmus']),
        'colorspin' : '{}/colorspin'.format(REPOS['liblitmus']),
        'rtspin'    : '{}/rtspin'.format(REPOS['liblitmus']),
        'release'   : '{}/release_ts'.format(REPOS['liblitmus']),
        'ftcat'     : '{}/ftcat'.format(REPOS['ft_tools']),
        'st_trace'  : '{}/st_trace'.format(REPOS['ft_tools']),
        'split'     : '{}/split'.format(REPOS['analysis']),
        'sort'      : '{}/sort-all'.format(REPOS['analysis']),
        'analyze'   : '{}/analyze'.format(REPOS['analysis']),
        'trace-cmd' : '{}/trace-cmd'.format(REPOS['trace-cmd'])}

DEFAULTS = {'params_file' : 'params.py',
            'sched_file'  : 'sched.py',
            'exps_file'   : 'exps.py',
            'duration'    : '10',
            'spin'		  : 'rtspin'}

FILES = {'ft_data'    : 'ft.bin',
         'linux_data' : 'trace.dat',
         'sched_data' : 'st-{}.bin',
         'log_data'   : 'trace.slog'}

PARAMS = {'sched' : 'scheduler',
          'dur'   : 'duration'}

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
