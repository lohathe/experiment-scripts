import re
import time
import subprocess
import config.config as conf

def switch_scheduler(switch_to_in):
    '''Switch the scheduler to whatever is passed in.

    This methods sleeps for two seconds to give Linux the chance to execute
    schedule switching code. Raises an exception if the switch does not work.

    '''

    switch_to = str(switch_to_in).strip()

    with open('/proc/litmus/active_plugin', 'w') as active_plugin:
        subprocess.Popen(["echo", switch_to], stdout=active_plugin)

    # it takes a bit to do the switch, sleep an arbitrary amount of time
    time.sleep(2)

    with open('/proc/litmus/active_plugin', 'r') as active_plugin:
        cur_plugin = active_plugin.read().strip()

    if switch_to != cur_plugin:
        raise Exception("Could not switch to plugin: %s" % switch_to)

def waiting_tasks():
    reg = re.compile(r'^ready.*?(?P<READY>\d+)$', re.M)
    with open('/proc/litmus/stats', 'r') as f:
        data = f.read()

    # Ignore if no tasks are waiting for release
    match = re.search(reg, data)
    ready = match.group("READY")

    return 0 if not ready else int(ready)

def release_tasks():

    try:
        data = subprocess.check_output([conf.BINS['release']])
    except subprocess.CalledProcessError:
        raise Exception('Something went wrong in release_ts')

    released = re.findall(r"([0-9]+) real-time", data)[0]

    return int(released)
