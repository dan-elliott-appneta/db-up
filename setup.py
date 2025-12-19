"""Backwards compatibility shim for older pip versions.

Modern pip uses pyproject.toml directly. This file exists only
for compatibility with pip versions < 21.3 that don't fully
support PEP 517/518 builds.
"""
from setuptools import setup

if __name__ == "__main__":
    setup()
