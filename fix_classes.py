#!/usr/bin/env python
'''
Created on Sep 25, 2014

@author: davide compagnin
'''

from optparse import OptionParser
import os
from config.config import FILES
import common as com
from collections import namedtuple
from pprint import pprint

def parse_args():
    parser = OptionParser("usage: %prog [options] [data_dir]...")

    return parser.parse_args()

ExpData = namedtuple('ExpData', ['path', 'params'])

def get_exp_params(data_dir):
    param_file = "%s/%s" % (data_dir, FILES['params_file'])
    if os.path.isfile(param_file):
        params = com.load_params(param_file)
    else:
        params = {}        
    return params

def get_class(value, sorted_classes):
    for c in sorted_classes:
        if value <= c:
            return c

def main():
    opts, args = parse_args()
    exp_dirs = args
    exps = []
    for data_dir in exp_dirs:
        if not os.path.isdir(data_dir):
            raise IOError("Invalid experiment '%s'" % os.path.abspath(data_dir))
        params = get_exp_params(data_dir)
        exps += [ExpData(data_dir, params)]
    
    classes = []
    for e in exps:
        print 'Reading: {0}'.format(unicode(e.path))
        c = e.params['mutils']
        if c not in classes:
            classes += [c]
    
    classes.sort()
    
    if len(classes) == 0:
        raise Exception
    
    for e in exps:
        exp_params_file = os.path.join(e.path, FILES['params_file'])
        print 'Fixing: {0}'.format(unicode(exp_params_file))
        with open(exp_params_file, 'w+') as f:
            e.params['mutils'] = get_class(e.params['autils'], classes)
            pprint(e.params, f)
            
    print 'All done!'
    
if __name__ == '__main__':
    main()