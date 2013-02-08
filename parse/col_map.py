from collections import defaultdict

class ColMapBuilder(object):
    def __init__(self):
        self.value_map = defaultdict(set)

    def build(self):
        columns = sorted(self.value_map.keys(),
                         key=lambda c: (len(self.value_map[c]), c))
        col_list = filter(lambda c : len(self.value_map[c]) > 1, columns)
        return ColMap(col_list)

    def try_add(self, column, value):
        self.value_map[column].add( value )

    def try_remove(self, column):
        del(self.value_map[column])

class ColMap(object):
    def __init__(self, col_list):
        self.col_list = col_list
        self.rev_map = {}

        for i, col in enumerate(col_list):
            self.rev_map[col] = i

    def columns(self):
        return self.col_list

    def get_key(self, kv):
        '''Convert a key-value dict into an ordered tuple of values.'''
        key = ()

        for col in self.col_list:
            if col not in kv:
                key += (None,)
            else:
                key += (kv[col],)

        return key

    def get_kv(self, key):
        '''Convert an ordered tuple of values into a key-value dict.'''
        kv = {}
        for i in range(0, len(key)):
            kv[self.col_list[i]] = key[i]
        return kv


    def encode(self, kv):
        '''Converted a dict into a string with items sorted according to
        the ColMap key order.'''
        def escape(val):
            return str(val).replace("_", "-").replace("=", "-")

        vals = []

        for key in self.col_list:
            if key not in kv:
                continue
            k, v = escape(key), escape(kv[key])
            vals += ["%s=%s" % (k, v)]

        return "_".join(vals)

    @staticmethod
    def decode(string):
        '''Convert a string into a key-value dict.'''
        vals = {}
        for assignment in string.split("_"):
            k, v = assignment.split("=")
            vals[k] = v
        return vals

    def __contains__(self, col):
        return col in self.rev_map

    def __str__(self):
        return "<ColMap>%s" % (self.rev_map)
