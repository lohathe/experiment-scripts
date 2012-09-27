from collections import defaultdict

def load_params(fname):
    params = defaultdict(int)
    with open(fname, 'r') as f:
        data = f.read()
    try:
        parsed = eval(data)
        # Convert to defaultdict
        for k in parsed:
            params[k] = str(parsed[k])
    except Exception as e:
        raise IOError("Invalid param file: %s\n%s" % (fname, e))

    return params


