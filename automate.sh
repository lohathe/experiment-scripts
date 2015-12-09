#!/bin/bash

# EXPORTING PATHS
# SchedCAT, libLITMUS, featherTrace
SCHEDCAT_PATH="/home/luca/RUN/schedcat"
LITMUS_PATH="/home/luca/RUN/12-liblitmus"
FEATHERTRACE_PATH="/home/luca/RUN/12-feather-trace-tools"

export PATH=$PATH:$LITMUS_PATH:$FEATHERTRACE_PATH
export PYTHONPATH=$PYTHONPATH:$SCHEDCAT_PATH

# PARAMETERS OF THE EXPERIMENTS
# file describing the taskset/system
TASKSET=""
# number of processors to use in the experiment
CPU_COUNT=4
# how long to run each experiment (seconds)
DURATION=10

echo "Proceding to execute AUTOMATE. This may take a while."
echo "Several folders and files will be created."
echo " (o) gen-exps (input used to run the experiments)"
echo " (o) run-exps (tracing of the experiments)"
echo " (o) par-exps (parsed data extracted from the traces)"
echo " (o) result   (the final result)"
echo "The folder 'result' will contain a folder of images and the file"
echo "'automate.html'. Use a browser to open the file: it contains"
echo "all the results in a human-readable fashion."
echo "The folder 'result' will not require anything that resides in"
echo "other folders. Therefore, when AUTOMATE terminates 'gen-exps',"
echo "'run-exps' and 'par-exps' may be deleted without problem."

# From now on, modify with caution! (or not modify at all)
prepare_exps -c $CPU_COUNT -d $DURATION -i $TASKSET -o "gen-exps"
#run_exps -o "run-exps" "gen-exps/GSN-EDF" "gen-exps/PSN-EDF" "gen-exps/RUN" "gen-exps/QPS"
run_exps -o "run-exps" "gen-exps/"
parse_exps -o "par-exps/parsedData" -f -m -t -x "run-exps"
manage_parsed_data -o "result" -i "par-exps/parsedData" -s $TASKSET -c $CPU_COUNT

