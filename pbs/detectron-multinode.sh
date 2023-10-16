#!/bin/bash

# environment
module load cray-pals

echo $(pwd)

# cd
cd ${PBS_O_WORKDIR:-""}

# address & port
export MASTER_NODE=$(head -1 $PBS_NODEFILE)
export MASTER_ADDR=$(ssh -n $MASTER_NODE ifconfig hsn0 | egrep -o 'inet [0-9.]+' | sed 's/inet //g')
RANDOM=$(egrep -o '^[0-9]+' <<< $PBS_JOBID)
export MASTER_PORT=$((1024+RANDOM*190/100))

# nodes
nodes=$(cat $PBS_NODEFILE)

# exit if no file given
if [[ $# -eq 0 ]]; then
  echo "[$(date +%d-%m-%Y' '%H:%M:%S)] detectron-multinode.sh: no arguments given"
  exit 1
else
  # otherwise launch
  mpiexec \
    --np $(wc -l <<< $nodes) \
    --hosts $(tr '\n' ',' <<< $nodes) \
    --ppn 1 \
    --cpu-bind none \
    $(dirname "$0")/detectron-multinode-exec.sh $@
fi
