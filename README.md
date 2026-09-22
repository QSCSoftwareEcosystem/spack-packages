# Quantum Science Center Spack repository

This repository is for rapid development and deployment of quantum
science software using the [Spack HPC package manager](https://spack.readthedocs.io/en/latest/).

# Usage

Currently this project is just getting started so it's assumed you're on the SE
team developing a new package.

## Adding this package repository to Spack

Assuming you have already set up Spack (see [the Spack getting started page](https://spack.readthedocs.io/en/latest/getting_started.html)):

```sh
$ spack repo add https://github.com/QSCSoftwareThrust/spack-packages.git
```

This clones the repository to your local spack package repo: you can find the
location with `spack location --repo` or `spack repo list`. You can treat it
like a normal git repository.

## Creating a new package

Follow the [spack packaging guidelines](https://spack.readthedocs.io/en/latest/packaging_guide_creation.html), but use the `-N qsc` flag to `spack create` to indicate the new package belongs in this repository.

For Python packages specifically, see
[docs/python-packaging-best-practices.md](docs/python-packaging-best-practices.md)
for guidance on CMake integration, virtual environments, and avoiding vendored
dependencies across GPU/QPU target platforms.

## Installing a QSC package

To be added.

# Environments

Future work will add concrete environments for relevant HPC and QHPC systems.
