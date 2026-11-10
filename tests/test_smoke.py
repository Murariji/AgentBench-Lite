"""Smoke tests: prove the package is installed and importable.

A "smoke test" is the simplest possible check that something works at all.
"""

from importlib.metadata import version

import agentbench


def test_package_imports_and_has_version():
    assert isinstance(agentbench.__version__, str)
    assert agentbench.__version__ != ""


def test_package_is_installed():
    # importlib.metadata only knows about *installed* distributions.
    # If `pip install -e .` was not run, this raises PackageNotFoundError.
    installed_version = version("agentbench-lite")
    assert installed_version == agentbench.__version__
