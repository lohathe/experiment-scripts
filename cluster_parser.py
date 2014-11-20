#!/usr/bin/env python
'''
Created on Sep 23, 2014

@author: davide compagnin
'''

from optparse import OptionParser
import os
from config.config import FILES
import common as com
from collections import namedtuple
import csv 
import json
from math import ceil
from pprint import pprint
import numpy as np

class Node:
    
    def __init__(self, id, rate_num, rate_den, level, children = []):
        self.id = id
        self.rate_num = rate_num
        self.rate_den = rate_den
        self.level = level
        self.children = children
        
    def utilization(self):
        return 1 - (float(self.rate_num) / float(self.rate_den))

def parse_args():
    parser = OptionParser("usage: %prog [options] [data_dir]...")

    parser.add_option('-o', '--out-dir', dest='out_dir',
                      help='file or directory for data output',
                      default='/tmp')

    return parser.parse_args()

ExpData = namedtuple('ExpData', ['path', 'params'])

def get_exp_params(data_dir):
    param_file = "%s/%s" % (data_dir, FILES['params_file'])
    if os.path.isfile(param_file):
        params = com.load_params(param_file)
    else:
        params = {}        
    return params

def parse_node(data):
    if len(data) < 1:
        return []
    children = []
    for d in data:
        n = Node(d['id'], d['cost'], d['period'], d['level'], parse_node(d['children']))
        children.append(n)
    return children

def rebuild_tree(data):
    return Node(data['id'], data['cost'], 
                data['period'], data['level'], 
                parse_node(data['children']))

def get_qps_clusters(fname, cpus):
    masters = []
    with open(fname, 'r') as f:
        csvreader = csv.reader(f, delimiter=' ')
        for row in csvreader:
            masters.append(row)
    
    mapping = {k: {'top' : k, 'level': 0} for k in range(0,cpus)}

    for m in masters:
        from_cpu = int(m[2].strip())
        to_cpu = int(m[0].strip())
        for k,v in mapping.iteritems():
            if v['top'] == from_cpu:
                mapping[k]['top'] = mapping[to_cpu]['top'] 
                mapping[k]['level'] += 1
    
    tmp = [(v['top'],v['level']) for k,v in mapping.iteritems()]
    keys = list(set([v['top'] for k,v in mapping.iteritems()]))
    clusters = []
    for k in keys:
        tmp2 = [y for x,y in tmp if x==k]
        clusters.append((len(tmp2), max(tmp2)))
    return clusters

def get_unit_servers(node, clusters):
    if len(node.children) < 1:
        if node.rate_num == 0:
            clusters.append((1, 0))
            return 0
        else:
            return node.utilization()
    sum = 0
    for n in node.children:
        sum += get_unit_servers(n, clusters) 
    if node.rate_num == 0:
        clusters.append((int(ceil(sum)), int(node.level)))
        return 0
    else:
        return sum
        
def get_run_clusters(fname):
    with open(fname, 'r') as f:    
        data = json.load(f)
        root = rebuild_tree(data);
    clusters = []
    get_unit_servers(root, clusters)
    return clusters

def get_num_of_tasks(fname):
    return sum(1 for line in open(fname, 'r'))

def gen_gnuplot_file(data, out_dir, out_name, xlabel="Utilization cap", ylabel=""):
    out_chartname = out_name + '.pdf'
    out_gnuplotname = out_name + '.gnuplot'
    out_dataname = out_name + '.csv'
    out_template = """#!/usr/bin/gnuplot
reset
set terminal pdf dashed enhanced font 'Verdana,10'
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

def gen_plotting_data(collapsed_dict, classes, schedulers, metrics, measure_type):
    out = []
    for c in classes:
        row = (c,)
        header = ('class',)
        for s in schedulers:
            if not len(out) > 0:
                header += (s,)
            v = collapsed_dict.get((s, c))
            if metrics in v and v[metrics][measure_type]: 
                row += (format(v[metrics][measure_type], '.3f'),)
            else:
                row += (0,)
        if not len(out) > 0:
            out.append(header)
        out.append(row)
    return out


def gen_gnuplot_levels_file(data, out_dir, out_name, xlabel="Utilization cap", ylabel=""):
    out_chartname = out_name + '.pdf'
    out_gnuplotname = out_name + '.gnuplot'
    out_dataname = out_name + '.csv'
    out_template = """#!/usr/bin/gnuplot
    reset
set terminal pdf dashed enhanced font 'Verdana,10'
set size ratio 0.5
set output '{0}'
set datafile separator ","
set grid
set border 3
#set border linewidth 4
set style data histograms
set style histogram rowstacked
set boxwidth 0.75
set style fill solid 1.00 border -1 
#set key horiz bmargin center
set key outside right top vertical Left reverse noenhanced autotitles columnhead nobox
set format y "%g %%"
set ylabel 'Ratio' offset 1
set yrange [0:100]
set xlabel 'Utilization cap' offset 0, -0.5
set xtics nomirror scale 0 font ",7"
set style line 1 lc rgb '#aa9d88' lt 1 lw 1
set style line 2 lc rgb '#9ebaa0' lt 1 lw 2
set style line 3 lc rgb '#738e96' lt 1 lw 2
set style line 4 lc rgb '#f2fcff' lt 1 lw 2
set style line 5 lc rgb '#f2fcaa' lt 1 lw 2
set style line 6 lc rgb '#aafcff' lt 1 lw 2
#set style fill pattern 1
set datafile separator ","
plot newhistogram "QPS", \\
    '{3}' using ($2*100):xticlabels(1) title columnhead ls 1, \\
    '' using ($3*100):xticlabels(1) title columnhead ls 2, \\
    '' using ($4*100):xticlabels(1) title columnhead ls 3, \\
    '' using ($5*100):xticlabels(1) title columnhead ls 4, \\
    '' using ($6*100):xticlabels(1) title columnhead ls 5, \\
    newhistogram "RUN", \\
    '' using ($8*100):xticlabels(1) notitle ls 1, \\
    '' using ($9*100):xticlabels(1) notitle ls 2, \\
    '' using ($10*100):xticlabels(1) notitle ls 3, \\
    '' using ($11*100):xticlabels(1) notitle ls 4, \\
    '' using ($12*100):xticlabels(1) notitle ls 5""".format(out_chartname, xlabel, ylabel, out_dataname)
    
    with open(os.path.join(out_dir, out_gnuplotname), "wb") as f:
        f.write(out_template)
        
    with open(os.path.join(out_dir, out_dataname), "wb") as f:
        writer = csv.writer(f)
        writer.writerows(data)

def gen_plotting_levels_data(collapsed_dict, classes, schedulers, trace_types):
    out = []
    for c in classes:
        row = (c,)
        header = ('class',)
        for s in schedulers:
            for t in trace_types:
                if not len(out) > 0:
                    header += (t,)
                v = collapsed_dict.get((s, c))
                if t in v and v[t]: 
                    row += (format(v[t], '.3f'),)
                else:
                    row += (0,)
        if not len(out) > 0:
            out.append(header)
        out.append(row)
    return out

# Replaced by fix_classes.py script
#def get_class(value, sorted_classes):
#    for c in sorted_classes:
#        if value <= c:
#            return c

def main():
    opts, args = parse_args()
    exp_dirs = args
    exps = []
    cols = ['scheduler', 'autils', 'mutils', 'tasks']
    levels = ['level-0', 'level-1', 'level-2', 'level-3', 'level-4', 'level-5']
    metrics = ['clusters', 'clusters-avg', 'levels-max', 'levels-avg'] + levels
    measure_types = ['max', 'min', 'avg', 'var', 'sum']
    out = {'columns' : cols, 'rows' : {}}
    
    if len(exp_dirs) < 1:
        raise Exception('No experiments: USAGE cluster_paser.py EXP_DIR -o OUT_DIR')
    
    for data_dir in exp_dirs:
        if not os.path.isdir(data_dir):
            raise IOError("Invalid experiment '%s'" % os.path.abspath(data_dir))

        params = get_exp_params(data_dir)
        exps += [ExpData(data_dir, params)]
    
    classes = []
    schedulers = []
    for e in exps:
        tasks = get_num_of_tasks(os.path.join(e.path, FILES['sched_file']))
        cpus = e.params['cpus']
        k = (e.params[cols[0]], e.params[cols[1]], e.params[cols[2]], tasks)
        (s,u,c,t) = k
        if c not in classes:
            classes += [c]
        if s not in schedulers:
            schedulers += [s]
        if e.params['scheduler'] == 'QPS':
            v = get_qps_clusters(os.path.join(e.path, FILES['masters_file']), cpus)
        if e.params['scheduler'] == 'RUN':
            if tasks <= cpus:
                v = [(1,0) for i in range(0,cpus)]
            else:
                v = get_run_clusters(os.path.join(e.path, FILES['nodes_file']))
            
        if k in out['rows'].keys():
            tmp = out['rows'][k]['clusters']
            out['rows'][k]['clusters'] = tmp + len(v)
            tmp = out['rows'][k]['clusters-avg']
            out['rows'][k]['clusters-avg'] = np.mean([tmp, len(v)])
            tmp = out['rows'][k]['levels-max']
            out['rows'][k]['levels-max'] = max(tmp, max(v, key=lambda x:x[1])[1])
            tmp = out['rows'][k]['levels-avg']
            out['rows'][k]['levels-avg'] = np.mean([tmp] + [l for c,l in v])
            tmp = out['rows'][k]['level-0']
            out['rows'][k]['level-0'] = tmp + len([l for c,l in v if l == 0])
            tmp = out['rows'][k]['level-1']
            out['rows'][k]['level-1'] = tmp + len([l for c,l in v if l == 1])
            tmp = out['rows'][k]['level-2']
            out['rows'][k]['level-2'] = tmp + len([l for c,l in v if l == 2])
            tmp = out['rows'][k]['level-3']
            out['rows'][k]['level-3'] = tmp + len([l for c,l in v if l == 3])
            tmp = out['rows'][k]['level-4']
            out['rows'][k]['level-4'] = tmp + len([l for c,l in v if l == 4])
            tmp = out['rows'][k]['level-5']
            out['rows'][k]['level-5'] = tmp + len([l for c,l in v if l == 5])
        else:
            out['rows'][k] = {'clusters' : len(v),
                              'clusters-avg' : len(v),
                              'levels-max': max(v, key=lambda x:x[1])[1], 
                              'levels-avg': np.mean([l for c,l in v]),
                              'level-0': len([l for c,l in v if l == 0]),
                              'level-1': len([l for c,l in v if l == 1]),
                              'level-2': len([l for c,l in v if l == 2]),
                              'level-3': len([l for c,l in v if l == 3]),
                              'level-4': len([l for c,l in v if l == 4]),
                              'level-5': len([l for c,l in v if l == 5]),}
    #pprint(out)
    classes.sort()
    
    first_collapsed_dict = {}
    for k in out['rows'].keys():
        for m in metrics:
            (s,u,c,t) = k
            # Replaced by fix_classes.py script
            #new_k = (s, get_class(u,classes))
            new_k = (s, c)
            if new_k in first_collapsed_dict:
                if m in first_collapsed_dict[new_k]:
                    first_collapsed_dict[new_k][m] += [out['rows'][k][m]]
                else:
                    first_collapsed_dict[new_k][m] = [out['rows'][k][m]]
            else:  
                first_collapsed_dict[new_k] = {m: [out['rows'][k][m]]}
                
    
    second_collapsed_dict = {}
    for k in first_collapsed_dict.keys():
        for m in metrics:
            tmp = first_collapsed_dict[k][m]
            tmp.sort()
            if k not in second_collapsed_dict:
                second_collapsed_dict[k] = {}
            if m not in second_collapsed_dict[k]:
                second_collapsed_dict[k][m] = {'max': tmp[-1], 
                                               'min': tmp[0], 
                                               'avg': np.mean(tmp), 
                                               'var': np.var(tmp),
                                               'sum': np.sum(tmp)}
    
    levels_out = {}
    for k in second_collapsed_dict.keys():
        for m in levels:
            if k not in levels_out:
                levels_out[k] = {'level-0': 0.0, 
                                 'level-1': 0.0, 
                                 'level-2': 0.0, 
                                 'level-3': 0.0,
                                 'level-4': 0.0,
                                 'level-5': 0.0}
            levels_out[k][m] = float(second_collapsed_dict[k][m]['sum'])/ second_collapsed_dict[k]['clusters']['sum']
            
    pprint(second_collapsed_dict)
    pprint(levels_out)
    
    for m in metrics: #levels, custers
        for t in measure_types: # max min avg
            gen_gnuplot_file(gen_plotting_data(second_collapsed_dict, classes, schedulers, m, t), 
                             opts.out_dir, '_'.join([m, t]))
            
    gen_gnuplot_levels_file(gen_plotting_levels_data(levels_out, classes, schedulers, levels), 
                             opts.out_dir, 'levels')
            
    
    pass
    
if __name__ == '__main__':
    main()