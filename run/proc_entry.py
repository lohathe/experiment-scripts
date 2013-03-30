import os

class ProcEntry(object):
    def __init__(self, proc, data):
        self.proc = proc
        self.data = data

    def write_proc(self):
        if not os.path.exists(self.proc):
            raise Exception("Invalid proc entry %s" % self.proc)
        try:
            with open(self.proc, 'w') as entry:
                entry.write(self.data)
        except:
            print("Failed to write into %s value:\n%s" % (self.proc, self.data))
