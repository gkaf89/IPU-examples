# Copyright (c) 2020 Graphcore Ltd. All rights reserved.
import argparse
import yaml
import multiprocessing
import import_helper
import models


class YAMLNamespace(argparse.Namespace):
    def __init__(self, config_dict):
        for key, value in config_dict.items():
            setattr(self, key, value)


def get_available_configs(config_file):
    with open(config_file) as file:
        configs = yaml.full_load(file)
    return configs


def parse_with_config(parser, config_file, custom_args=None):
    configurations = get_available_configs(config_file)
    parser.add_argument('--config', choices=configurations.keys(), help="Select from avalible configurations")

    def parse_args(arguments):
        if arguments is None:
            return parser.parse_args()
        else:
            return parser.parse_known_args(args=arguments)[0]
    args = parse_args(custom_args)
    if args.config is not None:
        # Load the configurations from the YAML file and update command line arguments
        loaded_config = YAMLNamespace(configurations[args.config])
        # Check the config file keys
        for k in vars(loaded_config).keys():
            assert k in vars(args).keys(), f"Couldn't recognise argument {k}."

        args = parser.parse_args(args=custom_args, namespace=loaded_config)
    if args.dataloader_worker is None:
        # determine dataloader-worker
        args.dataloader_worker = min(32, multiprocessing.cpu_count())
    return args


def get_common_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--micro-batch-size', type=int, default=1, help='Micro batch size for training')
    parser.add_argument('--dataloader-rebatch-size', type=int, help='Dataloader rebatching size. (Helps to optimise the host memory footprint)')
    parser.add_argument('--iterations', type=int, default=100, help='number of program iterations')
    parser.add_argument('--model', choices=models.available_models.keys(),  default='resnet18', help="Choose model")
    parser.add_argument('--pipeline-splits', type=str, nargs='+', default=[], help="List of the splitting layers")
    parser.add_argument('--replicas', type=int, default=1, help="Number of IPU replicas")
    parser.add_argument('--device-iterations', type=int, default=1, help="Device Iteration")
    parser.add_argument('--half-partial', action='store_true', help='Accumulate matrix multiplication partials in half precision')
    parser.add_argument('--exchange-memory-target', default='cycles', choices=['cycles', 'balanced', 'memory'], help='Exchange memory optimisation target: balanced/cycles/memory. In case of '
                        'cycles it uses more memory, but runs faster.')
    parser.add_argument('--norm-type', choices=['batch', 'group', 'none'], default='batch',  help="Set normalization layers in the model")
    parser.add_argument('--norm-eps', type=float, default=1e-5,  help="Set normalization layers epsilon")
    parser.add_argument('--norm-num-groups', type=int, default=32, help="In case of group normalization, the number of groups")
    parser.add_argument('--enable-fast-groupnorm', action='store_true', help="There are two implementations of the group norm layer. If the fast implementation enabled, "
                        "it couldn't load checkpoints, which didn't train with this flag. The default implementation can use any checkpoint.")
    parser.add_argument('--batchnorm-momentum', type=float, default=0.1, help="BatchNorm momentum")
    parser.add_argument('--normalization-location', choices=['host', 'ipu', 'none'], default='host', help='Location of the data normalization')
    parser.add_argument('--eight-bit-io', action='store_true', help="Image transfer from host to IPU in 8-bit format, requires normalisation on the IPU")
    parser.add_argument('--dataloader-worker', type=int, help="Number of worker for each dataloader")
    parser.add_argument('--profile', action='store_true', help='Create PopVision Graph Analyzer report')
    parser.add_argument('--model-cache-path', type=str, help='Load the precompiled model from the given path. If the given path is empty / not existing the compiled model is saved to the given folder')
    parser.add_argument('--input-image-padding', action='store_true', help='Pad input images to be 4 channel images. This could speed up the model.')
    parser.add_argument('--num-io-tiles', type=int, default=0, help='Number of IO tiles. Minimum 32. Default 0 (no overlap)')
    parser.add_argument("--compile-only", action="store_true", help="Create an offline IPU target that can only be used for offline compilation.")
    parser.add_argument('--offline-target-ipu-version', type=int, default=2, help="IPU version used for offline compilation.")
    # EfficientNet parameters
    parser.add_argument('--efficientnet-expand-ratio', type=int, default=6, help='Expand ratio of the blocks in EfficientNet')
    parser.add_argument('--efficientnet-group-dim', type=int, default=1, help='Group dimensionality of depthwise convolution in EfficientNet')
    return parser
