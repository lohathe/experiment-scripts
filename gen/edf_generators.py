import generator as gen
import random
import schedcat.model.tasks as tasks
import csv
from fractions import Fraction
from decimal import Decimal
from config.config import FILES

TP_TBASE = """#for $t in $task_set
{} $t.cost $t.period
#end for"""
TP_GLOB_TASK = TP_TBASE.format("")
TP_PART_TASK = TP_TBASE.format("-p $t.cluster")
TP_QP_TASK = TP_TBASE.format("-p $t.cpu -S $t.set")

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

        ts = self._create_taskset(exp_params, pdist, udist)

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
        clusters  = exp_params['clusters']

        utils = [0]*clusters
        tasks = [0]*clusters

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
def utilization(t):
    return Fraction(t.cost, t.period)

def taskToList(t):
    return [t.cpu, t.set, t.client_cpu, t.cost, t.period]

#class QPTask(tasks.SporadicTask):
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
    def decreasing_first_fit(items, bins, capacity=Fraction(1,1), weight=id, empty_bin=list):
        
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
                #overpacking code
                candidates = [Fraction(1,1) - s for s in sums]
                i = candidates.index(max(candidates))
                sets[i] += [x]
                sums[i] += c
                print 'Overpacking bin {0}'.format(i) #insert here the overpack code
                
        return sets
    
    @staticmethod
    def overpacked(item):
        return item > Fraction(1,1)
    
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
        
        split_util = qp_sum * Fraction(1,2)
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
        
        if qp_sum > Fraction(1,1):
            surplus = Fraction(qp_sum.numerator - qp_sum.denominator, qp_sum.denominator)
            a_util = sum([utilization(x) for x in qp_bin if x.set == 0]) - surplus
            b_util = Fraction(1,1) - a_util - surplus
            a_set = ExecutionSet(cpu, 0, a_util)
            b_set = ExecutionSet(cpu, 1, b_util)
        else:
            a_set = ExecutionSet(cpu, 0, Fraction(1,1))
            b_set = ExecutionSet(cpu, 1, Fraction(0,1))
        return [a_set, b_set]
    
    def _customize(self, taskset, exp_params):
        
        cpus  = exp_params['cpus']
        #cpus = 3
        #taskset = [tasks.SporadicTask(3,4), tasks.SporadicTask(3,4), tasks.SporadicTask(3,4), tasks.SporadicTask(3,4)]
        
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
                                                   Fraction(1,1), 
                                                   lambda x: utilization(x))
        
        sums = QuasiPartitionedGenerator.binsSum(bins, len(bins))
        
        masters = list()
        exec_sets = list()
        
        j = 0 #processor allocation index 
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
                    masters.append(surplus) #collection of all generated master
                    
                    tmp_bin = QuasiPartitionedGenerator.bipartition(QuasiPartitionedGenerator.allocate(bins[i], j), sums[i])
                    exec_sets += QuasiPartitionedGenerator.determineExecutionSet(tmp_bin, sums[i], j)
                    
                    t_id += 1
                    j += 1
                    
            for i in xrange(0, len(bins)):
                if not QuasiPartitionedGenerator.overpacked(sums[i]):
                    qp_bins = qp_bins + bins[i]
            
            bins = QuasiPartitionedGenerator.decreasing_first_fit(qp_bins, 
                                           cpus - j,
                                           Fraction(1,1), 
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