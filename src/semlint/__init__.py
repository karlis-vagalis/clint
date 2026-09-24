"""Semantic redundancy analysis for agent instruction files."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("semlint")
except PackageNotFoundError:
    __version__ = "0.0.0"
