from collections import namedtuple
import matplotlib.pyplot as plot

class Style(namedtuple('SS', ['marker', 'line', 'color'])):
    def fmt(self):
        return self.marker + self.line + self.color

class StyleMap(object):
    '''Maps configs (dicts) to specific line styles.'''
    DEFAULT = Style(marker='', line= '-', color='k')
    ORDER = [ str, bool, float, int ]

    def __init__(self, col_list, col_values):
        '''Assign (some) columns in @col_list to fields in @Style to vary, and
        assign values for these columns to specific field values.'''
        self.value_map = {}
        self.field_map = {}

        # Prioritize non-numbers
        def type_priority(column):
            value = col_values[column].pop()
            col_values[column].add(value)
            try:
                t = float if float(value) % 1.0 else int
            except:
                t = bool if value in ['True','False'] else str
            return StyleMap.ORDER.index(t)
        col_list = sorted(col_list, key=type_priority)

        # TODO: undo this, switch to popping mechanism
        for field, values in reversed([x for x in self.__get_all()._asdict().iteritems()]):
            if not col_list:
                break

            next_column = col_list.pop(0)
            value_dict  = {}

            for value in sorted(col_values[next_column]):
                value_dict[value] = values.pop(0)

            self.value_map[next_column] = value_dict
            self.field_map[next_column] = field

    def __get_all(self):
        '''A Style holding all possible values for each property.'''
        return Style(marker=list('.,ov^<>1234sp*hH+xDd|_'),
                     line=['-', ':', '--'],
                     color=list('bgrcmyk'))

    def get_style(self, kv):
        '''Translate column values to unique line style.'''
        style_fields = {}

        for column, values in self.value_map.iteritems():
            if column not in kv:
                continue
            field = self.field_map[column]
            style_fields[field] = values[kv[column]]

        return StyleMap.DEFAULT._replace(**style_fields)

    def get_key(self):
        '''A visual description of this StyleMap.'''
        key = []

        for column, values in self.value_map.iteritems():
            for v in values.keys():
                sdict = dict([(column, v)])
                style = self.get_style(sdict)

                styled_line = plot.plot([], [], style.fmt())[0]
                description = "%s:%s" % (column, v)

                key += [(styled_line, description)]

        return sorted(key, key=lambda x:x[1])

