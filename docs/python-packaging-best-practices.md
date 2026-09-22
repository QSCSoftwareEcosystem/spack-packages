# Best Practices: Python Packages for a Quantum HPC Ecosystem

This page collects conventions for packaging Python software in the QSC Spack
repository (`spack_repo/qsc/`).
The goal is that a package builds correctly and
reproducibly on laptops, CI, and heterogeneous HPC systems (mixed CPU/GPU/QPU
targets), while sharing dependencies with the rest of the ecosystem instead of
duplicating them.

The core principle behind almost every rule below is: **Spack manages
dependencies; CMake and Python must not.**
Every `pip`, `conda`, `FetchContent`, or bundled binary that bypasses Spack is
a dependency Spack doesn't know about, can't swap out for an
optimized/GPU-aware build, and can't guarantee ABI (application binary
interface) compatibility with the rest of the DAG.

## Choose a build system

Most Python packages use
`spack_repo.builtin.build_systems.python.PythonPackage`: see
[py_qiskit/package.py](../spack_repo/qsc/packages/py_qiskit/package.py).
Many packages also include compiled extensions built via CMake (e.g.
`scikit-build-core`, `pybind11`/`nanobind`): these *still* use `PythonPackage`.
That build system understands `pyproject.toml` / PEP 517 builds and will invoke
the backend's CMake step for you.
See [py_clifft/package.py](../spack_repo/qsc/packages/py_clifft/package.py) for
an example using `scikit-build-core` with `nanobind`.


Some C++/CMake applications or libraries merely *expose* a Python API as
bindings built as part of a larger CMake project.
These should use `CMakePackage` directly, as in
[qiree/package.py](../spack_repo/qsc/packages/qiree/package.py), and add
`extends("python")` if they install importable Python modules.

*Do not* ever directly call `setup.py`: Spack's `PythonPackage` builder uses
`pip install --no-build-isolation --no-deps` under the hood, which is what
makes "no vendoring" possible.

## Declare dependencies with spack

- *Every* build-time requirement must be an explicit
  `depends_on(..., type="build")` (or `type=("build", "run")` if also needed
  at import time).
- Because Spack disables pip's build isolation, nothing is fetched implicitly—if a
  `pyproject.toml` build-backend requirement (`setuptools`, `setuptools-scm`,
  `cython`, `scikit-build-core`, `nanobind`, `hatchling`, `pdm-backend`, ...)
  is not declared, the build will fail (or silently reach out to PyPI, which
  breaks air-gapped/HPC builds and is itself a form of vendoring).
- Mirror the project's `pyproject.toml` `[build-system].requires` and
  `[project].dependencies` exactly; pin lower bounds with `@x.y:` matching
  upstream's `>=` constraints.
- Use `type="test"` for test-only dependencies (`py-pytest`, etc.) so they
  don't bloat production install DAGs.
- Prefer generic virtual/provider deps (`blas`, `lapack`, `mpi`, `cuda`) over
  naming a specific implementation, so downstream users can swap
  `openblas` ↔ `intel-oneapi-mkl`, `openmpi` ↔ `mpich`, etc. without editing
  the package.
- When a Python package wraps a QPU SDK or hardware vendor library that only
  ships as a proprietary wheel, still add a `depends_on` (even a bare
  `resource()`/manual download) rather than letting pip pull it—this keeps
  provenance and licensing visible in `spack spec`.

## Python packages with C++ extensions

Quantum HPC Python packages very often wrap a C++/CUDA/HIP simulation kernel
(state-vector simulators, tensor-network contractions, QIR/LLVM tooling).
Getting these packages right requires understanding *which* build backend is
actually invoking CMake, and how to steer it from `package.py`.

### Which build backend drives CMake

`pip install` doesn't know anything about CMake by itself—it delegates the
build to whatever PEP 517 backend is named in `pyproject.toml`'s
`[build-system].build-backend`.
For CMake-based extensions in the wild you'll
mostly see:

- **`scikit_build_core.build`** (`scikit-build-core`)—the modern,
  actively-developed choice, and what most new nanobind/pybind11 projects use
  (e.g. [py_clifft](../spack_repo/qsc/packages/py_clifft/package.py), and
  upstream's `py-fenics-dolfinx`).
  It runs CMake + your generator (Ninja by
  default) under the hood and exposes CMake knobs through PEP 517
  `--config-settings`.
- **`skbuild`** (legacy `scikit-build`) is an older/less maintained
  API; treat like `scikit-build-core` for packaging purposes.
- **`mesonpython`** (`meson-python`)—same *pattern* as scikit-build-core but
  for Meson instead of CMake (e.g. upstream's `py-numpy`, `py-scipy`).
- **Bare `setuptools`** with a custom `build_ext`/`CMakeExtension`—an older,
  hand-rolled pattern (pre-dates PEP 517 build isolation controls) where
  `setup.py` shells out to `cmake`/`make` itself, often reading configuration
  from **environment variables** rather than command-line flags.
  Upstream `py-torch` is the canonical (extreme) example of this style.

Identify which one you're dealing with by checking `pyproject.toml`'s
`[build-system]` table before writing `cmake_args()`/`config_settings()` —
the two backends are configured completely differently.

### Passing configuration through `scikit-build-core` (PEP 517 config-settings)

For `PythonPackage` recipes, Spack's builder calls
`pip install --config-settings=KEY=VALUE ...` (implemented in
`spack_repo.builtin.build_systems.python.PythonPipBuilder.install`).
Override
the `config_settings()` hook to return the dict of settings—`scikit-build-core`
turns these directly into the equivalent `cmake -D...`/generator invocation:

```python
def config_settings(self, spec, prefix):
    return {
        # equivalent to `cmake --build . -- -jN`
        "build.tool-args": f"-j{make_jobs}",
        "build.verbose": "true",
        # equivalent to `cmake -DCMAKE_BUILD_TYPE=...`
        "cmake.build-type": spec.variants["build_type"].value,
        # equivalent to `cmake -DFOO=ON -DBAR=/path/to/thing`
        "cmake.define.CLIFFT_USE_MPI": "ON" if spec.satisfies("+mpi") else "OFF",
        "cmake.define.CLIFFT_BLAS_ROOT": spec["blas"].prefix,
    }
```

This mirrors how upstream's `py-fenics-dolfinx` package forwards a
`build_type` variant and parallel job count straight into scikit-build-core's
CMake invocation, and how `py-numpy`/`py-scipy` forward BLAS/LAPACK selection
through the equivalent `setup-args` key for `meson-python`.
Prefer this over
patching `CMakeLists.txt` whenever the value only needs to change a `-D`
define—it keeps the patch surface small and upstream-mergeable.

If the project's `pyproject.toml` doesn't live at the repository root (common
for monorepos, e.g.
FEniCSx keeps its Python bindings under `python/`), point
the builder at it instead of patching paths:

```python
build_directory = "python"
```

### Passing configuration to legacy `setup.py` + CMake builds via environment

Older or very large C++/CUDA projects (e.g. upstream `py-torch`) don't go
through PEP 517 config-settings at all—their `setup.py`/`CMakeLists.txt`
reads configuration straight out of `os.environ`.
For these, override
`setup_build_environment()` on the package and set the variables the build
expects, pointing them at Spack prefixes instead of letting the build fetch
or auto-detect something else:

```python
def setup_build_environment(self, env):
    if self.spec.satisfies("+cuda"):
        env.set("USE_CUDA", "1")
        env.set("CUDNN_INCLUDE_DIR", self.spec["cudnn"].prefix.include)
        env.set("CUDNN_LIBRARY", self.spec["cudnn"].libs[0])
    else:
        env.set("USE_CUDA", "0")

    # Tell the vendored build to use Spack's copies instead of fetching/bundling
    env.set("USE_SYSTEM_PYBIND11", "ON")
    env.set("USE_SYSTEM_EIGEN_INSTALL", "ON")
```

This is exactly the pattern `py-torch` uses (see its `USE_SYSTEM_*` and
`USE_CUDA`/`PYTORCH_ROCM_ARCH`/`BLAS` environment variables) to steer a
`setup.py`-driven CMake build without ever calling `pip install` yourself or
patching the CMake files.

### Letting `find_package()` see Spack's dependencies

Whichever mechanism you use, CMake still needs to *locate* Spack-built
dependencies:

- Spack automatically adds build/link dependencies' prefixes to
  `CMAKE_PREFIX_PATH` in the build environment, so a plain
  `find_package(nanobind CONFIG REQUIRED)` often succeeds with no extra flags.
- When that is insufficient (a dependency without a CMake config file, or a
  nonstandard install layout), be explicit rather than letting the project
  fall back to `FetchContent`:
  - pass `"cmake.define.<PKG>_ROOT": spec["pkg"].prefix` (scikit-build-core)
    or `self.define("<PKG>_ROOT", spec["pkg"].prefix)` (`CMakePackage.cmake_args()`);
  - or set an environment variable the project's `CMakeLists.txt` already
    checks (`<PKG>_DIR`, `<PKG>_ROOT`), as shown above for `py-torch`.
- For a `CMakePackage` (not a Python extension), override `cmake_args()`
  directly:

  ```python
  def cmake_args(self):
      return [
          self.define_from_variant("QIREE_USE_LIGHTNING", "lightning"),
          self.define("CMAKE_DISABLE_FIND_PACKAGE_CURL", True),
      ]
  ```

### Disabling `FetchContent`/vendored fallbacks

Many upstream `CMakeLists.txt` files fetch a private copy of `googletest`,
`fmt`, `json`, `pybind11`, `Eigen`, etc. if they aren't found on the system.
In rough order of preference:

1.
Make `find_package()` succeed (see previous subsection) so the fetch step
   is simply never reached.
2.
Set `-DFETCHCONTENT_FULLY_DISCONNECTED=ON` and/or
   `-DFETCHCONTENT_TRY_FIND_PACKAGE_MODE=ALWAYS` when the project supports
   it, to hard-fail instead of silently downloading.
3.
As a last resort, patch the `CMakeLists.txt` to delete the
   `FetchContent_Declare`/`add_subdirectory(third_party/...)` calls and
   replace them with `find_package()`—see
   [dmrgpp/fixup-brittle-hardcoded-relative-path.patch](../spack_repo/qsc/packages/dmrgpp/fixup-brittle-hardcoded-relative-path.patch)
   for the pattern of shipping a patch alongside `package.py`.
4.
For backends that expose it as a config-setting instead of a CMake
   define (e.g.
XGBoost's Python package), prefer that: upstream's
   `py-xgboost` sets `config_settings()` to return
   `{"use_system_libxgboost": True}` and patches the package to look in the
   Spack `xgboost` prefix rather than compiling its own bundled copy.

### Compiler and generator dependencies

- Always add `depends_on("cmake@X:", type="build")` with a lower bound that
  matches the project's `cmake_minimum_required`.
- Declare `depends_on("c", type="build")` / `depends_on("cxx", type="build")`
  (and `"fortran"` if relevant) so Spack picks a compatible compiler and
  doesn't assume the build is pure Python.
- For nanobind/pybind11 bindings, depend on `py-nanobind`/`py-pybind11` as a
  **build** dependency (they're header-only at runtime) instead of letting
  `scikit-build-core` fetch a copy via `FetchContent`.
- If the CMake project embeds a copy of a QPU/accelerator SDK's headers,
  check whether the ecosystem already has a Spack package for it—link
  against that instead of the bundled copy, even if it means adding a small
  patch to point `find_package`/`pkg-config` at the Spack prefix.

## Avoid vendored dependencies at the Python level

"Vendoring" here means anything that installs or downloads a private copy of
software that should instead be shared via Spack's dependency graph.

### Never let `pip` resolve dependencies on its own

Spack's `PythonPackage` already invokes `pip install --no-deps
--no-build-isolation`; don't override `install_args` to remove `--no-deps`,
and don't add `pip install` calls in `install()` or post-install hooks.

### Depend on the ecosystem's shared scientific stack, not bundled wheels

Don't bundle wheels for `numpy`, `scipy`, BLAS/LAPACK backends, MPI bindings
(`mpi4py`), or HDF5 bindings (`h5py`)—depend on the ecosystem's `py-numpy`,
`py-scipy`, `py-mpi4py`, `py-h5py`, which are themselves built against the
shared `blas`/`lapack`/`mpi`/`hdf5` Spack packages.
This is the only way
BLAS/MPI selection stays consistent (and GPU-aware) across the whole DAG.

### Point compiled extensions at Spack's copy instead of building their own

Some Python packages wrap a C++ library that can *also* build its own private
copy of that same library if you let it.
Prefer depending on the Spack
package and telling the Python build to link against it instead of compiling
its own:

- Upstream's `py-xgboost` depends on the separate `xgboost` Spack package,
  passes `config_settings()` returning `{"use_system_libxgboost": True}` (or
  `install_options()` returning `["--use-system-libxgboost"]` on older pip),
  and patches `xgboost/libpath.py` to point at `self.spec["xgboost"].prefix`
  instead of the bundled build.
- Upstream's `py-torch` sets `USE_SYSTEM_PYBIND11=ON`,
  `USE_SYSTEM_EIGEN_INSTALL=ON`, `USE_SYSTEM_GLOO=ON`, `USE_SYSTEM_NCCL=ON`,
  etc. (see [Python packages with C++ extensions](#python-packages-with-c-extensions))
  so its `setup.py`-driven CMake build links Spack's copies of those
  libraries rather than the ones vendored under `third_party/`.

### Watch for build backends that silently vendor their own tools

`scikit-build-core` and `meson-python` can pull in a private CMake/Ninja if
`cmake`/`ninja` aren't on `PATH`.
Always add `depends_on("cmake", type="build")`
and `depends_on("ninja", type="build")` explicitly so Spack's copies are used.

### Binary wheels that bundle prebuilt shared libraries

Some Python packages bundle prebuilt shared libraries inside their wheel
(common for `pip`-distributed CUDA/QPU SDKs).
When building from source is
possible, prefer it and depend on Spack's version of the library; when only a
proprietary binary wheel exists, isolate it as its own Spack package
(documented in `package.py` as an external/manual-download resource) so it is
not silently duplicated inside every consumer.

### Audit the installed tree

After building, it's worth a quick `ldd`/`otool -L` (compiled extensions) or
`grep` of the installed tree for suspicious bundled `.so`/`.dylib` files that
don't resolve to the Spack `prefix` of a dependency—that's a sign CMake
fell back to a vendored copy.

## Use virtual environments and Python environments

Spack itself *is* the environment manager here—don't layer `venv`/`conda`
underneath it.

### Never create a venv inside a `package.py` build step

Spack builds already happen in an isolated, PATH-controlled environment;
wrapping it in another virtual environment just hides which Python
interpreter and site-packages are actually being used.

### Use a Spack Environment as the shareable-venv analogue

For end users who want a reproducible, shareable set of packages (the Spack
analogue of a `requirements.txt`/venv), use a
[Spack Environment](https://spack.readthedocs.io/en/latest/environments.html)
(`spack.yaml` + `spack.lock`) instead of `python -m venv`:

```yaml
# spack.yaml
spack:
  specs:
    - py-qiskit
    - py-clifft
    - py-physics-tenpy +cuda
  view: true
```

`spack env activate` then puts a filesystem view on `PATH`/`PYTHONPATH` that
behaves like an activated venv, but every package in it is still tracked in
the Spack DAG (so `spack find`, rebuilds, and dependency audits all work).

### Prototyping outside of Spack

If a user genuinely needs `pip` for a package that is not in Spack yet (rapid
prototyping), point them at `spack python -m venv --system-site-packages ...`
or `pip install --user` *outside* of any `package.py`, and treat it as a
stopgap until the package is added to this repo—not as a packaging pattern.

### Keep `pip`/`venv` out of runtime dependencies

Avoid `depends_on("py-pip")`/`depends_on("py-virtualenv")` as *runtime*
dependencies of a package; they're only ever build tools for the package
manager itself, and adding them as run deps is a smell that something is
shelling out to `pip` at runtime.

### Don't port `conda`-first installs verbatim

If upstream ships a `conda`-first install (`environment.yml`), don't encode
that in the Spack package—re-derive the equivalent `depends_on()` list from
`pyproject.toml`/`setup.cfg` instead so Spack's solver—not conda's—owns
dependency resolution.

## Targeting mixed GPU/QPU platforms

The ecosystem is deployed across systems with different accelerator mixes
(NVIDIA GPUs, AMD GPUs, and various QPU/simulator backends), so a single
package often needs to build cleanly with any subset of them enabled.

### Model each accelerator backend as a variant

Default to `False`/off unless it's free to include everywhere (mirrors
`qiree`'s `+lightning`/`+qsim` pattern).
Keep hardware-specific code behind
the variant so a CPU-only site never needs a CUDA toolchain to build.

### Forward target architecture through `CudaPackage`/`ROCmPackage`

For CUDA/ROCm-capable packages, mix in Spack's `CudaPackage`/`ROCmPackage`
base classes (or forward `cuda_arch`/`amdgpu_target` variants) so the target
architecture is a first-class, solver-visible property instead of an env var
baked in at build time:

```python
depends_on("py-pennylane-lightning-gpu", when="+cuda")
depends_on("cuda_arch=70,80,90", when="+cuda")
```

### Never depend on PyPI's bundled CUDA wheels

`pip install nvidia-cublas-cu12` (or similar `-cuXX` PyPI wheels) is exactly
the kind of vendored CUDA library this repo avoids; depend on Spack's
`cuda`/`cudnn`/`nccl` packages so the same toolkit is shared with every other
GPU-enabled package in the DAG.

### QPU backends are optional variants too

Hardware access libraries and cloud-runtime SDKs should be optional variants,
gated on whether the target platform has that hardware/credentials—don't
assume every build host can reach a QPU.

### Use `conflicts()` for unsupported combinations

```python
conflicts("+rocm", when="+lightning", msg="lightning backend is CUDA-only")
```

### Keep GPU/QPU variants orthogonal

Keep variants independent of each other where possible so users can compose
exactly the backends their platform supports, e.g. `py-physics-tenpy +cuda
~rocm` on an NVIDIA node and `py-physics-tenpy ~cuda +rocm` on an AMD node
from the *same* `package.py`.

## Metadata and hygiene checklist

Quick checklist to run through before merging a new/updated `package.py`:

- [ ] `license(...)` set with a real SPDX identifier and `checked_by=<github user>`
      (avoid leaving `license("UNKNOWN", checked_by="github_user1")` as in the
      `dmrgpp` FIXME template).
- [ ] `homepage`/`pypi`/`git`/`url` all point at the canonical upstream, not a fork.
- [ ] Versions pinned by `sha256` (or `branch=`/`commit=` for `develop`/`main`
      tracking versions only).
- [ ] All `pyproject.toml` build-backend requirements present as
      `type="build"` deps.
- [ ] No `FetchContent`/bundled third-party source left un-patched in the
      CMake build.
- [ ] No `pip install`, `venv`, or `conda` invocations anywhere in the
      package recipe.
- [ ] GPU/QPU-specific code is behind a variant, not a hard dependency.
- [ ] `depends_on` uses shared/virtual packages (`blas`, `lapack`, `mpi`,
      `cuda`) rather than a hardcoded specific provider.

## References

- [Spack Packaging Guide](https://spack.readthedocs.io/en/latest/packaging_guide_creation.html)
- [Spack Environments](https://spack.readthedocs.io/en/latest/environments.html)
- [Spack `PythonPackage` build system](https://spack.readthedocs.io/en/latest/build_systems/pythonpackage.html)
- [Spack `CMakePackage` build system](https://spack.readthedocs.io/en/latest/build_systems/cmakepackage.html)
- Example packages in this repo:
  [py_qiskit](../spack_repo/qsc/packages/py_qiskit/package.py),
  [py_clifft](../spack_repo/qsc/packages/py_clifft/package.py),
  [py_physics_tenpy](../spack_repo/qsc/packages/py_physics_tenpy/package.py),
  [qiree](../spack_repo/qsc/packages/qiree/package.py),
  [dmrgpp](../spack_repo/qsc/packages/dmrgpp/package.py)
