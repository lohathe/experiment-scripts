from collections import defaultdict
from point import SummaryPoint
from dir_map import DirMap

class ColMap(object):
    def __init__(self):
        self.rev_map = {}
        self.value_map = {}
        self.col_list = []

    def columns(self):
        return self.col_list

    def get_key(self, kv):
        key = ()

        for col in self.col_list:
            if col not in kv:
                key += (None,)
            else:
                key += (kv[col],)

        return key

    def __contains__(self, col):
        return col in self.rev_map

    def get_map(self, tuple):
        map = {}
        for i in range(0, len(tuple)):
            map[self.col_list[i]] = tuple[i]
        return map

    def try_add(self, column, value):
        if column not in self.rev_map:
            if column not in self.value_map:
                self.value_map[column] = value
            elif value != self.value_map[column]:
                self.rev_map[column] = len(self.col_list)
                self.col_list += [column]

    def __str__(self):
        return "<ColMap>%s" % (self.rev_map)

class TupleTable(object):
    def __init__(self, col_map):
        self.col_map = col_map
        self.table = defaultdict(lambda: [])
        self.reduced = False

    # TODO: rename, make exp agnostic, extend for exps
    def add_exp(self, kv, point):
        key = self.col_map.get_key(kv)
        self.table[key] += [point]

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
            self.table[key] = SummaryPoint(str(key), values)

    def write_result(self, out_dir):
        dir_map = DirMap(out_dir)

        for key, point in self.table.iteritems():
            kv = self.col_map.get_map(key)

            for col in self.col_map.columns():
                val = kv[col]

                try:
                    float(val)
                except:
                    # Only vary numbers. Otherwise, just have seperate lines
                    continue

                kv.pop(col)
                dir_map.add_point(col, val, kv, point)
                kv[col] = val

        dir_map.reduce()
        dir_map.write()
