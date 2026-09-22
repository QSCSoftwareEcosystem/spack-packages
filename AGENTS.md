# AGENTS

## Project purpose

This repository holds the QSC Spack package repository for rapid development and deployment of quantum science software in HPC environments. The repo is meant to package software using Spack so that dependencies are managed consistently, reproducibly, and with awareness of CPU/GPU/QPU heterogeneity.

The project is currently in early development, with the expectation that contributors are building new packages for the SE team and extending the repository as new workflows and HPC environments are needed.

## Repository layout

- `README.md`: project overview and basic Spack usage.
- `docs/python-packaging-best-practices.md`: core conventions for Python packages in this repository.
- `spack_repo/qsc/repo.yaml`: Spack repository metadata.
- `spack_repo/qsc/packages/`: package recipes, one package per directory.

## Working with this repo

### Add the repo to Spack

If Spack is already configured, add this repository with:

```sh
spack repo add https://github.com/QSCSoftwareThrust/spack-packages.git
```

This repo behaves like a normal local Spack repository checkout, and package locations can be inspected with `spack location --repo` or `spack repo list`.

### Create a new package

Use the normal Spack packaging flow, but indicate QSC ownership with:

```sh
spack create -N qsc <package-name>
```

For Python packages, follow the guidance in [docs/python-packaging-best-practices.md](docs/python-packaging-best-practices.md) rather than ad hoc package definitions.

## Core packaging rules

### 1) Spack owns dependency resolution

The dominant rule is: Spack manages dependencies; CMake and Python must not.

- Do not rely on `pip`, `conda`, `FetchContent`, or bundled binaries as a substitute for Spack packages.
- If a dependency is not declared in the Spack recipe, it is not part of the verified DAG and may break reproducibility or HPC portability.
- Dependencies that are build-only or runtime-only should be declared explicitly with the right Spack dependency types.

### 2) Prefer `PythonPackage` for Python projects

Most Python packages should use `spack_repo.builtin.build_systems.python.PythonPackage`.

- This is the right fit for `pyproject.toml` / PEP 517 builds.
- It supports `pip install --no-build-isolation --no-deps` semantics and avoids vendoring.
- For compiled extensions built with CMake or another backend, keep using `PythonPackage` and pass configuration through the supported build hooks.

For projects that are more naturally CMake-first libraries with Python bindings, use `CMakePackage` and add `extends("python")` when appropriate.

### 3) Declare build requirements explicitly

Every build requirement should be declared using Spack dependency rules, including relevant build tools like:

- `cmake`
- `c`, `cxx`, `fortran` as needed
- Python build backends like `py-setuptools`, `py-scikit-build-core`, `py-nanobind`, `py-pybind11`, etc.
- BLAS/LAPACK/MPI/CUDA or provider-level virtual dependencies instead of hard-coding a single concrete implementation.

This keeps downstream installs consistent and portable across hardware targets.

### 4) Do not vendor scientific dependencies

Do not bundle or fetch private copies of scientific software that should instead be shared via Spack, such as:

- NumPy / SciPy
- BLAS / LAPACK backends
- MPI libraries and MPI Python bindings
- HDF5-related packages
- common C++/CMake dependencies such as `pybind11`, `nanobind`, Eigen, GoogleTest, etc.

Prefer letting Spack provide the correct, shared, GPU-aware version of the dependency stack.

### 5) Use the package build hooks to steer CMake correctly

For Python packages with compiled extensions:

- Identify the actual build backend from `pyproject.toml` (`scikit-build-core`, `skbuild`, `meson-python`, or legacy `setuptools` + `setup.py`).
- Use `config_settings()` for PEP 517-backed builds to pass `cmake` settings.
- Use `setup_build_environment()` for legacy `setup.py` / CMake flows that read environment variables.
- Expose dependency prefixes using `*_ROOT`/`*_DIR` or `CMAKE_PREFIX_PATH`-friendly configuration so `find_package()` resolves Spack-provided packages.

### 6) Disable vendored fallback behavior when possible

If a project silently fetches bundled copies via `FetchContent` or a vendored library path, prefer:

1. making `find_package()` succeed,
2. setting `FETCHCONTENT_FULLY_DISCONNECTED` or related flags,
3. patching the upstream build system to stop vendoring in favor of Spack dependencies.

This keeps the package traceable, inspectable, and consistent with the rest of the ecosystem.

## Practical guidance for contributors

- Follow the QSC packaging best practices before writing or modifying a package.
- Prefer small, reviewable patches over large local rewrites.
- Preserve compatibility across laptops, CI, and HPC target systems.
- Keep the dependency graph explicit and transparent in each Spack recipe.
- Treat the package repository as infrastructure for a shared scientific software stack, not as a place to hide private build logic.

## Current status

This repo is intentionally lightweight and growing. It exists as a package registry and packaging guidance source for quantum HPC software, with future work expected to add more concrete environment definitions for specific HPC systems.
