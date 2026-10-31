"""Smoke test: the package can be imported and exposes a version."""

import contribution_tool


def test_package_has_version():
    assert isinstance(contribution_tool.__version__, str)
    assert contribution_tool.__version__ != ""
