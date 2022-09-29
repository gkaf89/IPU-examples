# Copyright (c) 2021 Graphcore Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import torch
import poptorch
import popart
import numpy as np
import os
from examples_utils import load_lib
import logging


def get_options(config):
    """
    Set ipu specific options for the model, see documentation:
    https://docs.graphcore.ai/en/latest/
    """

    if not config.compile_only and poptorch.ipuHardwareVersion() != 2:
        raise RuntimeError("This version of BERT requires an IPU Mk2 system to run.")

    # Load custom ops
    if config.custom_ops is True:
        logging.info("Building (if necessary) and loading residual_add_inplace_pattern.")
        load_lib(os.path.dirname(__file__) + '/custom_ops/workarounds/residual_add_inplace_pattern.cpp')

    # Poptorch options
    if config.use_popdist:
        # Use popdist.poptorch options if running in distributed mode
        import popdist
        import popdist.poptorch
        opts = popdist.poptorch.Options(ipus_per_replica=config.ipus_per_replica)
    else:
        opts = poptorch.Options()
        # Set the replication factor
        opts.replicationFactor(config.replication_factor)

    opts.autoRoundNumIPUs(True)
    opts.deviceIterations(config.device_iterations)

    # Set gradient accumulation factor
    opts.Training.gradientAccumulation(config.gradient_accumulation)
    opts.Training.accumulationAndReplicationReductionType(poptorch.ReductionType.Mean)

    # Enable automatic loss scaling
    # Note that it expects accumulationAndReplicationReductionType to be set
    # to Mean as above, and for accumulation by the optimizer to be done in
    # half precision using accum_type=torch.float16 during optimizer instatiation.
    if config.auto_loss_scaling is True:
        opts.Training.setAutomaticLossScaling(True)

    # For efficiency return the sum of the outputs from IPU to host
    opts.outputMode(poptorch.OutputMode.Sum)

    # Fix the random seeds
    np.random.seed(config.random_seed)
    opts.randomSeed(config.random_seed)

    # Enable Replicated Tensor Sharding (RTS) of optimizer state
    #  with optimizer state residing either on-chip or in DRAM
    opts.TensorLocations.setOptimizerLocation(
        poptorch.TensorLocationSettings()
        # Optimizer state lives on- or off-chip
        .useOnChipStorage(not config.optimizer_state_offchip)
        # Shard optimizer state between replicas with zero-redundancy
        .useReplicatedTensorSharding(config.replicated_tensor_sharding))

    # Use Pipelined Execution
    opts.setExecutionStrategy(
        poptorch.PipelinedExecution(poptorch.AutoStage.AutoIncrement))

    # Compile offline (no IPUs required)
    if config.compile_only:
        opts.useOfflineIpuTarget()

    # Set available Transient Memory For matmuls and convolutions operations
    mem_prop = {
        f'IPU{i}': config.matmul_proportion[i]
        for i in range(config.ipus_per_replica)
    }
    opts.setAvailableMemoryProportion(mem_prop)

    # Enable caching the compiled executable to disk
    if config.executable_cache_dir:
        opts.enableExecutableCaching(config.executable_cache_dir)

    # Enable stochastic rounding (recommended for training with FP16)
    opts.Precision.enableStochasticRounding(True)

    # Half precision partials for matmuls and convolutions
    if config.enable_half_partials:
        opts.Precision.setPartialsType(torch.float16)

    # Enable synthetic random data generated on device (so with no I/O)
    if config.synthetic_data:
        opts.enableSyntheticData(int(popart.SyntheticDataMode.RandomNormal))

    # PopART performance options #
    # Only stream needed tensors back to host
    opts._Popart.set("disableGradAccumulationTensorStreams", True)
    # Parallelize optimizer step update across IPUs
    opts._Popart.set("accumulateOuterFragmentSettings.schedule",
                     int(popart.AccumulateOuterFragmentSchedule.OverlapMemoryOptimized))
    opts._Popart.set("accumulateOuterFragmentSettings.excludedVirtualGraphs", ["0"])
    # Enable patterns for better throughput and memory reduction
    opts._Popart.set("subgraphCopyingStrategy", int(popart.SubgraphCopyingStrategy.JustInTime))
    opts._Popart.set("scheduleNonWeightUpdateGradientConsumersEarly", True)
    opts._Popart.setPatterns({"TiedGather": True, "TiedGatherAccumulate": True, "UpdateInplacePrioritiesForIpu": True})

    # Options for profiling with Popvision
    engine_options = {
        "opt.useAutoloader": "true",
        "target.syncReplicasIndependently": "true",
    }
    if config.profile_dir:
        engine_options = {
            **engine_options,
            **{
                "debug.allowOutOfMemory": "true",
                "autoReport.directory": config.profile_dir,
                "profiler.format": "v3",
                "autoReport.all": "true",
            }
        }
    opts._Popart.set("engineOptions", engine_options)

    return opts
