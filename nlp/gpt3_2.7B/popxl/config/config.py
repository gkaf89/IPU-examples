# Copyright (c) 2022 Graphcore Ltd. All rights reserved.
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass
from utils.simple_parsing_tools import Config, Choice, flag, parse_args_with_config_file
import popxl


@dataclass
class ModelConfig(Config):
    """Change the size/setup of the GPT model"""

    layers: int = 12
    """The number of decoder blocks in
        the model (hf: n_layer)"""

    hidden_size: int = 768
    """The hidden size of the decoder blocks (hf: n_embd)."""

    sequence_length: int = 128
    """Number of tokens in a sample."""

    eval: bool = flag(False)
    """If eval mode is enabled the model will be built for inference or validation
    - disabling steps such as dropout and optimisation."""

    dropout_prob: float = 0.1
    """Dropout probability"""

    class Precision(Choice):
        float32 = popxl.float32
        float16 = popxl.float16

    precision: Precision = Precision.float16
    """Set the precision used for parameters in the model. Supported: float32, float16."""

    @property
    def dtype(self) -> popxl.dtype:
        return self.precision.value

    @dtype.setter
    def dtype(self, value: popxl.dtype):
        self.precision = ModelConfig.Precision(value)

    seed: int = 42
    """The random seed used by the model and host-side data generation (numpy and pytorch)."""

    @dataclass
    class Embedding(Config):
        """Configuration of GPT Embedding layers"""

        vocab_size: int = 50257
        """Number of entries in the word vocabulary"""

        max_positional_length: int = 1024
        """Maximum number of positions to support in the embeddings.
            The position embedding will be constructed as:
            shape=[max_positional_length, hidden_size]. (hf: n_positions)"""

    embedding: Embedding = Embedding()

    @dataclass
    class Attention(Config):
        """Configuration of GPT Attention layers"""

        heads: int = 12
        """Number of Attention Heads"""

    attention: Attention = Attention()


@dataclass
class Training(Config):
    """Changes the training setup."""

    steps: int = 1
    """The number of training steps."""

    epochs: int = 1
    """The number of iterations through the whole dataset to train for. Typically `steps` would be used,
        however some tasks have hyperparameters defined using epochs, such as SQuAD."""

    global_batch_size: int = 32
    """The number of samples that contribute to an optimizer step."""

    stochastic_rounding: bool = flag(True)
    """See https://docs.graphcore.ai/projects/ai-float-white-paper/en/latest/ai-float.html#deterministic-versus-stochastic-rounding"""

    @dataclass
    class Optimizer(Config):
        """Changes the optimizer setup and hyperparameters."""

        name: str = "adamw"

        @dataclass
        class LearningRate(Config):
            """Changes the learning rate function."""

            function: str = "linear"

            maximum: float = 0.01

            warmup_proportion: float = 0.0

        learning_rate: LearningRate = LearningRate()

        beta1: float = 0.9

        beta2: float = 0.999

        weight_decay: float = 0.01

        gradient_clipping: float = 1.0

    optimizer: Optimizer = Optimizer()


@dataclass
class Data(Config):
    """Configures the dataset"""

    input_files: Tuple[str, ...] = ()


@dataclass
class Execution(Config):
    """Changes the execution of the model."""

    micro_batch_size: int = 1
    """The number of samples that contribute to a
        gradient accumulation step."""

    data_parallel: int = 1
    """Set the number of model replicas to use for data-parallelism."""

    device_iterations: int = 1
    """Number of times the training loop is executed before relinquishing control and reporting to the host """

    io_tiles: int = 1

    available_memory_proportion: Tuple[float, ...] = (0.28, 0.28, 0.28, 0.28)

    loss_scaling: int = 1
    """The loss scaling to apply to gradient. This helps avoid underflowing
        in the gradient calculations."""

    pipeline: Optional[Tuple[int, ...]] = None
    """pipeline layers distribution."""

    @property
    def pipeline_ipus(self):
        return len(self.pipeline) if self.pipeline else 1

    def get_pipeline_layer_ipu(self):
        """List containing the ipu number for each layer"""
        layer_ipu: List[int] = []
        for ipu, n_layers in enumerate(self.pipeline):
            layer_ipu += [ipu] * n_layers
        return layer_ipu

    tensor_parallel: int = 1
    """Number of ipus used for tensor model parallel axis"""

    code_load: bool = flag(False)
    """Store the code for each layer graph in remote memory"""


@dataclass
class Checkpoint(Config):
    """Configuration of how to manage loading/storing of checkpoints"""

    load: Optional[str] = None
    """Load checkpoint from this location"""

    save: Optional[str] = None
    """Save checkpoint to this location"""


@dataclass
class GPTConfig(Config):
    """Configuration of PopXL GPT"""

    model: ModelConfig = ModelConfig()
    training: Training = Training()
    data: Data = Data()
    execution: Execution = Execution()
    checkpoint: Checkpoint = Checkpoint()

    @property
    def gradient_accumulation(self):
        denom = (self.execution.data_parallel *
                 self.execution.micro_batch_size)
        if self.training.global_batch_size % denom != 0:
            raise RuntimeError(
                "Unable to set gradient accumulation to match the global batch size. "
                "global_batch_size % (data_parallel * micro_batch_size) != 0. "
                f"{self.training.global_batch_size} % "
                f"({self.execution.data_parallel} * {self.execution.micro_batch_size}) != 0")

        return self.training.global_batch_size // denom

    @property
    def ipus(self):
        """Total number of IPUs required for execution"""
        DP = self.execution.data_parallel
        PP = self.execution.pipeline_ipus
        TP = self.execution.tensor_parallel
        return DP * PP * TP

    def validate(self):
        if self.training.epochs > 1 and self.training.steps > 1:
            logging.warning(
                "Both `steps` and `epochs` are specified. Only one will be used.")
        assert self.model.hidden_size % self.model.attention.heads == 0, "Hidden size should be a multiple of attention heads"


if __name__ == "__main__":
    config = parse_args_with_config_file(GPTConfig)
    print(config.dumps_yaml())
