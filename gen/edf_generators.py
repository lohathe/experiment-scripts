import generator as gen
import random
import schedcat.model.tasks as tasks
from fractions import Fraction

TP_TBASE = """#for $t in $task_set
{} $t.cost $t.period
#end for"""
TP_GLOB_TASK = TP_TBASE.format("")
TP_PART_TASK = TP_TBASE.format("-p $t.cluster")
TP_QP_TASK = TP_TBASE.format("-p $t.cluster -S $t.set")

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

class QPTask(tasks.SporadicTask):
    def __init__(self, id=None, exec_cost, period, deadline=None, cpu=None, exec_set=0, is_master=False, client_cpu=None):
        super(QPTask, self).__init__(exec_cost, period, deadline, id)
        self.cpu = cpu
        self.exec_set = exec_set
        self.is_master = is_master
        self.client_cpu = client_cpu
    
    def utilization(self):
        return Fraction(self.cost, self.period)
    
class ExecutionSet:
    def __init__(self, cpu=None, exec_set=0, utilization=Fraction()):
        self.cpu = cpu
        self.exec_set = exec_set
        self.utilization = utilization
    
class QuasiPartitionedGenerator(EdfGenerator):
    def __init__(self, scheduler, templates, options, params):
        super(PartitionedGenerator, self).__init__(scheduler,
                                                   templates + [TP_PART_TASK], 
                                                   options, 
                                                   params)

    @staticmethod
    def decreasing_first_fit(items, bins, capacity=Fraction(1,1), weight=id, empty_bin=list):
        
        sets = [empty_bin() for _ in xrange(0, bins)]
        sums = [Fraction() for _ in xrange(0, bins)]
        
        items.sort(key=lambda x:x.utilization(), reverse=True)
        
        for x in items:
            c = weight(x)
            for i in xrange(0, bins):
                if sums[i] + c <= capacity:
                    sets[i] += [x]
                    sums[i] += c
                    break
            else:
                pass #insert here the overpack code
        return sets
    
    @staticmethod
    def overpacked(item):
        return item > Fraction(1,1)
    
    @staticmethod
    def binsSum(bins):
        sums = [Fraction() for _ in xrange(0, bins)]
        for i in xrange(0, bins):
            sums[i] = sum([x.utilization() for x in bins[i]])
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
        return qp_bin
    
    @staticmethod
    def determineExecutionSet(qp_bin, qp_sum, cpu):
        
        if qp_sum < Fraction(1,1):
            raise Exception('Invalid overpacked set')
        
        surplus = Fraction(qp_sum.numerator - qp_sum.denumerator, qp_sum.denumerator)
        a_util = sum([x.utilization() for x in qp_bin if x.set == 0]) - surplus
        b_util = Fraction(1,1) - a_util - surplus
        a_set = ExecutionSet(cpu, 0, a_util)
        b_set = ExecutionSet(cpu, 1, b_util)
        
        return [a_set, b_set]
    
    def _customize(self, taskset, exp_params):
        
        cpus  = exp_params['cpus']
        
        t_id = 0
        qp_taskset = list()
        sys_util = Fraction()
        
        for t in taskset:
            t.id = t_id
            qp_taskset.append(QPTask(t_id, t.cost, t.period, t.deadline))
            sys_util += Fraction(t.cost, t.period)
            
        
        
        bins = QuasiPartitionedGenerator.decreasing_first_fit(qp_taskset, 
                                                   cpus, 
                                                   Fraction(1,1), 
                                                   lambda x: x.utilization())
        
        sums = QuasiPartitionedGenerator.binsSum(bins)
        
        masters = list()
        tasks = list()
        exec_sets = list()
        
        j = 0 #processor allocation index 
        while(not QuasiPartitionedGenerator.terminate(sums)):
            
            qp_bins = list()
            
            for i in xrange(0, bins):
                if QuasiPartitionedGenerator.overpacked(sums[i]):
                    
                    surplus = QPTask(id=-1, 
                                     exec_cost=sums[i].numerator - sums[i].denominator, 
                                     period=sums[i].denominator, 
                                     deadline=sums[i].denominator, 
                                     is_master=True,
                                     client_cpu=j)
                    
                    qp_bins.append(surplus)
                    masters.append(surplus) #collection of all generated master
                    
                    tmp_bin = QuasiPartitionedGenerator.bipartition(QuasiPartitionedGenerator.allocate(bins[i], j), sums[i])
                    exec_sets += QuasiPartitionedGenerator.determineExecutionSet(tmp_bin, sums[i], j)
                    tasks += tmp_bin
                    
                    j += 1
                else:
                    qp_bins = qp_bins + bins[i]
            
            bins = QuasiPartitionedGenerator.decreasing_first_fit(qp_bins, 
                                           cpus - j,
                                           Fraction(1,1), 
                                           lambda x: x.utilization())

            sums = QuasiPartitionedGenerator.binsSum(bins)
        
        for b in bins:
            tmp_bin = QuasiPartitionedGenerator.allocate(b, j)
            tasks += tmp_bin
            j += 1
        
        # masters and tasks colelctions can be written to file
        
            
        
        