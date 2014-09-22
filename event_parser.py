#!/usr/bin/env python
'''
Created on 26/giu/2013

@author: davide
'''
import sys
import csv
#from symbol import except_clause

ONE_MS = 1000000

class Event(object):
    def __init__(self, id, task, job, type, time, cpu):
        self.id = id
        self.task = task
        self.job = job
        self.type = type
        self.time = time
        self.cpu = cpu

def main():
    
    cpus = len(sys.argv) - 1;
    
    if cpus < 1:
        raise Exception("No data")
    
    data = []
    for i in range(0,cpus):
        with open(sys.argv[i + 1]) as f:
            tmp1 = f.readlines()
            tmp2 = []
            for line in tmp1:
                tmp_line = line.rstrip('\n')
                if len(tmp_line) > 0:
                    tmp2.append(tmp_line)
            data.append(tmp2)
    
    keys = set(['release','switch_to','switch_away','completion'])
    
    by_cpu_events = {}
    for i in range(0,cpus):
        by_cpu_events[i] = []
        for j in xrange(0, len(data[i]), 4):
            try:
                id = int((data[i][j + 0].split(':')[1]).strip())
                tmp = (data[i][j + 1].split(':')[1]).split('.')
                task = int(tmp[0].strip())
                job = int(tmp[1].strip())
                type = (data[i][j + 2].split(':')[1]).strip()
                time = long((data[i][j + 3].split(':')[1]).strip())
                e = Event(id, task, job, type, time, i)
                if e.type in keys:
                    by_cpu_events[i].append(e)
            except:
                print 'Parsing error: event {0} on cpu {1} ignored. {2}'.format(unicode(str(id)), unicode(str(i)), unicode(sys.exc_info()[0]))
    
    for t in by_cpu_events.keys():
        by_cpu_events[t].sort(key = lambda x: x.time)
    
    by_task_events = {}
    for i in by_cpu_events.keys():
        for e in by_cpu_events[i]:
            if e.task not in by_task_events.keys():
                by_task_events[e.task] = []
            by_task_events[e.task].append(e)

    for t in by_task_events.keys():
        by_task_events[t].sort(key = lambda x: x.time)
    
    by_task_pre = dict.fromkeys(by_task_events.keys(),0)
    by_task_mig = dict.fromkeys(by_task_events.keys(),0)
    by_task_jobs = dict.fromkeys(by_task_events.keys(),0)
    by_task_miss = dict.fromkeys(by_task_events.keys(),0)
    by_task_resp_time = dict.fromkeys(by_task_events.keys(),0)
    
#     by_task_job_exec = dict.fromkeys(by_task_events.keys(),[])
#     for t in by_task_events.keys():
#         by_task_job_exec[t] = [0]*(by_task_events[t][-1].job)
#     
#     by_task_wcet = dict.fromkeys(by_task_events.keys(),0)
#     by_task_overhead_ratio = dict.fromkeys(by_task_events.keys(),Decimal(0))
    
#     for i in by_cpu_events.keys():
#         last_switch_to = None
#         for e in by_cpu_events[i]:
#             if e.type == 'switch_to':
# #                 if last_switch_to != None:
# #                     by_task_job_exec[last_switch_to.task][last_switch_to.job - 1] += (e.time - last_switch_to.time) 
#                 last_switch_to = e
#             if e.type == 'switch_away':
#                 if last_switch_to != None:
#                     if (last_switch_to.task != e.task or last_switch_to.job != e.job):
#                         raise Exception('Error on sequence')
#                     else:
#                         by_task_job_exec[last_switch_to.task][last_switch_to.job - 1] += (e.time - last_switch_to.time)
                      
                
#     for t in by_task_events.keys():
#         by_task_wcet[t] = max(by_task_job_exec[t])
#     for t in by_task_events.keys():
#         ns_to_ms = (by_task_wcet[t] / ONE_MS) * ONE_MS
#         if Decimal(ns_to_ms) > Decimal(0):
#         	by_task_overhead_ratio[t] = round((Decimal(by_task_wcet[t] - ns_to_ms) / Decimal(ns_to_ms)),3)
        
    for t in by_task_events.keys():
        
        prec_event = None
        last_rel = None
        num_of_switch_to = 1
        last_switch_to = None
        
        tmp_event = None
        
        for e in by_task_events[t]:
            
            if e.type not in keys:
                print 'Event type error'
                raise Exception('Event type error')
                
            if (prec_event != None) and (e.time <= prec_event.time):
                print 'event: duplicated [type: {0} = {1}; job {2} = {3}]'.format(prec_event.type, e.type, prec_event.job, e.job)
            else:
                if e.type == 'release':
                    
                    if (tmp_event != None) and (tmp_event.type == 'release'):
                        by_task_miss[t] += 1
                        
                    tmp_event = e
                    last_rel = e
                    
                if e.type == 'completion':
                    
                    if last_rel == None:
                        print 'event: completion {0} without release'.format(unicode(e.id))
                        #PFAIR?
                        #raise Exception('Completion and last_rel == None')
                    else:
                        if (e.job < last_rel.job) or ((tmp_event != None) and (tmp_event.type == 'completion')):
                            by_task_miss[t] += 1
                            print 'event: miss, task: {0}, time: {1}'.format(unicode(e.task),unicode(e.time))
                        else:
                            rt = e.time - last_rel.time
                            if by_task_resp_time[t] < rt:
                                by_task_resp_time[t] = rt
                                
                        tmp_event = e
        #                 if e.job < last_rel.job:
        #                     print 'WARNING: Completion whithout release'
        #                     raise Exception('Completion whithout release')
                        
        #                 if e.job < last_rel.job:
        #                     by_task_miss[t] += 1
        
                    by_task_jobs[t] += 1
                    
                if e.type == 'switch_to':
                    
                    if (last_switch_to != None) and (last_switch_to.job > e.job):
                        print 'Switch_to out of order'
                        raise Exception('Switch_to out of order')
                    
                    if (last_switch_to == None) or (last_switch_to.job < e.job):
                        num_of_switch_to = 1
                    else:
                        num_of_switch_to += 1
                        
                    if num_of_switch_to > 1:
                        by_task_pre[t] += 1
                        if last_switch_to.cpu != e.cpu:
                            by_task_mig[t] += 1
                            #print 'event: migration, task: {0}, time: {1}'.format(unicode(e.task),unicode(e.time))
                    
                    last_switch_to = e
                
                prec_event = e
                            
    out_data = dict.fromkeys(by_task_events.keys(),[])
    for t in by_task_events.keys():
        out_data[t] = [by_task_jobs[t], by_task_pre[t], by_task_mig[t], by_task_miss[t], by_task_resp_time[t]]
    
    with open('out_stat.csv', 'wb') as f:
        writer = csv.writer(f)
        for key, value in out_data.items():
            writer.writerow([key, value[0], value[1], value[2], value[3], value[4]])
    
    jobs_tot = 0
    mig_tot = 0
    pre_tot = 0
    miss_tot = 0
    for t in by_task_events.keys():
        jobs_tot += by_task_jobs[t]
        mig_tot += by_task_mig[t]
        pre_tot += by_task_pre[t]
        miss_tot += by_task_miss[t]
        
    print "-------------------------------------------------------"
    print "jobs: "+ str(jobs_tot) + ", preempt: " + str(pre_tot) + ", migrat: " + str(mig_tot) + ", miss: " + str(miss_tot)
    
    with open('out_stat_tot.csv', 'wb') as f:
        writer = csv.writer(f)
        writer.writerow([jobs_tot, pre_tot, mig_tot, miss_tot])
    
    if (jobs_tot > 0):
        avg_pre = float(pre_tot) / jobs_tot
        avg_mig = float(mig_tot) / jobs_tot
        avg_miss = float(miss_tot) / jobs_tot
        
        avg_pre = round(avg_pre,8)
        avg_mig = round(avg_mig,8)
        avg_miss = round(avg_miss,8)
    
        with open('out_stat_avg.csv', 'wb') as f:
            writer = csv.writer(f)
            writer.writerow([jobs_tot, avg_pre, avg_mig, avg_miss])

#     with open('out_pre.csv', 'wb') as file:
#         writer = csv.writer(file)
#         for key, value in by_task_pre.items():
#             writer.writerow([key, value])
#             
#     with open('out_migs.csv', 'wb') as file:
#         writer = csv.writer(file)
#         for key, value in by_task_mig.items():
#             writer.writerow([key, value])
#             
#     with open('out_jobs.csv', 'wb') as file:
#         writer = csv.writer(file)
#         for key, value in by_task_jobs.items():
#             writer.writerow([key, value])
    
    #Parsing           
    #reader = csv.reader(open('dict.csv', 'rb'))
    #mydict = dict(x for x in reader)


if __name__ == '__main__':
    main()
