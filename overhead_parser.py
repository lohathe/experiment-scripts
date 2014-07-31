#!/usr/bin/env python
'''
Created on 12/lug/2013

@author: davide
'''

import csv
import numpy as np
import os
from optparse import OptionParser

def_out_file = 'out_stat_overhead.csv'
def_release = 'overh_release.csv'
def_schedule = 'overh_schedule.csv'
def_schedule2 = 'overh_schedule2.csv'
def_tick = 'overh_tick.csv'
def_cxs = 'overh_cxs.csv'
def_latency = 'overh_release_latency.csv'
def_tree = 'overh_tree.csv'
def_dir = '.'
def_percentile = 99.9

def parse_args():
    parser = OptionParser("usage: %prog [options]")
    
    parser.add_option('-o', '--out-file', dest='out_file',
                      help='file for data output',
                      default=def_out_file)
    
    parser.add_option('-r', '--release', dest='ft_release',
                      help='ft release csv file',
                      default=def_release)
     
    parser.add_option('-s', '--schedule', dest='ft_schedule',
                      help='ft schedule csv file',
                      default=def_schedule)
    
    parser.add_option('-S', '--schedule2', dest='ft_schedule2',
                      help='ft schedule2 csv file',
                      default=def_schedule2)
    
    parser.add_option('-t', '--tick', dest='ft_tick',
                      help='ft tick csv file',
                      default=def_tick)
    
    parser.add_option('-c', '--cxs', dest='ft_cxs',
                      help='ft cxs csv file',
                      default=def_cxs)
    
    parser.add_option('-l', '--latency', dest='ft_latency',
                      help='ft latency csv file',
                      default=def_latency)
    
    parser.add_option('-T', '--tree', dest='ft_tree',
                      help='ft tree csv file',
                      default=def_tree)
    
    parser.add_option('-d', '--dir', dest='dir',
                      help='working path',
                      default=def_dir)
    
    parser.add_option('-p', '--percentile', dest='percentile',
                      help='percentile',
                      default=def_percentile)

    return parser.parse_args()

def main():
    opts, args = parse_args()
    
    files = {
             'release': None,
             'schedule': None,
             'schedule2': None,
             'tick': None,
             'cxs': None,
             'latency': None,
             'tree': None,    
    }
    
    if opts.dir:
        if os.path.exists(opts.dir):
            def_dir = opts.dir
        else:
            raise Exception(' '.join([opts.dir, 'does not exists']))

    if opts.out_file:
        def_out_file = opts.out_file
    
    if os.path.exists(opts.ft_release):
        files['release'] = opts.ft_release
    elif os.path.exists(''.join([def_dir, def_release])):
        files['release'] = ''.join([def_dir, def_release])
    else:
        pass
    if os.path.exists(opts.ft_schedule):
        files['schedule'] = opts.ft_schedule
    elif os.path.exists(''.join([def_dir, def_schedule])):
        files['schedule'] = ''.join([def_dir, def_schedule])
    else:
        pass    
    if os.path.exists(opts.ft_schedule2):
        files['schedule2'] = opts.ft_schedule2
    elif os.path.exists(''.join([def_dir, def_schedule2])):
        files['schedule2'] = ''.join([def_dir, def_schedule2])
    else:
        pass
    if os.path.exists(opts.ft_tick):
        files['tick'] = opts.ft_tick
    elif os.path.exists(''.join([def_dir, def_tick])):
        files['tick'] = ''.join([def_dir, def_tick])
    else:
        pass
    if os.path.exists(opts.ft_cxs):
        files['cxs'] = opts.ft_cxs
    elif os.path.exists(''.join([def_dir, def_cxs])):
        files['cxs'] = ''.join([def_dir, def_cxs])
    else:
        pass
    if os.path.exists(opts.ft_latency):
        files['latency'] = opts.ft_latency
    elif os.path.exists(''.join([def_dir, def_latency])):
        files['latency'] = ''.join([def_dir, def_latency])
    else:
        pass
    if os.path.exists(opts.ft_tree):
        files['tree'] = opts.ft_tree
    elif os.path.exists(''.join([def_dir, def_tree])):
        files['tree'] = ''.join([def_dir, def_tree])
    else:
        pass
    
    data = []
    header = []
    
    max_value = long(0)
    min_value = long(0)
    avg_value = long(0)
    std_value = long(0)
    sum_value = long(0)
    
    if files['release'] != None:
        try:
            tmp_data = []
            
            with open(files['release'], 'rb') as f:            
                csv_data = csv.reader(f)
                for row in csv_data:
                    tmp_data.append(long(row[2].strip()))
    
            if tmp_data:
                percentile = np.percentile(tmp_data, float(opts.percentile))
                filtered = [v for v in tmp_data if v <= percentile]
                max_value = long(max(filtered))
                min_value = long(min(filtered))
                avg_value = long(np.mean(filtered))
                std_value = long(np.std(filtered))
                sum_value = long(sum(filtered))
           
        except IOError:
            pass
    
    data.append(max_value)
    header.append('release_max')
    data.append(min_value)
    header.append('release_min')
    data.append(avg_value)
    header.append('release_avg')
    data.append(std_value)
    header.append('release_std')
    data.append(sum_value)
    header.append('release_sum')
    
    max_value = long(0)
    min_value = long(0)
    avg_value = long(0)
    std_value = long(0)
    sum_value = long(0)
    
    if files['schedule'] != None:
        try:
            tmp_data = []
            
            with open(files['schedule'], 'rb') as f:    
                csv_data = csv.reader(f)
                for row in csv_data:
                    tmp_data.append(long(row[2].strip()))
    
            if tmp_data:
                percentile = np.percentile(tmp_data, float(opts.percentile))
                filtered = [v for v in tmp_data if v <= percentile]
                max_value = long(max(filtered))
                min_value = long(min(filtered))
                avg_value = long(np.mean(filtered))
                std_value = long(np.std(filtered))
                sum_value = long(sum(filtered))
               
        except IOError:
            pass
    
    data.append(max_value)
    header.append('schedule_max')
    data.append(min_value)
    header.append('schedule_min')
    data.append(avg_value)
    header.append('schedule_avg')
    data.append(std_value)
    header.append('schedule_std')
    data.append(sum_value)
    header.append('schedule_sum')
    
    max_value = long(0)
    min_value = long(0)
    avg_value = long(0)
    std_value = long(0)
    sum_value = long(0)
    
    if files['schedule2'] != None:
        try:
            tmp_data = []
            
            with open(files['schedule2'], 'rb') as f:
                csv_data = csv.reader(f)
                for row in csv_data:
                    tmp_data.append(long(row[2].strip()))
    
            if tmp_data:
                percentile = np.percentile(tmp_data, float(opts.percentile))
                filtered = [v for v in tmp_data if v <= percentile]
                max_value = long(max(filtered))
                min_value = long(min(filtered))
                avg_value = long(np.mean(filtered))
                std_value = long(np.std(filtered))
                sum_value = long(sum(filtered))
    
        except IOError:
            pass
    
    data.append(max_value)
    header.append('schedule2_max')
    data.append(min_value)
    header.append('schedule2_min')
    data.append(avg_value)
    header.append('schedule2_avg')
    data.append(std_value)
    header.append('schedule2_std')
    data.append(sum_value)
    header.append('schedule2_sum')
    
    max_value = long(0)
    min_value = long(0)
    avg_value = long(0)
    std_value = long(0)
    sum_value = long(0)
    
    if files['tick'] != None:
        try:
            tmp_data = []
            
            with open(files['tick'], 'rb') as f:
                csv_data = csv.reader(f)
                for row in csv_data:
                    tmp_data.append(long(row[2].strip()))
    
            if tmp_data:
                percentile = np.percentile(tmp_data, float(opts.percentile))
                filtered = [v for v in tmp_data if v <= percentile]
                max_value = long(max(filtered))
                min_value = long(min(filtered))
                avg_value = long(np.mean(filtered))
                std_value = long(np.std(filtered))
                sum_value = long(sum(filtered))
     
        except IOError:
            pass
    
    data.append(max_value)
    header.append('tick_max')
    data.append(min_value)
    header.append('tick_min')
    data.append(avg_value)
    header.append('tick_avg')
    data.append(std_value)
    header.append('tick_std')
    data.append(sum_value)
    header.append('tick_sum')
    
    max_value = long(0)
    min_value = long(0)
    avg_value = long(0)
    std_value = long(0)
    sum_value = long(0)
    
    if files['cxs'] != None:
        try:
            tmp_data = []
            
            with open(files['cxs'], 'rb') as f:
                csv_data = csv.reader(f)
                for row in csv_data:
                    tmp_data.append(long(row[2].strip()))
    
            if tmp_data:
                percentile = np.percentile(tmp_data, float(opts.percentile))
                filtered = [v for v in tmp_data if v <= percentile]
                max_value = long(max(filtered))
                min_value = long(min(filtered))
                avg_value = long(np.mean(filtered))
                std_value = long(np.std(filtered))
                sum_value = long(sum(filtered))
     
        except IOError:
            pass
    
    data.append(max_value)
    header.append('cxs_max')
    data.append(min_value)
    header.append('cxs_min')
    data.append(avg_value)
    header.append('cxs_avg')
    data.append(std_value)
    header.append('cxs_std')
    data.append(sum_value)
    header.append('cxs_sum')
    
    max_value = long(0)
    min_value = long(0)
    avg_value = long(0)
    std_value = long(0)
    sum_value = long(0)
    
    if files['latency'] != None:
        try:
            tmp_data = []
            
            with open(files['latency'], 'rb') as f:
                csv_data = csv.reader(f)
                for row in csv_data:
                    tmp_data.append(long(row[2].strip()))
    
            if tmp_data:
                percentile = np.percentile(tmp_data, float(opts.percentile))
                filtered = [v for v in tmp_data if v <= percentile]
                max_value = long(max(filtered))
                min_value = long(min(filtered))
                avg_value = long(np.mean(filtered))
                std_value = long(np.std(filtered))
                sum_value = long(sum(filtered))
                 
        except IOError:
            pass
    
    data.append(max_value)
    header.append('latency_max')
    data.append(min_value)
    header.append('latency_min')
    data.append(avg_value)
    header.append('latency_avg')
    data.append(std_value)
    header.append('latency_std')
    data.append(sum_value)
    header.append('latency_sum')
    
    max_value = long(0)
    min_value = long(0)
    avg_value = long(0)
    std_value = long(0)
    sum_value = long(0)
    
    if files['tree'] != None:
        try:
            tmp_data = []
            
            with open(files['tree'], 'rb') as f:
                csv_data = csv.reader(f)
                for row in csv_data:
                    tmp_data.append(long(row[2].strip()))
    
            if tmp_data:
                percentile = np.percentile(tmp_data, float(opts.percentile))
                filtered = [v for v in tmp_data if v <= percentile]
                max_value = long(max(filtered))
                min_value = long(min(filtered))
                avg_value = long(np.mean(filtered))
                std_value = long(np.std(filtered))
                sum_value = long(sum(filtered))
          
        except IOError:
            pass
    
    data.append(max_value)
    header.append('tree_max')
    data.append(min_value)
    header.append('tree_min')
    data.append(avg_value)
    header.append('tree_avg')
    data.append(std_value)
    header.append('tree_std')
    data.append(sum_value)
    header.append('tree_sum')
    
    with open(''.join([def_dir, opts.out_file]), 'wb') as f:
        writer = csv.writer(f)
        #writer.writerow(header)
        writer.writerow(data)

if __name__ == '__main__':
    main()
