#!/usr/bin/env python
'''
Created on Oct 1, 2014

@author: davide compagnin
'''
import sys
import os.path
import pprint
import csv
import numpy as np

def gen_plotting_data(collapsed_dict, classes, schedulers, measure_type):
    out = []
    for c in classes:
        row = (c,)
        header = ('class',)
        for s in schedulers:
            if not len(out) > 0:
                header += (s,)
            v = collapsed_dict.get((s, c))
            row += (v[measure_type],)
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

def main():
    if len(sys.argv) < 3:
        raise Exception("Invalid parameters: USAGE {0} FILE OUT_DIR".format(sys.argv[0]))
    
    fname = sys.argv[1]
    out_dir = sys.argv[2]
    col_class = 'mutils'
    
    print 'Reading {0}'.format(fname)
    
    with open(fname, 'r') as f:
        data = f.read().strip()
    
    evaluated = eval(data)
    
    if col_class not in evaluated['columns']:
        raise Exception("Invalid collapsing class")
    
    col_index = evaluated['columns'].index(col_class)
    autils_index = evaluated['columns'].index('autils')
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
        actual_class = k[col_index]
        actual_key = (k[scheduler_index], actual_class)
        if first_collapsed_dict.has_key(actual_key):
            first_collapsed_dict[actual_key] += [float(evaluated['rows'][k]['sum']['sum'])/evaluated['rows'][k]['jobs']['sum']]
        else:
            first_collapsed_dict[actual_key] = [float(evaluated['rows'][k]['sum']['sum'])/evaluated['rows'][k]['jobs']['sum']]
    
    second_collapsed_dict = {}
    maxs = dict([(s,0) for s in schedulers])
    for k in first_collapsed_dict:
        data = first_collapsed_dict[k]
        data.sort()
        #if not second_collapsed_dict.has_key(k):
        #    second_collapsed_dict[k] = {}
        vavg = vmax = vmin = vvar = 0.0
        if len(data) > 0:
            vavg = np.mean(data)
            vmax = data[-1]
            vmin = data[0]
            vvar = np.var(data)
        second_collapsed_dict[k] = {'avg' : vavg,
                                    'max' : vmax,
                                    'min' : vmin,
                                    'var' : vvar}
        if vmax > maxs[k[0]]:
            maxs[k[0]] = vmax
    
    #pprint.pprint(second_collapsed_dict)
    get_gnuplot_file(gen_plotting_data(second_collapsed_dict, classes, schedulers, 'avg'), 
                     out_dir, 
                     'overhead-per-job')
    
    for s in schedulers:
        print 'MAX overhead-per-job {0} = {1}'.format(unicode(s), unicode(maxs[s]))
    pass

if __name__ == '__main__':
    main()