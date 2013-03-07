import generator as gen
import random
import schedcat.generator.tasks as tasks

class EdfGenerator(gen.Generator):
    '''Creates sporadic task sets with the most common Litmus options.'''
    def __init__(self, name, templates, options, params):
        super(EdfGenerator, self).__init__(name, templates,
                                           self.__make_options(params) + options,
                                           params)

    def __make_options(self, params):
        '''Return generic EDF options.'''
        return [gen.Generator._dist_option('utils', ['uni-medium'],
                                           gen.NAMED_UTILIZATIONS,
                                           'Task utilization distributions.'),
                gen.Generator._dist_option('periods', ['harmonic'],
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
        tg = tasks.TaskGenerator(period=pdist, util=udist)

        ts = []
        tries = 0
        while len(ts) != exp_params['num_tasks'] and tries < 5:
            ts = tg.make_task_set(max_tasks = exp_params['num_tasks'])
            tries += 1
        if len(ts) != exp_params['num_tasks']:
            print("Failed to create task set with parameters: %s" % exp_params)

        self._customize(ts, exp_params)

        exp_params['task_set'] = ts
        self._write_schedule(exp_params)

        del exp_params['task_set']
        del exp_params['num_tasks']
        self._write_params(exp_params)

    def _customize(self, taskset, exp_params):
        '''Configure a generated taskset with extra parameters.'''
        pass


class PartitionedGenerator(EdfGenerator):
    def __init__(self, name, templates, options, params):
        super(PartitionedGenerator, self).__init__(name,
            templates + [gen.TP_PART_TASK], options, params)

    def _customize(self, taskset, exp_params):
        start = 1 if exp_params['release_master'] else 0
        # Random partition for now: could do a smart partitioning
        for t in taskset:
            t.cpu = random.randint(start, exp_params['cpus'] - 1)

class PedfGenerator(PartitionedGenerator):
    def __init__(self, params={}):
        super(PedfGenerator, self).__init__("PSN-EDF", [], [], params)

class CedfGenerator(PartitionedGenerator):
    TP_CLUSTER = "plugins/C-EDF/cluster{$level}"
    CLUSTER_OPTION = gen.GenOption('level', ['L2', 'L3', 'All'], ['L2'],
                                   'Cache clustering level.',)

    def __init__(self, params={}):
        super(CedfGenerator, self).__init__("C-EDF",
                                            [CedfGenerator.TP_CLUSTER],
                                            [CedfGenerator.CLUSTER_OPTION],
                                            params)

class GedfGenerator(EdfGenerator):
    def __init__(self, params={}):
        super(GedfGenerator, self).__init__("GSN-EDF", [gen.TP_GLOB_TASK],
                                            [], params)
