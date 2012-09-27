import os

from collections import defaultdict
from point import Type

class TreeNode(object):
    def __init__(self, parent = None):
        self.parent = parent
        self.children = defaultdict(lambda : TreeNode(self))
        self.values = []

class DirMap(object):
    def to_csv(self, vals):
        val_strs = []
        for key in sorted(vals.keys()):
            val_strs += ["%s=%s" % (key, vals[key])]
        return "%s.csv" % ("_".join(val_strs))
    
    def __init__(self, out_dir):
        self.root = TreeNode(None)
        self.out_dir = out_dir
        self.values  = []

    def debug_update_node(self, path, keys, value):
        self.__update_node(path, keys, value)

    def __update_node(self, path, keys, value):
        node = self.root

        path += [ self.to_csv(keys) ]
        for p in path:
            node = node.children[p]

        node.values += [value]

    def add_point(self, vary, vary_value, keys, point):
        for stat in point.get_stats():
            summary = point[stat]

            for summary_type in Type:
                measurement = summary[summary_type]

                for base_type in Type:
                    if not base_type in measurement:
                        continue
                    # Ex: wcet/avg/max/vary-type/other-stuff.csv
                    path  = [ stat, summary_type, base_type, "vary-%s" % vary ]
                    result = measurement[base_type]

                    self.__update_node(path, keys, (vary_value, result))


                        
    def reduce(self):
        def reduce2(node):
            for key in node.children.keys():
                child = node.children[key]
                reduce2(child)
                if not (child.children or child.values):
                    node.children.pop(key)

            if len(node.values) == 1:
                node.values = []

        reduce2(self.root)

    def write(self):    
        def write2(path, node):
            out_path = "/".join(path)
            if node.values:
                # Leaf
                with open("/".join(path), "w") as f:
                    arr = [",".join([str(b) for b in n]) for n in node.values]
                    f.write("\n".join(arr) + "\n")
            elif not os.path.isdir(out_path):
                os.mkdir(out_path)        

            for (key, child) in node.children.iteritems():
                path.append(key)
                write2(path, child)
                path.pop()


        write2([self.out_dir], self.root)


    def __str__(self):
        def str2(node, level):
            header = "  " * level
            ret = ""
            if not node.children:
                return "%s%s\n" % (header, str(node.values) if node.values else "")
            for key,child in node.children.iteritems():
                ret += "%s/%s\n" % (header, key)
                ret += str2(child, level + 1)
            return ret
            
        return "%s\n%s" % (self.out_dir, str2(self.root, 1))
       
        
                
        
                
            
