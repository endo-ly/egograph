"""EgoGraph - プライバシーファーストの個人データ集約およびRAGシステム。"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("egograph-ingest")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"
