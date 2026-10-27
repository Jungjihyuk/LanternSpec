"""LanternSpec — illuminate the unknown, show the path taken."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("lanternspec")  # pyproject.toml is the only source of the version — read the value copied at install time
except PackageNotFoundError:  # imported straight from a source folder without installing
    __version__ = "0+unknown"
