# Graphcore: Dynamic Sparsity

---
## Dynamic Sparse Matrix Support

The Poplar SDK supports dynamic sparse weight matrices where the
sparsity pattern can be dynamically changed at runtime. The library
here uses custom TensorFlow ops to access that dynamic sparsity
support in the popsparse library from PopLibs and exposes it via a
layers API e.g. SparseFcLayer. Unlike many sparse training
implementations the sparse representation in the model is triplets (COO)
rather than dense masks. This representation is much simpler and more
efficient to manipulate in the host side Python code, as well as mapping
naturally to the proprietary on IPU representation.

### Sparse Training Algorithms
This dynamic sparsity support can be used to build sparse training
algorithms: training of models whilst simultaneously learning an
appropriate sparsity pattern (as opposed to pruning of a pre-trained
dense model to create a sparse network). Some examples of this are
provided here: MNIST and a dynamic sparse language model based on GPT2.
Both these examples implement Rig-L ([arxiv](https://arxiv.org/abs/1911.11134))
as the sparse traninig algorithm but the library could be used to efficiently
implement various other sparse training methods. For more information on these
models view their respective READMEs.

NOTE: Although dynamic sparsity has been supported since Poplar SDK
1.2 these examples require Poplar SDK >= 1.4.

### File structure

* ipu_sparse_ops/ A TensorFlow Python module for accessing IPU sparse custom ops.
* mnist_rigl/ Train MNIST using the ipu_sparse_ops module to implement a dymanic sparse optimiser (Rig-L)
* language_modelling/ A transformer based language model where all weight matrices can be sparsely trained using Rig-L.
* `README.md` This file.

### How to use this application

1) Prepare the environment.

   Install the Poplar SDK following the instructions in the Getting Started guide for your IPU system.
   Make sure to source the enable.sh script for poplar and install the Graphcore TensorFlow 1.15.x wheel.

2) Install required pip modules:

```bash
pip install -r requirements.txt
```

3) Check that you have the required apt packages installed in order to build the custom ops:

```bash
dpkg-query -W -f='${Status} ${Version}\n' $(<required_apt_packages.txt)
```

If you have admin privileges, you can install any that are missing with the following command, otherwise contact your system administrator to do this for you:

```bash
sudo apt install $(< required_apt_packages.txt)
```  


4) Build the custom ops and then run the Python code. The command below runs a simple test of the ipu_sparse_ops module. To use this module it must be on your `PYTHONPATH`. (Below the environment variable is set only for this single command but you can append ipu_sparse_ops permanently to your Python path if you intend to use the module regularly).

Build the ipu_sparse_ops module and test it:
```bash
make -j
PYTHONPATH=./:$PYTHONPATH python ipu_sparse_ops/tools/sparse_matmul.py
```

If you have previously built this module using a different SDK version run ```make clean``` before running ```make -j```.

To run any of the sparse models/training see the READMEs in their respective folders for example mnist_rigl/README.md, language_modelling/README.md.

## Running and benchmarking

To run a tested and optimised configuration and to reproduce the performance shown on our [performance results page](https://www.graphcore.ai/performance-results), please follow the setup instructions in this README to setup the environment, and then use the `examples_utils` module (installed automatically as part of the environment setup) to run one or more benchmarks. For example:

```python
python3 -m examples_utils benchmark --spec <path to benchmarks.yml file>
```

Or to run a specific benchmark in the `benchmarks.yml` file provided:

```python
python3 -m examples_utils benchmark --spec <path to benchmarks.yml file> --benchmark <name of benchmark>
```

For more information on using the examples-utils benchmarking module, please refer to [the README](https://github.com/graphcore/examples-utils/blob/master/examples_utils/benchmarks/README.md).


