#!/usr/bin/env python
'''
Created on 25/giu/2013

@author: davide
'''
import sys
import os.path
import run_exps
import schedcat.model.tasks as tasks
from gen.edf_generators import QPSGenerator

def main():
    
    if len(sys.argv) != 3:
        raise Exception("Invalid parameters")
    
    fname = sys.argv[1]
    (path, name) = os.path.split(fname)
    cpus = int(sys.argv[2])
    
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
        
        index = 0
        if '-S' in real_args:
            index = real_args.index('-S') + 2
            
        if '-p'in real_args:
            index = real_args.index('-p') + 2
            
        ts.append(tasks.SporadicTask(int(real_args[index + 0]), int(real_args[index + 1])))
    
    generator = QPSGenerator()
    generator.out_dir = path
    generator._customize(ts, {'cpus': cpus})
    
    with open(path + "/" + 'sched.py', 'w') as out_file:
        for t in ts:
            out_file.write("-p {0} -S {1} {2} {3}\n".format(t.cpu, t.set, t.cost, t.period))
    
if __name__ == '__main__':
    main()