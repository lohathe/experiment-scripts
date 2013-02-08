from collections import defaultdict
from point import SummaryPoint,Type
from dir_map import DirMap

from pprint import pprint

class TupleTable(object):
    def __init__(self, col_map):
        self.col_map = col_map
        self.table = defaultdict(lambda: [])
        self.reduced = False

    # TODO: rename, make exp agnostic, extend for exps
    def add_exp(self, kv, point):
        key = self.col_map.get_key(kv)
        self.table[key] += [point]

    def col_map(self):
        return self.col_map

    def get_exps(self, kv):
        key = self.col_map.get_key(kv)
        return self.table[key]

    def __contains__(self, kv):
        key = self.col_map.get_key(kv)
        return key in self.table

    def reduce(self):
        if self.reduced:
            raise Exception("cannot reduce twice!")
        self.reduced = True
        for key, values in self.table.iteritems():
            self.table[key] = SummaryPoint(values[0].id, values)

    def write_map(self, out_map):
        if not self.reduced:
            raise Exception("must reduce table to write map!")

        rows = {}

        for key, point in self.table.iteritems():
            row = {}
            for name,measurement in point:
                name = name.lower().replace('_','-')
                row[name]={}
                for base_type in Type:
                    type_key = str(base_type).lower()
                    if base_type in measurement[Type.Avg]:
                        value = measurement[Type.Avg][base_type]
                        row[name][type_key] = value
            rows[key] = row

        result = {'columns': self.col_map.columns(), 'rows':rows}

        with open(out_map, 'wc') as map_file:
            pprint(result,stream=map_file, width=20)


    def __add_to_dirmap(self, dir_map, variable, kv, point):
        value = kv.pop(variable)

        for stat in point.get_stats():
            summary = point[stat]

            for summary_type in Type:
                measurement = summary[summary_type]

                for base_type in Type:
                    if not base_type in measurement:
                        continue
                    # Ex: release/num_tasks/measured-max/avg/x=5.csv
                    leaf = self.col_map.encode(kv) + ".csv"
                    path = [ stat, variable, "taskset-" + base_type,
                             summary_type, leaf ]
                    result = measurement[base_type]

                    dir_map.add_values(path, [(value, result)])

        kv[variable] = value

    def to_dir_map(self):
        dir_map = DirMap()

        for key, point in self.table.iteritems():
            kv = self.col_map.get_kv(key)

            for col in self.col_map.columns():
                val = kv[col]

                try:
                    float(val)
                except:
                    # Only vary numbers. Otherwise, just have seperate files
                    continue

                self.__add_to_dirmap(dir_map, col, kv, point)

        dir_map.reduce()
        return dir_map
