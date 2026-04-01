"""Backend API for EgoGraph."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("egograph-backend")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"
