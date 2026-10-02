# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.python import PythonPackage

from spack.package import *


class PyLightstim(PythonPackage):
    """LightStim is a modular Quantum Error Correction (QEC) framework built
    on Stim. It provides high-level abstractions for constructing
    fault-tolerant circuits with automatic detector generation, running
    simulation and decoding pipelines, and comparing logical error rates
    across QEC codes and protocols."""

    homepage = "https://github.com/QuTone/LightStim"
    git = "https://github.com/QuTone/LightStim.git"

    maintainers("x8fangQ")

    license("Apache-2.0", checked_by="x8fangQ")

    version("main", branch="main")
    version("0.1.1", tag="v0.1.1", commit="6ba31f8414d2875fd13205592d38428ff35026df")

    variant("decoders", default=False, description="CPU BP+OSD (stimbposd) and MWPF decoders")

    # Build backend (pyproject: setuptools>=61)
    depends_on("python@3.10:", type=("build", "run"))
    depends_on("py-setuptools@61:", type="build")

    # Core runtime dependencies (pyproject [dependencies])
    depends_on("py-numpy@1.20:", type=("build", "run"))
    depends_on("py-stim@1.15:", type=("build", "run"))
    depends_on("py-sinter@1.15:", type=("build", "run"))
    depends_on("py-pymatching@2:", type=("build", "run"))
    depends_on("py-pandas", type=("build", "run"))

    # Optional decoders (pyproject [decoders] extra)
    depends_on("py-stimbposd", when="+decoders", type=("build", "run"))
    depends_on("py-mwpf", when="+decoders", type=("build", "run"))
