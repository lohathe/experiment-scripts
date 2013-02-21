from Cheetah.Template import Template
from collections import namedtuple
from common import get_config_option
from config.config import DEFAULTS
from gen.dp import DesignPointGenerator
from parse.col_map import ColMapBuilder

import gen.rv as rv
import os
import random
import run.litmus_util as lu
import schedcat.generator.tasks as tasks
import shutil as sh

NAMED_PERIODS = {
    'harmonic'            : rv.uniform_choice([25, 50, 100, 200]),
    'uni-short'           : rv.uniform_int( 3,  33),
    'uni-moderate'        : rv.uniform_int(10, 100),
    'uni-long'            : rv.uniform_int(50, 250),
}

NAMED_UTILIZATIONS = {
    'uni-very-light': rv.uniform(0.0001, 0.001),
    'uni-light'     : rv.uniform(0.001, 0.1),
    'uni-medium'    : rv.uniform(  0.1, 0.4),
    'uni-heavy'     : rv.uniform(  0.5, 0.9),

    'exp-light'     : rv.exponential(0, 1, 0.10),
    'exp-medium'    : rv.exponential(0, 1, 0.25),
    'exp-heavy'     : rv.exponential(0, 1, 0.50),

    'bimo-light'    : rv.multimodal([(rv.uniform(0.001, 0.5), 8),
                                     (rv.uniform(  0.5, 0.9), 1)]),
    'bimo-medium'   : rv.multimodal([(rv.uniform(0.001, 0.5), 6),
                                     (rv.uniform(  0.5, 0.9), 3)]),
    'bimo-heavy'    : rv.multimodal([(rv.uniform(0.001, 0.5), 4),
                                     (rv.uniform(  0.5, 0.9), 5)]),
}

# Cheetah templates for schedule files
TP_CLUSTER = "plugins/C-EDF/cluster{$level}"
TP_RM = """#if $release_master
release_master{1}
#end if"""
TP_TBASE = """#for $t in $task_set
{}$t.cost $t.period
#end for"""
TP_PART_TASK = TP_TBASE.format("-p $t.cpu ")
TP_GLOB_TASK = TP_TBASE.format("")

GenOption = namedtuple('GenOption', ['name', 'types', 'default', 'help'])

class BaseGenerator(object):
    '''Creates sporadic task sets with the most common Litmus options.'''
    def __init__(self, name, templates, options, params):
        self.options = self.__make_options(params) + options

        self.__setup_params(params)

        self.params   = params
        self.template = "\n".join([TP_RM] + templates)
        self.name     = name

    def __make_options(self, params):
        '''Return generic Litmus options.'''

        # Guess defaults using the properties of this computer
        if 'cpus' in params:
            cpus = min(map(int, params['cpus']))
        else:
            cpus = lu.num_cpus()
        try:
            config = get_config_option("RELEASE_MASTER") and True
        except:
            config = False
        release_master = list(set([False, config]))

        list_types = [str, float, type([])]

        return [GenOption('cpus', int, [cpus],
                          'Number of processors on target system.'),
                GenOption('num_tasks', int, range(cpus, 5*cpus, cpus),
                          'Number of tasks per experiment.'),
                GenOption('utils', list_types + NAMED_UTILIZATIONS.keys(),
                          ['uni-medium'],'Task utilization distributions.'),
                GenOption('periods', list_types + NAMED_PERIODS.keys(),
                          ['harmonic'], 'Task period distributions.'),
                GenOption('release_master', [True,False], release_master,
                          'Redirect release interrupts to a single CPU.'),
                GenOption('duration', float, [30], 'Experiment duration.')]

    def __create_dist(self, name, value, named_dists):
        '''Attempt to create a distribution representing the data in @value.
        If @value is a string, use it as a key for @named_dists.'''
        name = "%s distribution" % name
        # A list of values
        if type(value) == type([]):
            map(lambda x : self.__check_value(name, x, [float, int]), value)
            return rv.uniform_choice(value)
        elif type(value) in [float, int]:
            return lambda : value
        elif value in named_dists:
            return named_dists[value]
        else:
            raise ValueError("Invalid %s value: %s" % (name, value))

    def __create_exp(self, exp_params, out_dir):
        '''Create a single experiment with @exp_params in @out_dir.'''
        pdist = self.__create_dist('period',
                                   exp_params['periods'],
                                   NAMED_PERIODS)
        udist = self.__create_dist('utilization',
                                   exp_params['utils'],
                                   NAMED_UTILIZATIONS)
        tg = tasks.TaskGenerator(period=pdist, util=udist)

        ts = []
        tries = 0
        while len(ts) != exp_params['num_tasks'] and tries < 5:
            ts = tg.make_task_set(max_tasks = exp_params['num_tasks'])
            tries += 1
        if len(ts) != exp_params['num_tasks']:
            print("Failed to create task set with parameters: %s" % exp_params)

        self._customize(ts, exp_params)

        sched_file = out_dir + "/" + DEFAULTS['sched_file']
        with open(sched_file, 'wa') as f:
            exp_params['task_set'] = ts
            f.write(str(Template(self.template, searchList=[exp_params])))

        del exp_params['task_set']
        del exp_params['num_tasks']
        exp_params_file = out_dir + "/" + DEFAULTS['params_file']
        with open(exp_params_file, 'wa') as f:
            exp_params['scheduler'] = self.name
            f.write(str(exp_params))

    def __setup_params(self, params):
        '''Set default parameter values and check that values are valid.'''
        for option in self.options:
            if option.name not in params:
                params[option.name] = option.default
            params[option.name] = self._check_value(option.name,
                                                    option.types,
                                                    params[option.name])
        return params


    def _check_value(self, name, types, val):
        '''Raise an exception if the value of type of @val is not specified
        in @types. Returns a copy of @val with strings converted to raw
        Python types, if possible.'''
        if types == float:
            types = [float, int]
        if type(types) != type([]):
            types = [types]
        if type(val) != type([]):
            val = [val]

        retval = []
        for v in val:
            # Has to be a better way to find this
            v = False if v in ['f', 'False', 'false', 'n', 'no']  else v
            v = True  if v in ['t', 'True',  'true',  'y', 'yes'] else v

            if type(v) not in types and v not in types:
                # Try and convert v to one of the specified types
                parsed = None
                for t in types:
                    try:
                        parsed = t(v)
                        break
                    except:
                        pass

                if parsed:
                    retval += [parsed]
                else:
                    raise TypeError("Invalid %s value: '%s'" % (name, v))
            else:
                retval += [v]
        return retval

    def _customize(self, taskset, exp_params):
        '''Configure a generated taskset with extra parameters.'''
        pass

    def create_exps(self, out_dir, force):
        '''Create experiments for all possible combinations of params in
        @out_dir. Overwrite existing files if @force is True.'''
        builder = ColMapBuilder()

        # Track changing values so only relevant parameters are included
        # in directory names
        for dp in DesignPointGenerator(self.params):
            for k, v in dp.iteritems():
                builder.try_add(k, v)
        col_map = builder.build()

        for dp in DesignPointGenerator(self.params):
            dir_leaf = "sched=%s_%s" % (self.name, col_map.encode(dp))
            dir_path = "%s/%s" % (out_dir, dir_leaf.strip('_'))

            if os.path.exists(dir_path):
                if force:
                    sh.rmtree(dir_path)
                else:
                    print("Skipping existing experiment: '%s'" % dir_path)
                    continue

            os.mkdir(dir_path)

            self.__create_exp(dp, dir_path)

    def print_help(self):
        s = str(Template("""Generator $name:
        #for $o in $options
        $o.name -- $o.help
        \tDefault: $o.default
        \tAllowed: $o.types
        #end for""", searchList=vars(self)))

        # Has to be an easier way to print this out...
        for line in s.split("\n"):
            res = []
            i = 0
            for word in line.split(", "):
                i+= len(word)
                res += [word]
                if i > 80:
                    print(", ".join(res[:-1]))
                    res = ["\t\t "+res[-1]]
                    i = line.index("'")
            print(", ".join(res))

class PartitionedGenerator(BaseGenerator):
    def __init__(self, name, templates, options, params):
        super(PartitionedGenerator, self).__init__(name,
            templates + [TP_PART_TASK], options, params)

    def _customize(self, taskset, exp_params):
        start = 1 if exp_params['release_master'] else 0
        # Random partition for now: could do a smart partitioning
        for t in taskset:
            t.cpu = random.randint(start, exp_params['cpus'] - 1)

class PedfGenerator(PartitionedGenerator):
    def __init__(self, params={}):
        super(PedfGenerator, self).__init__("PSN-EDF", [], [], params)

class CedfGenerator(PartitionedGenerator):
    LEVEL_OPTION = GenOption('level', ['L2', 'L3', 'All'], ['L2'],
                             'Cache clustering level.',)

    def __init__(self, params={}):
        super(CedfGenerator, self).__init__("C-EDF", [TP_CLUSTER],
            [CedfGenerator.LEVEL_OPTION], params)

class GedfGenerator(BaseGenerator):
    def __init__(self, params={}):
        super(GedfGenerator, self).__init__("GSN-EDF", [TP_GLOB_TASK], [], params)
