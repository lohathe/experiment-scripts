import generator as gen
import random
import schedcat.model.tasks as tasks
import csv
import json
import math
from fractions import Fraction
from decimal import Decimal
from config.config import FILES

TP_TBASE = """#for $t in $task_set
{} $t.cost $t.period
#end for"""
TP_GLOB_TASK = TP_TBASE.format("")
TP_PART_TASK = TP_TBASE.format("-p $t.cluster")
TP_QP_TASK = TP_TBASE.format("-p $t.cpu -S $t.set")
TP_RUN_TASK = TP_TBASE.format("-S $t.server")

def utilization(t):
    return Fraction(t.cost, t.period)

class EdfGenerator(gen.Generator):
    '''Creates sporadic task sets with the most common Litmus options.'''
    def __init__(self, scheduler, templates, options, params):
        super(EdfGenerator, self).__init__(scheduler, templates,
                                           self.__make_options() + options,
                                           params)

    def __make_options(self):
        '''Return generic EDF options.'''
        return [gen.Generator._dist_option('utils', 'uni-medium',
                                           gen.NAMED_UTILIZATIONS,
                                           'Task utilization distributions.'),
                gen.Generator._dist_option('periods', 'harmonic',
                                           gen.NAMED_PERIODS,
                                           'Task period distributions.')]

    def _create_exp(self, exp_params):
        '''Create a single experiment with @exp_params in @out_dir.'''
        pdist = self._create_dist('period',
                                  exp_params['periods'],
                                  gen.NAMED_PERIODS)

        udist = self._create_dist('utilization',
                                  exp_params['utils'],
                                  gen.NAMED_UTILIZATIONS)
        
        ts = self._create_taskset(exp_params, pdist, udist, exp_params['mutils'])
        
        exp_params['autils'] = float(sum([utilization(t) for t in ts]))
        
        self._customize(ts, exp_params)

        self._write_schedule(dict(exp_params.items() + [('task_set', ts)]))
        self._write_params(exp_params)

    def _customize(self, taskset, exp_params):
        '''Configure a generated taskset with extra parameters.'''
        pass


class PartitionedGenerator(EdfGenerator):
    def __init__(self, scheduler, templates, options, params):
        super(PartitionedGenerator, self).__init__(scheduler,
            templates + [TP_PART_TASK], options, params)

    def _customize(self, taskset, exp_params):
        clusters = exp_params['clusters']

        utils = [0] * clusters
        tasks = [0] * clusters

        if exp_params['release_master'] and clusters != exp_params['cpus']:
            # The first cluster is one CPU smaller to accomodate the
            # release master. Increase the first cluster's utilization
            # to account for this.
            utils[0] += 1

        # Partition using worst-fit for most even distribution
        for t in taskset:
            t.cluster = utils.index(min(utils))
            utils[t.cluster] += t.utilization()
            tasks[t.cluster] += 1

class PedfGenerator(PartitionedGenerator):
    def __init__(self, params={}):
        super(PedfGenerator, self).__init__("PSN-EDF", [], [], params)

class CedfGenerator(PartitionedGenerator):
    TP_CLUSTER = "plugins/C-EDF/cluster{$level}"
    CLUSTER_OPTION = gen.GenOption('level', ['L1', 'L2', 'L3', 'All'], 'L2',
                                   'Cache clustering level.',)

    def __init__(self, params={}):
        super(CedfGenerator, self).__init__("C-EDF",
                                            [CedfGenerator.TP_CLUSTER],
                                            [CedfGenerator.CLUSTER_OPTION],
                                            params)

class GedfGenerator(EdfGenerator):
    def __init__(self, params={}):
        super(GedfGenerator, self).__init__("GSN-EDF", [TP_GLOB_TASK],
                                            [], params)

########## QPS offline functions ##########
def taskToList(t):
    return [t.cpu, t.set, t.client_cpu, t.cost, t.period]

# class QPTask(tasks.SporadicTask):
#    
#    def __init__(self, id=None, exec_cost=None, period=None, deadline=None, cpu=None, exec_set=0, is_master=False, client_cpu=None):
#        super(QPTask, self).__init__(exec_cost, period, deadline, id)
#        self.cpu = cpu
#        self.exec_set = exec_set
#        self.is_master = is_master
#        self.client_cpu = client_cpu
#    
#    def utilization(self):
#        return Fraction(self.cost, self.period)
#    
#    def toList(self):
#        return [self.cpu, self.exec_set, self.client_cpu, self.exec_cost, self.period]

class ExecutionSet:
    
    def __init__(self, cpu=None, exec_set=0, utilization=Fraction()):
        self.cpu = cpu
        self.set = exec_set
        self.utilization = utilization
    
    def toList(self):
        return [self.cpu, self.set, self.utilization.numerator, self.utilization.denominator]
    
class QuasiPartitionedGenerator(EdfGenerator):
    def __init__(self, scheduler, templates, options, params):
        super(QuasiPartitionedGenerator, self).__init__(scheduler,
                                                   templates + [TP_QP_TASK],
                                                   options,
                                                   params)

    @staticmethod
    def decreasing_first_fit(items, bins, capacity=Fraction(1, 1), weight=id, empty_bin=list):
        
        sets = [empty_bin() for _ in xrange(0, bins)]
        sums = [Fraction() for _ in xrange(0, bins)]
        
        items.sort(key=weight, reverse=True)
        
        for x in items:
            c = weight(x)
            for i in xrange(0, bins):
                if sums[i] + c <= capacity:
                    sets[i] += [x]
                    sums[i] += c
                    break
            else:
                # overpacking code
                candidates = [Fraction(1, 1) - s for s in sums]
                i = candidates.index(max(candidates))
                sets[i] += [x]
                sums[i] += c
                print 'Overpacking bin {0}'.format(i)  # insert here the overpack code
                
        return sets
    
    @staticmethod
    def overpacked(item):
        return item > Fraction(1, 1)
    
    @staticmethod
    def binsSum(bins, elements):
        sums = [Fraction() for _ in xrange(0, elements)]
        for i in xrange(0, elements):
            sums[i] = sum([utilization(x) for x in bins[i]])
        return sums
    
    @staticmethod
    def terminate(sums):
        for s in sums:
            if QuasiPartitionedGenerator.overpacked(s):
                return False
        return True
    
    @staticmethod
    def allocate(qp_bin, cpu):
        for t in qp_bin:
            t.cpu = cpu
        return qp_bin
    
    @staticmethod
    def bipartition(qp_bin, qp_sum):
        
        split_util = qp_sum * Fraction(1, 2)
        tmp_util = Fraction()
        
        for t in qp_bin:
            
            if tmp_util < split_util:
                t.set = 0
            else:
                t.set = 1
                
            tmp_util += utilization(t)
            
        return qp_bin
    
    @staticmethod
    def determineExecutionSet(qp_bin, qp_sum, cpu):
        
        if qp_sum > Fraction(1, 1):
            surplus = Fraction(qp_sum.numerator - qp_sum.denominator, qp_sum.denominator)
            a_util = sum([utilization(x) for x in qp_bin if x.set == 0]) - surplus
            b_util = Fraction(1, 1) - a_util - surplus
            a_set = ExecutionSet(cpu, 0, a_util)
            b_set = ExecutionSet(cpu, 1, b_util)
        else:
            a_set = ExecutionSet(cpu, 0, Fraction(1, 1))
            b_set = ExecutionSet(cpu, 1, Fraction(0, 1))
        return [a_set, b_set]
    
    def _customize(self, taskset, exp_params):
        
        cpus = exp_params['cpus']
        
        # EXAMPLE
        # cpus = 3
        # taskset = [tasks.SporadicTask(3,4), 
        #            tasks.SporadicTask(3,4), 
        #            tasks.SporadicTask(3,4), 
        #            tasks.SporadicTask(3,4)]
        
        t_id = 0
        sys_util = Fraction()
        
        for t in taskset:
            t.id = t_id
            t.cpu = None
            t.set = 0
            t.is_master = False
            sys_util += utilization(t)
            t_id += 1
        
        print 'System utilization: {0}'.format(Decimal(sys_util.numerator) / Decimal(sys_util.denominator))
        
        bins = QuasiPartitionedGenerator.decreasing_first_fit(taskset,
                                                   cpus,
                                                   Fraction(1, 1),
                                                   lambda x: utilization(x))
        
        sums = QuasiPartitionedGenerator.binsSum(bins, len(bins))
        
        masters = list()
        exec_sets = list()
        
        j = 0  # processor allocation index 
        while(not QuasiPartitionedGenerator.terminate(sums)):
            
            qp_bins = list()
            
            for i in xrange(0, len(bins)):
                if QuasiPartitionedGenerator.overpacked(sums[i]):
                    
                    surplus = tasks.SporadicTask(id=t_id,
                                                 exec_cost=sums[i].numerator - sums[i].denominator,
                                                 period=sums[i].denominator,
                                                 deadline=sums[i].denominator) 
                    surplus.is_master = True
                    surplus.set = 0
                    surplus.client_cpu = j
                    
                    qp_bins.append(surplus)
                    masters.append(surplus)  # collection of all generated master
                    
                    tmp_bin = QuasiPartitionedGenerator.bipartition(QuasiPartitionedGenerator.allocate(bins[i], j), sums[i])
                    exec_sets += QuasiPartitionedGenerator.determineExecutionSet(tmp_bin, sums[i], j)
                    
                    t_id += 1
                    j += 1
                    
            for i in xrange(0, len(bins)):
                if not QuasiPartitionedGenerator.overpacked(sums[i]):
                    qp_bins = qp_bins + bins[i]
            
            bins = QuasiPartitionedGenerator.decreasing_first_fit(qp_bins,
                                           cpus - j,
                                           Fraction(1, 1),
                                           lambda x: utilization(x))

            sums = QuasiPartitionedGenerator.binsSum(bins, len(bins))
        
        for i in xrange(0, len(bins)):
            tmp_bin = QuasiPartitionedGenerator.allocate(bins[i], j)
            exec_sets += QuasiPartitionedGenerator.determineExecutionSet(tmp_bin, sums[i], j)
            j += 1
                    
        # masters, tasks and exec_sets are now completed and can be written to file
        masters_file = self.out_dir + "/" + FILES['masters_file']
        with open(masters_file, 'wa') as f:
            csvwriter = csv.writer(f, delimiter=' ')
            for m in masters:
                if m.is_master == False:
                    raise Exception("Not master detected")
                csvwriter.writerow(taskToList(m))
            
        sets_file = self.out_dir + "/" + FILES['sets_file']
        with open(sets_file, 'wa') as f:
            csvwriter = csv.writer(f, delimiter=' ')
            for s in exec_sets:
                csvwriter.writerow(s.toList())
        
class QPSGenerator(QuasiPartitionedGenerator):
    def __init__(self, params={}):
        super(QPSGenerator, self).__init__("QPS", [], [], params)

# RUN generator

def ignore(_):
    pass

class FixedRateTask(tasks.SporadicTask):
    
    def __init__(self, exec_cost, period, deadline=None, id=None, server=None, level=-1):
        super(FixedRateTask, self).__init__(exec_cost, period, deadline, id)
        self.server = server
        self.level = level
        self.children = []
        self.parent = None
        
    def dual_utilization(self):
        return Decimal(1) - self.utilization()
    
    def dual_util_frac(self):
        return Fraction(self.period - self.cost, self.period)
    
    def utilization(self):
        return Decimal(self.cost) / Decimal(self.period)
    
    def util_frac(self):
        return Fraction(self.cost, self.period)
    
    def get_children(self):
        return self.children
    
    @staticmethod
    def _aggregate(task_list, server, level):
        
        tot_util = Fraction()
        for t in task_list:
            tot_util += t.util_frac()
        new_task = FixedRateTask(tot_util.numerator,
                                 tot_util.denominator,
                                 tot_util.denominator,
                                 server,
                                 None,
                                 level)
        
        for t in task_list:
            t.parent = new_task
            t.server = server
            new_task.children.append(t)
        return new_task
    
    @staticmethod
    def serialize(task):
        obj = {
            'id': task.id,
            'cost': task.cost,
            'period': task.period,
            'level' : task.level,
            'children': []
        }
        if (task.level > 0):
            for ch in task.get_children():
                obj['children'].append(FixedRateTask.serialize(ch))
            
        return obj

class RUNGenerator(EdfGenerator):
    def __init__(self, params={}):
        super(RUNGenerator, self).__init__("RUN",
            [TP_RUN_TASK], [], params)
        self.server_count = 0
    
    def _customize(self, taskset, exp_params):
        cpus = exp_params['cpus']
        self.server_count = 0
        slack_dist = False
        if 'slack_dist' in exp_params:
            slack_dist = True if (exp_params['slack_dist'] == 'tasks') else False
        data = self._reductor(taskset, cpus, slack_dist)
        tree_file = self.out_dir + "/tree.json"
        with open(tree_file, 'wa') as f:
            json.dump(data, f, indent=4)
            
    def _reductor(self, taskset, cpus, slack_dist):
        
        # First create fixed-rates        
        n_tasks = len(taskset)
        # On heavy task case #tasks may be less than #cpus
        if (n_tasks < cpus):
            print 'attention: #cpus has changed from {0} to {1}'.format(unicode(cpus), unicode(n_tasks))
            cpus = n_tasks
            
        t_id = 0
        fr_taskset = []
        tot_util = Fraction()
        
        for t in taskset:
            t.id = t_id
            fr_taskset.append(FixedRateTask(t.cost, t.period, t.deadline, t_id))
            t_id += 1
            tot_util += Fraction(t.cost, t.period)
        # Second distribuites unused cpu capacity (slack-pack)
        print 'Total utilization: {0}'.format(Decimal(tot_util.numerator) / Decimal(tot_util.denominator))
        
        unused_capacity = Fraction(cpus, 1) - tot_util
        if (unused_capacity < Fraction()):
            raise Exception('Unfeasible Taskset')
        
        if (slack_dist):
            fr_taskset.sort(key=lambda x: x.util_frac(), reverse=True)
            self._distribuite_slack(fr_taskset, unused_capacity)
            new_taskset = self._pack(fr_taskset, cpus, 0)
            self._dual(new_taskset)
        else:
            new_taskset = self._pack(fr_taskset, cpus, 0)
            new_taskset.sort(key=lambda x: x.utilization(), reverse=True)
            self._distribuite_slack(new_taskset, unused_capacity)
            self._dual(new_taskset)
        
        unit_server = self._reduce(new_taskset, 1)
        
        if (len(unit_server) != 1):
            raise Exception('Not a Unit-Server')
        
        if (unit_server[0].util_frac() != Fraction() and not(unit_server[0].util_frac().numerator == unit_server[0].util_frac().denominator)):
            raise Exception('Not a Unit-Server')
        
        if (unit_server[0].util_frac().numerator == 1):
            print 'Root level: {0}'.format(unicode(unit_server[0].level - 1))
        else: 
            print 'Root level: {0}'.format(unicode(unit_server[0].level))
            
        for t in taskset:
            for fr_t in fr_taskset:
                if (fr_t.id == t.id):
                    t.server = fr_t.server
                    
        return FixedRateTask.serialize(unit_server[0])
    
    def _slack_dist(self, ts, slack):
        
        n_tasks = len(ts)
        val_a = ts[0].dual_utilization()
        val_b = slack / Decimal(n_tasks)
        
        unused_capacity = slack
        
        task_extra_util = min(val_a, val_b)
        for t in ts:
            if (t.dual_utilization() <= task_extra_util):
                unused_capacity -= t.dual_utilization()
                t.cost = t.period
            else:
                tmp_util = t.utilization()
                t.cost += int(task_extra_util * Decimal(t.period))
                unused_capacity -= (t.utilization() - tmp_util)
        
        tries = 10
        while (unused_capacity > Decimal(0)) and (tries > 0):
            for t in ts:
                tmp_value = unused_capacity * Decimal(t.period)
                if (t.dual_utilization() >= unused_capacity) and tmp_value == int(tmp_value):
                    t.cost += int(tmp_value)
                    unused_capacity = Decimal(0)
                    break
            if (unused_capacity > Decimal(0)):
                for t in ts:
                    if (t.dual_utilization() <= unused_capacity):
                        unused_capacity -= t.dual_utilization()
                        t.cost = t.period
            tries -= 1
            
        if (unused_capacity > Decimal(0)):
            raise Exception('Still capacity unused: ' + str(unused_capacity))
    
    def _distribuite_slack(self, ts, slack):
        ts.sort(key=lambda x: x.util_frac(), reverse=True)
        i = 0
        unused_capacity = slack        
        while (unused_capacity > Fraction()) and (i < len(ts)):
            t = ts[i]
            if (t.dual_util_frac() <= unused_capacity):
                unused_capacity -= t.dual_util_frac()
                t.cost = t.period
            else:
                tmp_frac = t.util_frac() + unused_capacity
                t.cost = tmp_frac.numerator
                t.period = tmp_frac.denominator
                unused_capacity = Fraction()
            i += 1            
        if (unused_capacity > Fraction()):
            raise Exception('Still capacity unused: ' + str(unused_capacity))
        
    def _dual(self, taskset):
        for t in taskset:
            t.cost = t.period - t.cost
        
    def _pack(self, taskset, cpus, level):
        self.misfit = 0
        n_bins = cpus
        
        taskset.sort(key=lambda x: x.util_frac(), reverse=True)
        
        bins = RUNGenerator.worst_fit(taskset,
                                      n_bins,
                                      Fraction(1, 1),
                                      lambda x: x.util_frac(),
                                      self._misfit)
        while (self.misfit > 0):
            # n_bins += math.ceil(self.misfit)
            n_bins += 1  # self.misfit
            self.misfit = 0
            bins = RUNGenerator.worst_fit(taskset,
                                          n_bins,
                                          Fraction(1, 1),
                                          lambda x: x.util_frac(),
                                          self._misfit)    
        servers = []
        for item in bins:
            tmp_server = FixedRateTask._aggregate(item, self.server_count, level)
            servers.append(tmp_server)
            self.server_count += 1
        
        self.misfit = 0
        return servers
        
    def _misfit(self, x):
        # self.misfit += x.dual_utilization()
        self.misfit += 1
           
    def _reduce(self, taskset, level):
        utilization = Fraction()
        for t in taskset:
            utilization += t.util_frac()
        
        new_taskset = self._pack(taskset,
                                 int(math.ceil(utilization)),
                                 level)
        self._dual(new_taskset)
        
        if (utilization <= Fraction(1, 1)):
            return new_taskset
        else:
            return self._reduce(new_taskset, level + 1)
    
    @staticmethod
    def worst_fit(items, bins, capacity=Fraction(1, 1), weight=id, misfit=ignore, empty_bin=list):
        sets = [empty_bin() for _ in xrange(0, bins)]
        sums = [Fraction() for _ in xrange(0, bins)]
        for x in items:
            c = weight(x)
            # pick the bin where the item will leave the most space
            # after placing it, aka the bin with the least sum
            candidates = [s for s in sums if s + c <= capacity]
            if candidates:
                # fits somewhere
                i = sums.index(min(candidates))
                sets[i] += [x]
                sums[i] += c
            else:
                misfit(x)
        return sets
