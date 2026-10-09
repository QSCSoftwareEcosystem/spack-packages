# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.cmake import CMakePackage
from spack.package import *


class Dcapp(CMakePackage):
    """The DCA++ code provides a state of the art implementation of
    the dynamical cluster approximation (DCA) and its DCA++ extension.
    High scalability and portable performance allow to exploit today's
    leadership computing systems.
    """
    homepage = "https://github.com/CompFUSE/DCA"
    url = "https://github.com/CompFUSE/DCA/archive/refs/tags/v2.0.0-alpha3.tar.gz"

    maintainers("PDoakORNL")

    default_version = "2.0.0-alpha3"

    license("BSD-3-Clause", checked_by="PDoakORNL")

    version("2.0.0-alpha3", sha256="82cadf6cb17bb330fafe899ca54948acdeecc9651f37f8fd70595e3bf88a49c9")
    version("master", branch="master", get_full_repo=True)

    depends_on("cmake", type="build")
    depends_on("mpi")
    depends_on("llvm@21.0.0:")
    depends_on("fftw")
    conflicts("^gcc")
    depends_on("openblas threads=none")
    depends_on("hdf5+cxx")

    variant("cuda", default=False, description="enable CUDA support")
    variant("hip", default=False, description="enable HIP support")
    variant("tests_fast", default=False, description="Build DCA++'s fast tests.")
    variant("tests_extensive", default=False, description="Build DCA++'s extensive tests.")
    variant(
        "point_group",
        default="no_symmetry<2>",
        values=("C6", "D4", "no_symmetry<2>", "no_symmetry<3>"),
        description="Point group symmetry",
    )
    variant(
        "lattice",
        default="square",
        values=(
            "bilayer",
            "square",
            "triangular",
            "Kagome",
            "Plaquette",
            "hund",
            "twoband_Cu",
            "threeband",
            "Rashba_Hubbard",
            "Moire_Hubbard",
            "FeAs",
            "material_NiO",
            "material_FeSn",
            "La3Ni2O7_bilayer",
        ),
        description="Lattice type",
    )

    with when("+cuda"):
        depends_on("cuda@12:12.9")

    with when("+hip"):
        depends_on("hip@6.0: +rocm")

    with when("+cuda" or "+hip"):
        depends_on("magma@2.10:")

    def cmake_args(self):
        spec = self.spec
        args = []
        args.append(self.define_from_variant("DCA_WITH_TESTS_FAST", "tests_fast"))
        args.append(self.define_from_variant("DCA_WITH_TESTS_EXTENSIVE", "tests_extensive"))
        args.append(self.define_from_variant("DCA_HAVE_CUDA", "cuda"))
        args.append(self.define_from_variant("DCA_HAVE_HIP", "hip"))
        if "point_group" in spec.variants:
            args.append(self.define("DCA_POINT_GROUP", spec.variants["point_group"].value))
        else:
            args.append(self.define("DCA_POINT_GROUP", "no_symmetry<2>"))
        if "lattice" in spec.variants:
            args.append(self.define("DCA_LATTICE", spec.variants["lattice"].value))
        else:
            args.append(self.define("DCA_LATTICE", "square"))

        if spec.satisfies("+tests_fast") or spec.satisfies("+tests_extensive"):
            args.append(self.define("TEST_RUNNER", "mpiexec"))

        return args
