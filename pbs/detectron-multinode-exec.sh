#!/bin/bash

# CUDA_VISIBLE_DEVICES
device_ids=""
devices=$(egrep -o 'GPU-.*' $PBS_NODEFILE.env | tr ',' ' ')
for device in $devices; do
  ngpus=$((ngpus+1))
  device_id=$(nvidia-smi -L | grep $device | egrep -o 'GPU [0-3]' | sed 's/GPU //g')
  device_ids+=$device_id,
done
export CUDA_VISIBLE_DEVICES=${device_ids::-1}

# run
singularity exec \
  --nv \
  --pwd /host_pwd \
  --bind ${PWD}:/host_pwd \
  $IMAGE_PATH \
    python3 $1 \
    --num-machines $(sort -u $PBS_NODEFILE | wc -l) \
    --machine-rank ${PALS_NODEID} \
    --dist-url "tcp://${MASTER_ADDR}:${MASTER_PORT}" \
    --num-gpus $ngpus \
    ${@:2}
 