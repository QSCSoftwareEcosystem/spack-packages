# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack_repo.builtin.build_systems.python import PythonPackage

from spack.package import *


class PyArqsim(PythonPackage):
    """System-level evaluation of fault-tolerant quantum architectures.

    ArqSim estimates execution time, physical-qubit footprint, and modeled
    success probability for synthesized logical circuits, including resource
    production, communication, waiting, and contention.
    """

    homepage = "https://github.com/QuTone/ArqSim"
    # The PyPI project named arqsim is unrelated; use the upstream release tag.
    url = "https://github.com/QuTone/ArqSim/archive/refs/tags/v0.2.0.tar.gz"

    maintainers("x8fangQ")

    license("Apache-2.0", checked_by="x8fangQ")

    version("0.2.0", sha256="1a588b54ec53c576b570f9a2287eb46f716f02c0a0854fe92ca9bcf22505615f")

    variant("visualization", default=False, description="Enable Matplotlib plotting helpers")

    depends_on("python@3.10:", type=("build", "run"))
    depends_on("py-setuptools@77:", type="build")

    depends_on("py-networkx@2.6:", type=("build", "run"))
    depends_on("py-pyyaml@5.4:", type=("build", "run"))
    depends_on("py-qiskit@1:", type=("build", "run"))
    depends_on("py-matplotlib@3.7:", when="+visualization", type=("build", "run"))

    @property
    def skip_modules(self):
        # Plotting imports require the optional Matplotlib dependency.
        return [] if "+visualization" in self.spec else ["arqsim.visualization"]

    def test_evaluation(self):
        """Evaluate a Clifford+T circuit using installed architecture/model data."""
        self.spec["python"].command(
            "-c",
            """
from pathlib import Path
from tempfile import TemporaryDirectory

from arqsim import EvaluationConfig, run_evaluation
from arqsim.program import load_ft_workload

with TemporaryDirectory() as directory:
    workload = Path(directory) / "small.qasm"
    workload.write_text('''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
s q[0];
cx q[0],q[1];
t q[1];
''', encoding="utf-8")
    circuit = load_ft_workload(workload, representation="gate")
    report = run_evaluation(circuit, EvaluationConfig(profile_id="2.3"))

assert report.summary.total_latency_s > 0
assert report.summary.total_physical_qubits > 0
assert 0 < report.summary.success_probability <= 1
assert report.summary.fidelity_complete_coverage
assert report.summary.all_invariants_satisfied
print("ArqSim evaluation passed")
""",
        )

    def test_cli(self):
        """Check that the installed command-line entry point is available."""
        Executable(self.prefix.bin.arqsim)("--help")
