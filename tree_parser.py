#!/usr/bin/env python
'''
Created on Jul 28, 2014

@author: davide
'''
import json
import os.path
import sys

class Node:
    
    def __init__(self, id, rate_num, rate_den, level, l_c = None, r_s = None):
        self.id = id
        self.rate_num = rate_num
        self.rate_den = rate_den
        self.level = level
        self.l_c = l_c
        self.r_s = r_s

def generate_params_preorder(node):
    
    if node is None:
        return [[-1, 0, 0, -1]]
    
    tmp_list = [[node.id, node.rate_num, node.rate_den, node.level]]
    for v in generate_params_preorder(node.l_c):
        tmp_list.append(v)
    for v in generate_params_preorder(node.r_s):
        tmp_list.append(v)

    return tmp_list

def parse_node(data):
    
    if len(data) < 1:
        return None
    
    first = prev = None
    
    for d in data:
        n = Node(d['id'], 
                 d['cost'], 
                 d['period'], 
                 d['level'])
        if prev is None:
            prev = n
            first = n
        else:
            prev.r_s = n
        n.l_c = parse_node(d['children'])
        prev = n
    
    return first

def rebuild_tree(data):
    return Node(data['id'], data['cost'], 
                data['period'], data['level'], 
                parse_node(data['children']), 
                None)

def main():
    
    root = None
    args = None
    executables = []
    
    # deep first traversal on json tree structure
    if (len(sys.argv) < 2) or not(os.path.isfile(sys.argv[1])):
        raise Exception("Invalid parameters")
    
    with open(sys.argv[1], 'r') as f:    
        data = json.load(f)
        root = rebuild_tree(data);
    
    if root is not None:
        args = generate_params_preorder(root)
    
    for a in args:
        print a
    
    #obj = {
    #        'id': task.id,
    #        'cost': task.cost,
    #        'period': task.period,
    #        'level' : task.level,
    #        'children': []
    #}
    #    if (task.level > 0):
    #        for ch in task.get_children():
    #            obj['children'].append(FixedRateTask.serialize(ch))
    #        
    #    return obj
    # 
    #root = {
    #   'id': 
    #}
        
    
    #for a in args:
    #    executables.append(Executable(BINS['qps_add_master'], a))
        
    #return executables
    
if __name__ == '__main__':
    main()