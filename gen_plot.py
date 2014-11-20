#!/usr/bin/env python
'''
Created on Sep 3, 2014

@author: davide
'''
# This script takes in input a mapfile, a collapsing class and returns a set of gnuplot scripts

import sys
import os.path
import pprint
import csv
import numpy as np

trace_types = ['cxs', 'plugin-sched', 'release', 'release-latency', 
               'sched', 'sched2', 'tick', 'tree', 'sum', 'jobs', 
               'preemptions', 'migrations', 'preemptions-per-job', 'migrations-per-job']
measure_types = ['avg', 'max', 'min', 'var', 'sum']

def get_class(value, classes):
    for c in classes:
        if value <= c:
            return c
            
def gen_plotting_data(collapsed_dict, classes, schedulers, trace_type, measure_type1, measure_type2):
    out = []
    for c in classes:
        row = (c,)
        header = ('class',)
        for s in schedulers:
            if not len(out) > 0:
                header += (s,)
            v = collapsed_dict.get((s, c))
            if trace_type in v and v[trace_type][measure_type1][measure_type2]: 
                row += (format(v[trace_type][measure_type1][measure_type2], '.3f'),)
            else:
                row += (0,)
        if not len(out) > 0:
            out.append(header)
        out.append(row)
    return out
    
def get_gnuplot_file(data, out_dir, out_name, xlabel="Utilization cap", ylabel="Time ({/Symbol m}s)"):
    out_chartname = out_name + '.pdf'
    out_gnuplotname = out_name + '.gnuplot'
    out_dataname = out_name + '.csv'
    out_template = """#!/usr/bin/gnuplot
reset
set terminal pdf dashed enhanced font 'Verdana,9'
set size ratio 0.5
set output '{0}'
set datafile separator ","
set border linewidth 4
set style line 1 lc rgb "#ff420E" lt 1 lw 4 pt 2 ps 0.4 # --- red
set style line 2 lc rgb "#004586" lt 3 lw 4 pt 7 ps 0.4 # --- blue
set key left top
set xlabel '{1}' offset 0, 0.5
set ylabel '{2}' offset 2
set yrange [0:]
plot '{3}' using 1:2 w lp ls 2 title columnhead, \\
'' using 1:3 w lp ls 1 title columnhead""".format(out_chartname, xlabel, ylabel, out_dataname)
    
    with open(os.path.join(out_dir, out_gnuplotname), "wb") as f:
        f.write(out_template)
        
    with open(os.path.join(out_dir, out_dataname), "wb") as f:
        writer = csv.writer(f)
        writer.writerows(data)

def list_of_dicts_to_list(list_of_dicts, trace_type, measure_type):
    tmp_list = []
    for v in list_of_dicts:
        if v.has_key(trace_type):
            tmp_list.append(v[trace_type][measure_type])
    return tmp_list

def collapse(dicts_list):
    collapsed_dict = {}
    for t in trace_types:
        for m in measure_types:
            for k in dicts_list: # k == 4.0 4.5 ...
                data = list_of_dicts_to_list(dicts_list[k], t, m)
                data.sort()
                if not collapsed_dict.has_key(k):
                    collapsed_dict[k] = {}
                vavg = vmax = vmin = vvar = 0
                
                if len(data) > 0:
                    vavg = np.mean(data)
                    vmax = data[-1]
                    vmin = data[0]
                    vvar = np.var(data)
                
                if not collapsed_dict[k].has_key(t):
                    collapsed_dict[k][t] = {'avg' : {m : vavg},
                                            'max' : {m : vmax},
                                            'min' : {m : vmin},
                                            'var' : {m : vvar}}
                else:
                    collapsed_dict[k][t]['avg'][m] = vavg
                    collapsed_dict[k][t]['max'][m] = vmax
                    collapsed_dict[k][t]['min'][m] = vmin
                    collapsed_dict[k][t]['var'][m] = vvar
                    
    return collapsed_dict

def main():
    if len(sys.argv) < 3:
        raise Exception("Invalid parameters: USAGE {0} FILE OUT_DIR [COLLAPSING_CLASS]".format(sys.argv[0]))
    
    fname = sys.argv[1]
    out_dir = sys.argv[2]
    col_class = 'mutils'
    
    if len(sys.argv) > 3:
        col_class = sys.argv[3].strip()
    
    print 'Reading {0}'.format(fname)
    
    with open(fname, 'r') as f:
        data = f.read().strip()
    
    evaluated = eval(data)
    
    if col_class not in evaluated['columns']:
        raise Exception("Invalid collapsing class")
    
    col_index = evaluated['columns'].index(col_class)
    scheduler_index = evaluated['columns'].index('scheduler')
    
    classes = []
    schedulers = []
    for k in evaluated['rows'].keys():
        if k[col_index] not in classes:
            classes.append(k[col_index])
        if k[scheduler_index] not in schedulers:
            schedulers.append(k[scheduler_index])
    
    classes.sort()
    first_collapsed_dict = {}
    
    #see http://stackoverflow.com/questions/3749512/python-group-by
    
    for k in evaluated['rows'].keys():
        if col_class == 'mutils':
            actual_class = k[col_index]#get_class(k[autils_index], classes)
        else:
            actual_class = k[col_index]#get_class(k[col_index], classes) #<-- in this case it returns k[col_class]
        actual_key = (k[scheduler_index], actual_class)
        if first_collapsed_dict.has_key(actual_key):
            first_collapsed_dict[actual_key] += [evaluated['rows'][k]]
        else:
            first_collapsed_dict[actual_key] = [evaluated['rows'][k]]
        
    second_collapsed_dict = collapse(first_collapsed_dict)
    #pprint.pprint(second_collapsed_dict)
    
    try:
        os.stat(out_dir)
    except:
        os.mkdir(out_dir)
    
    plot_traces = ['plugin-sched', 'release', 'sum', 
                   'jobs', 'preemptions', 'migrations', 
                   'preemptions-per-job', 'migrations-per-job']
    plot_measure = ['avg', 'sum']
    for t in plot_traces:#trace_types:
        for m in plot_measure:#measure_types:
            get_gnuplot_file(gen_plotting_data(second_collapsed_dict, classes, schedulers, t, 'avg', m), 
                             out_dir, '_'.join([t, m, 'avg']))
        
if __name__ == '__main__':
    main()