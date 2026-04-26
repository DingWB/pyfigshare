import sys
from .figshare import (
	upload, list_files, download, Figshare,
)
from .cli import main, build_parser

try:
	from ._version import version as __version__
except ImportError:  # source checkout without setuptools_scm-generated _version.py
	__version__ = "0.0.0+unknown"

__all__ = [
	"Figshare",
	"upload",
	"download",
	"list_files",
	"main",
	"build_parser",
	"__version__",
]

if __name__ == "__main__":
	sys.exit(main())
