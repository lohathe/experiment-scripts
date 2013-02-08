import os
import numpy as np

from collections import defaultdict

class TreeNode(object):
    def __init__(self, parent = None):
        self.parent = parent
        self.children = defaultdict(lambda : TreeNode(self))
        self.values = []

class DirMap(object):
    def __init__(self, in_dir = None):
        self.root = TreeNode(None)
        self.values  = []
        if in_dir:
            self.__read(in_dir)

    def add_values(self, path, values):
        node = self.root
        for p in path:
            node = node.children[p]
        node.values += values

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

    def write(self, out_dir):
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

        write2([out_dir], self.root)

    @staticmethod
    def read(in_dir):
        dir_map = DirMap()
        if not os.path.exists(in_dir):
            raise ValueError("Can't load from nonexistent path : %s" % in_dir)

        def read2(path):
            if os.path.isdir(path):
                map(lambda x : read2(path+"/"+x), os.listdir(path))
            else:
                with open(path, 'rb') as f:
                    data = np.loadtxt(f, delimiter=",")

                # Convert to tuples of ints if possible, else floats
                values = [map(lambda a:a if a%1 else int(a), t) for t in data]
                values = map(tuple, values)

                stripped = path if path.find(in_dir) else path[len(in_dir):]
                path_arr = stripped.split("/")

                dir_map.add_values(path_arr, values)

        read2(in_dir)

        return dir_map

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
        return str2(self.root, 1)
