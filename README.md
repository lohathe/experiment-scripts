# About
These Python scripts provide a common way for creating, running, parsing, and plotting experiments using [LITMUS^RT][litmus]. These scripts are:

1. `gen_exps.py`: for creating sets of experiments
2. `run_exps.py`: for running and tracing experiments
3. `parse_exps.py`: for parsing LITMUS^RT trace data
4. `plot_exps.py`: for plotting directories of csv data

They are designed with the following principles in mind:

1. Little or no configuration: all scripts use certain parameters to configure behavior. However, if the user does not give these parameters, the scripts will examine the properties of the user's system to pick a suitable default. Requiring user input is a last resort.

2. Interruptability: the scripts save their work as they evaluate multiple directories. When the scripts are interrupted, or if new data is added to those directories, the scripts can be re-run and they will resume where they left off. This vastly decreases turnaround time for testing new features.

3. Maximum Safety: where possible, scripts save metadata in their output directories about the data contained. This metadata can be used by the other scripts to safely use the data later.

4. Independence / legacy support: none of these scripts assume their input was generated by another of these scripts. Three are designed to recognize generic input formats inspired by past LITMUS^RT experimental setups. (The exception to this is gen_exps.py, which has only user intput and creates output only for run_exps.py)

5. Save everything: all output and parameters (even from subprocesses) is saved for debugging / reproducability. This data is saved in tmp/ directories while scripts are running in case scripts fail.

# Dependencies
These scripts were tested using Python 2.7.2. They have not been tested using Python 3. The [Matplotlib][matplotlib] Python library is needed for plotting.

The `run_exps.py` script should almost always be run using a LITMUS^RT kernel. In addition to the kernel, the following LITMUS-related repos must be in the user's `PATH`:

1. [liblitmus][liblitmus]: for real-time executable simulation and task set release
2. [feather-trace-tools][feather-trace-tools]: for recording and parsing overheads and scheduling events

Additional features will be enabled if these repos are present in the `PATH`:

1. [rt-kernelshark][rt-kernelshark]: to record ftrace events for kernelshark visualization
2. sched_trace ([UNC internal][rtunc]) to output a file containing scheduling events as strings

# Details
Each of these scripts is designed to operate independently of the others. For example, `parse_exps.py` will find any feather trace files resembling `ft-xyz.bin` or `xyz.ft` and print out overhead statistics for the records inside. However, the scripts provide the most features (especially safety) when their results are chained together, like so:

```
gen_exps.py --> [exps/*] --> run_exps.py  --> [run-data/*] --.
.------------------------------------------------------------'
'--> parse_exps.py --> [parse-data/*] --> plot_exps.py --> [plot-data/*.pdf]
```

1. Create experiments with `gen_exps.py` or some other script.
2. Run experiments using `run_exps.py`, generating binary files in `run-data/`.
3. Parse binary data in `run-data/` using `parse_exps.py`, generating csv files in `parse-data/`.
4. Plot `parse-data` using `plot_exps.py`, generating pdfs in `plot-data/`.

Each of these scripts will be described. The `run_exps.py` script is first because `gen_exps.py` creates schedule files which depend on `run_exps.py`.


## run_exps.py
*Usage*: `run_exps.py [OPTIONS] [SCHED_FILE]... [SCHED_DIR]...`

where a `SCHED_DIR` resembles:
```
SCHED_DIR/
	SCHED_FILE
	PARAM_FILE
```

*Output*: `OUT_DIR/[files]` or `OUT_DIR/SCHED_DIR/[files]` or `OUT_DIR/SCHED_FILE/[files]` depending on input

If all features are enabled, these files are:
```
OUT_DIR/[SCHED_(FILE|DIR)/]
	trace.slog    # LITMUS logging
	st-[1..m].bin # sched_trace data
	ft.bin        # feather-trace overhead data
	trace.dat     # ftrace data for kernelshark
	params.py     # Schedule parameters
	exec-out.txt  # Standard out from schedule processes
	exec-err.txt  # Standard err '''
```

*Defaults*: `SCHED_FILE = sched.py`, `PARAM_FILE = params.py`, `DURATION = 30`, `OUT_DIR = run-data/`

This script reads *schedule files* (described below) and executes real-time task systems, recording all overhead, logging, and trace data which is enabled in the system (unless a specific set of tracers is specified in the parameter file, see below). For example, if trace logging is enabled, rt-kernelshark is found in the path, but feather-trace is disabled (the devices are not present), only trace logs and rt-kernelshark logs will be recorded.

When `run_exps.py` is running a schedule file, temporary data is saved in a `tmp` directory in the same directory as the schedule file. When execution completes, this data is moved into a directory under the `run_exps.py` output directory (default: `run-data/`, can be changed with the `-o` option). When multiple schedules are run, each schedule's data is saved in a unique directory under the output directory.

If a schedule has been run and it's data is in the output directory, `run_exps.py` will not re-run the schedule unless the `-f` option is specified. This is useful if your system crashes midway through a set of experiments.

You can use the `-j` option to send a jabber instant message every time an experiment completes. Running the script with `-j` will print out more details about this option.

Schedule files have one of the following two formats:

1. simple format
```
       path/to/proc{proc_value}
       ...
       path/to/proc{proc_value}
       [real_time_task: default rtspin] task_arguments...
       ...
       [real_time_task] task_arguments...
```

2. python format
```python
       {'proc':[
           ('path/to/proc','proc_value'),
            ...,
           ('path/to/proc','proc_value')
        ],
        'task':[
           ('real_time_task', 'task_arguments'),
            ...
           ('real_time_task', 'task_arguments')
        ]
       }
```

The following creates a simple 3-task system with utilization 2.0, which is then run under the `GSN-EDF` plugin:

```bash
$ echo "10 20
30 40
60 90" > test.sched
$ run_exps.py -s GSN-EDF test.sched
[Exp test/test.sched]: Enabling sched_trace
...
[Exp test/test.sched]: Switching to GSN-EDF
[Exp test/test.sched]: Starting 3 regular tracers
[Exp test/test.sched]: Starting the programs
[Exp test/test.sched]: Sleeping until tasks are ready for release...
[Exp test/test.sched]: Releasing 3 tasks
[Exp test/test.sched]: Waiting for program to finish...
[Exp test/test.sched]: Saving results in /root/schedules/test/run-data/test.sched
[Exp test/test.sched]: Stopping regular tracers
[Exp test/test.sched]: Switching to Linux scheduler
[Exp test/test.sched]: Experiment done!
Experiments run:        1
  Successful:           1
  Failed:               0
  Already Done:         0
  Invalid environment:  0

```

The following will write a release master using `/proc/litmus/release_master`:

```bash
$ echo "release_master{2}
10 20" > test.sched && run_exps.py -s GSN-EDF test.sched
```

A longer form can be used for proc entries not under `/proc/litmus`:

```bash
$ echo "/proc/sys/something{hello}
10 20" > test.sched
```

You can specify your own spin programs to run as well instead of rtspin by putting their name at the beginning of the line. This example also shows how you can reference files in the same directory as the schedule file on the command line.

```bash
$ echo "colorspin -f color1.csv 10 20" > test.sched
```

You can specify parameters for an experiment in a file instead of on the command line using params.py (the `-p` option lets you choose the name of this file if `params.py` is not for you):

```bash
$ echo "{'scheduler':'GSN-EDF', 'duration':10}" > params.py
$ run_exps.py test.sched
```

You can also run multiple experiments with a single command, provided a directory with a schedule file exists for each. By default, the program will look for sched.py for the schedule file and params.py for the parameter file, but this behavior can be changed using the `-p` and `-c` options.

You can include non-relevant parameters which `run_exps.py` does not understand in `params.py`. These parameters will be saved with the data output by `run_exps.py`. This is useful for tracking variations in system parameters versus experimental results. In the following example, multiple experiments are demonstrated and an extra parameter `test-param` is included:

```bash
$ mkdir test1
# The duration will default to 30 and need not be specified
$ echo "{'scheduler':'C-EDF', 'test-param':1}" > test1/params.py
$ echo "-p 1 10 20" > test1/sched.py
$ cp -r test1 test2
$ echo "{'scheduler':'GSN-EDF', 'test-param':2}"> test2/params.py
$ run_exps.py test*
```

You can specify commands to run before and after each experiment is run using 'pre-experiment' and 'post-experiment'. This is useful for complicated system setup such as managing shared resources. The following example prints out a message before and after an experiment is run (note that command line arguments can be specified using arrays):
```bash
$ echo "10 20" > sched.py
$ echo "{'scheduler':'GSN-EDF',
'pre-experiment' : 'script1.sh',
'post-experiment' : ['echo', 'Experiment ends!']}" > params.py
$ echo "#!/bin/bash
Experiment begins!" > script1.sh
$ run_exps.py
$ cat pre-out.txt
Experiment begins!
$ cat post-out.txt
Experiment ends!
```

Finally, you can specify system properties in `params.py` which the environment must match for the experiment to run. These are useful if you have a large batch of experiments which must be run under different kernels or kernel configurations. The first property is a regular expression for the name of the kernel:

```bash
$ uname -r
3.0.0-litmus
$ echo "{'uname': r'.*linux.*'}" > params.py
$ run_exps.py -s GSN-EDF test.sched
Invalid environment for experiment 'test.sched'
Kernel name does not match '.*linux.*'.
Experiments run:        1
  Successful:           0
  Failed:               0
  Already Done:         0
  Invalid Environment:  1
$ echo "{'uname': r'.*litmus.*'}" > params.py
# run_exps.py will now succeed
```

The second property is kernel configuration options. These assume the configuration is stored at `/boot/config-$(uname -r)`. You can specify these in `params.py`. In the following example, the experiment will only run on an ARM system with the release master enabled:

```python
{'config-options':{
	'RELEASE_MASTER' : 'y',
	'ARM' : 'y'}
}
```

The third property is required tracers. The `tracers` property lets the user specify only those tracers they want to run with an experiment, as opposed to starting every available tracer (the default). If any of these specified tracers cannot be enabled, e.g. the kernel was not compiled with feather-trace support, the experiment will not run. The following example gives an experiment which will not run unless all four tracers are enabled:
```python
{'tracers':['kernelshark', 'log', 'sched', 'overhead']}
```

## gen_exps.py
*Usage*: `gen_exps.py [options] [files...] [generators...] [param=val[,val]...]`

*Output*: `OUT_DIR/EXP_DIRS` which each contain `sched.py` and `params.py`

*Defaults*: `generators = G-EDF P-EDF C-EDF`, `OUT_DIR = exps/`

This script uses *generators*, one for each LITMUS scheduler supported, which each have different properties which can be varied to generate different types of schedules. Each of these properties has a default value which can be modified on the command line for quick and easy experiment generation.

This script as written should be used to create debugging task sets, but not for creating task sets for experiments shown in papers. That is because the safety features of `run_exps.py` described above (`uname`, `config-options`) are not used here. If you are creating experiments for a paper, you should create your own generator which outputs values for the `config-options` required for your plugin so that you cannot ruin your experiments at run time. Trust me, you will.

The `-l` option lists the supported generators which can be specified:

```bash
$ gen_exps.py -l
G-EDF, P-EDF, C-EDF
```

The `-d` option will describe the properties of a generator or generators and their default values. Note that some of these defaults will vary depending on the system the script is run. For example, the `cpus` parameter defaults to the number of cpus on the current system, in this example 24.

```bash
$ gen_exps.py -d G-EDF,P-EDF
Generator GSN-EDF:
        tasks -- Number of tasks per experiment.
                Default: [24, 48, 72, 96]
                Allowed: <type 'int'>
	....

Generator PSN-EDF:
        tasks -- Number of tasks per experiment.
                Default: [24, 48, 72, 96]
                Allowed: <type 'int'>
        cpus -- Number of processors on target system.
                Default: [24]
                Allowed: <type 'int'>
	....
```

You create experiments by specifying a generator. The following will create experiments 4 schedules with 24, 48, 72, and 96 tasks, because the default value of `tasks` is an array of these values (see above).

```bash
$ gen_exps.py P-EDF
$ ls exps/
sched=GSN-EDF_num-tasks=24/  sched=GSN-EDF_num-tasks=48/
sched=GSN-EDF_num-tasks=72/  sched=GSN-EDF_num-tasks=96/
```

You can modify the default using a single value (the `-f` option deletes previous experiments in the output directory, defaulting to `exps/`, changeable with `-o`):

```bash
$ gen_exps.py -f P-EDF tasks=24
$ ls exps/
sched=GSN-EDF_num-tasks=24/
```

Or with an array of values, specified as a comma-seperated list:

```bash
$ gen_exps.py -f tasks=`seq -s, 24 2 30` P-EDF
sched=PSN-EDF_num-tasks=24/  sched=PSN-EDF_num-tasks=26/
sched=PSN-EDF_num-tasks=28/  sched=PSN-EDF_num-tasks=30/
```

The generator will create a different directory for each possible configuration of the parameters. Each parameter which is varied is included in the name of the schedule directory. For example, to vary the number of CPUs but not the number of tasks:

```bash
$ gen_exps.py -f tasks=24 cpus=3,6 P-EDF
$ ls exps
sched=PSN-EDF_cpus=3/  sched=PSN-EDF_cpus=6/
```

The values of non-varying parameters are still saved in `params.py`. Continuing the example above:

```bash
$ cat exps/sched\=PSN-EDF_cpus\=3/params.py
{'periods': 'harmonic', 'release_master': False, 'duration': 30,
 'utils': 'uni-medium', 'scheduler': 'PSN-EDF', 'cpus': 3}
```

You can also have multiple schedules generated with the same configuration using the `-n` option:

```bash
$ gen_exps.py -f tasks=24 -n 5 P-EDF
$ ls exps/
sched=PSN-EDF_trial=0/  sched=PSN-EDF_trial=1/  sched=PSN-EDF_trial=2/
sched=PSN-EDF_trial=3/  sched=PSN-EDF_trial=4/
```

## parse_exps.py
*Usage*: `parse_exps.py [options] [data_dir1] [data_dir2]...`

where the `data_dirx` contain feather-trace and sched-trace data, e.g. `ft.bin`, `mysched.ft`, or `st-*.bin`.

*Output*: print out all parsed data or `OUT_FILE` where `OUT_FILE` is a python map of the data or `OUT_DIR/[FIELD]*/[PARAM]/[TYPE]/[TYPE]/[LINE].csv`, depending on input.

The goal is to create csv files which record how varying `PARAM` changes the value of `FIELD`. Only `PARAM`s which vary are considered.

`FIELD` is a parsed value, e.g. 'RELEASE' overhead or 'miss-ratio'. `PARAM` is a parameter which we are going to vary, e.g. 'tasks'. A single `LINE` is created for every configuration of parameters other than `PARAM`.

`TYPE` is the statistic of the measurement, i.e. Max, Min, Avg, or Var[iance]. The two types are used to differentiate between measurements across tasks in a single taskset, and measurements across all tasksets. E.g. `miss-ratio/*/Max/Avg` is the maximum of all the average miss ratios for each task set, while `miss-ratio/*/Avg/Max` is the average of the maximum miss ratios for each task set.

*Defaults*: `OUT_DIR, OUT_FILE = parse-data`, `data_dir1 = .`

This script reads a directory or directories, parses the binary files inside for feather-trace or sched-trace data, then summarizes and organizes the results for output. The output can be to the console, to a python map, or to a directory tree of csvs (default). The python map (using `-m`) can be used for schedulability tests. The directory tree can be used to look at how changing parameters affects certain measurements.

The script will use all of the system CPUs to process data (changeable with `-p`).

In the following example, too little data was found to create csv files, so the data is output to the console despite the user not specifying the `-v` option. This use is the easiest for quick overhead evalutation and debugging. Note that for overhead measurements like these, `parse_exps.py` will use the `clock-frequency` parameter saved in a params.py file by `run_exps.py` to calculate overhead measurements. If a param file is not present, as in this case, the current CPUs frequency will be used.

```bash
$ ls run-data/
taskset_scheduler=C-FL-split-L3_host=ludwig_n=10_idx=05_split=randsplit.ft
$ parse_exps.py
Loading experiments...
Parsing data...
 0.00%
Writing result...
Too little data to make csv files.
<ExpPoint-/home/hermanjl/tmp>
                 CXS:  Avg:     5.053  Max:    59.925  Min:     0.241
               SCHED:  Avg:     4.410  Max:    39.350  Min:     0.357
                TICK:  Avg:     1.812  Max:    21.380  Min:     0.241
```

In the next example, because the value of num-tasks varies, csvs can be created. The varying parameters used to create csvs were found by reading the `params.py` files under each `run-data` subdirectory.

```bash
$ ls run-data/
sched=C-EDF_num-tasks=4/   sched=GSN-EDF_num-tasks=4/
sched=C-EDF_num-tasks=8/   sched=GSN-EDF_num-tasks=8/
sched=C-EDF_num-tasks=12/  sched=GSN-EDF_num-tasks=12/
sched=C-EDF_num-tasks=16/  sched=GSN-EDF_num-tasks=16/
$ parse_exps.py run-data/*
$ ls parse-data/
avg-block/  avg-tard/  max-block/  max-tard/  miss-ratio/
```

You can use the `-v` option to print out the values measured even when csvs could be created.

You can use the `-i` option to ignore variations in a certain parameter (or parameters if a comma-seperated list is given). In the following example, the user has decided the parameter `option` does not matter after viewing output. Note that the `trial` parameter, used by `gen_exps.py` to create multiple schedules with the same configuration, is always ignored.

```bash
$ ls run-data/
sched=C-EDF_num-tasks=4_option=1/ sched=C-EDF_num-tasks=4_option=2/
sched=C-EDF_num-tasks=8_option=1/ sched=C-EDF_num-tasks=8_option=2/
$ parse_exps.py run-data/*
$ for i in `ls parse-data/miss-ratio/tasks/Avg/Avg/`; do echo $i; cat
$i; done
option=1.csv
 4 .1
 8 .2
option=2.csv
 4 .2
 8 .4
# Now ignore 'option' for more accurate results
$ parse_exps.py -i option run-data/*
$ for i in `ls parse-data/miss-ratio/tasks/Avg/Avg/`; do echo $i; cat
$i; done
line.csv
 4 .2
 8 .3
```

The second command will also have run faster than the first. This is because `parse_exps.py` will save the data it parses in `tmp/` directories before it attempts to sort it into csvs. Parsing takes far longer than sorting, so this saves a lot of time. The `-f` flag can be used to re-parse files and overwrite this saved data.

All output from the *feather-trace-tools* programs used to parse data is stored in the `tmp/` directories created in the input directories.  If the *sched_trace* repo is found in the users `PATH`, `st_show` will be used to create a human-readable version of the sched-trace data which will also be stored there.

## plot_exps.py
*Usage*: `plot_exps.py [OPTIONS] [CSV_DIR]...`

where a `CSV_DIR` is a directory or directory of directories (and so on) containing csvs, like:
```
CSV_DIR/[SUBDIR/...]
	line1.csv
	line2.csv
	line3.csv
```

*Outputs*: `OUT_DIR/[CSV_DIR/]*[PLOT]*.pdf`

where a single plot exists for each directory of csvs, with a line for for each csv file in that directory. If only a single `CSV_DIR` is specified, all plots are placed directly under `OUT_DIR`.

*Defaults*: `OUT_DIR = plot-data/`, `CSV_DIR = .`

This script takes directories of csvs (or directories formatted as specified below) and creates a pdf plot of each csv directory found. A line is created for each .csv file contained in a plot. [Matplotlib][matplotlib] is used to do the plotting. The script will use all of the system CPUs to process data (changeable with `-p`).

If the csv filenames are formatted like: `param=value_param2=value2.csv`, the variation of these parameters will be used to color the lines in the most readable way. For instance, if there are three parameters, variations in one parameter will change line color, another line style (dashes/dots/etc), and a third line markers (trianges/circles/etc).

If a directory of directories is passed in, the script will assume the top level directory is the measured value and the next level is the variable, ie: `value/variable/[..../]line.csv`, and will put a title on the plot of "Value by variable (...)". Otherwise, the name of the top level directory will be the title, like "Value".

A directory with some lines:

```bash
$ ls
line1.csv line2.csv
$ plot_exps.py
$ ls plot-data/
plot.pdf
```

A directory with a few subdirectories:

```bash
$ ls test/
apples/ oranges/
$ ls test/apples/
line1.csv line2.csv
$ plot_exps.py test/
$ ls plot-data/
apples.pdf oranges.pdf
```

A directory with many subdirectories:

```bash
$ ls parse-data
avg-block/  avg-tard/  max-block/  max-tard/  miss-ratio/
$ ls parse-data/avg-block/tasks/Avg/Avg
scheduler=C-EDF.csv scheduler=PSN-EDF.csv
$ plot_exps.py parse-data
$ ls plot-data
avg-block_tasks_Avg_Avg.pdf avg-block_tasks_Avg_Max.pdf avg-block_tasks_Avg_Min.pdf
avg-block_tasks_Max_Avg.pdf avg-block_tasks_Max_Max.pdf avg-block_tasks_Max_Min.pdf
avg-block_tasks_Min_Avg.pdf avg-block_tasks_Min_Max.pdf avg-block_tasks_Min_Min.pdf
avg-block_tasks_Var_Avg.pdf avg-block_tasks_Var_Max.pdf avg-block_tasks_Var_Min.pdf
.......
```

If you run the previous example directly on the subdirectories, subdirectories will be created in the output:

```bash
$ plot_exps.py parse-data/*
$ ls plot-data/
avg-block/  max-tard/ avg-tard/ miss-ratio/ max-block/
$ ls plot-data/avg-block/
tasks_Avg_Avg.pdf  tasks_Avg_Min.pdf  tasks_Max_Max.pdf
tasks_Min_Avg.pdf  tasks_Min_Min.pdf  tasks_Var_Max.pdf
tasks_Avg_Max.pdf  tasks_Max_Avg.pdf  tasks_Max_Min.pdf
tasks_Min_Max.pdf  tasks_Var_Avg.pdf  tasks_Var_Min.pdf
```

However, when a single directory of directories is given, the script assumes the experiments are related and can make line styles match in different plots and more effectively parallelize the plotting.

[litmus]: https://github.com/LITMUS-RT/litmus-rt
[liblitmus]: https://github.com/LITMUS-RT/liblitmus
[rt-kernelshark]: https://github.com/LITMUS-RT/rt-kernelshark
[feather-trace-tools]: https://github.com/LITMUS-RT/feather-trace-tools
[rtunc]: http://www.cs.unc.edu/~anderson/real-time/
[matplotlib]: http://matplotlib.org/