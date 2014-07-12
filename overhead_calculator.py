#!/usr/bin/env python

import sys
import run_exps

def main():
    
    if len(sys.argv) < 2:
        raise Exception("Invalid parameters")
    
    fname = sys.argv[1]
    if len(sys.argv) > 2:
        overhead = float(sys.argv[2])
    else:
        overhead = 0.6
    if len(sys.argv) > 3:
        min_c = float(sys.argv[3])
    else:
        min_c = 0.0
    
    with open(fname, 'r') as f:
        data = f.read().strip()
    
    try:
        schedule = eval(data)
    except:
        schedule = run_exps.convert_data(data)
    
    ts = []
    for task_conf in schedule['task']:
        
        (task, args) = (task_conf[0], task_conf[1])
        real_args = args.split()
        
        C = float(real_args[-2])
        if (C > min_c):
            s = 1 - round((overhead / C),3)
            ts.append('-s {0:.3f} {1}\n'.format(s, args))
        else:
            print 'Discarded task: {0} {1}'.format(C, real_args[-1])
        #print '-s {0:.3f} {1}'.format(s, args)
    
    with open(fname, 'w') as out_file:
        for t in ts:
            out_file.write(t)
    
if __name__ == '__main__':
    main()
