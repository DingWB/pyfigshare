import fire
from .figshare import *
from ._version import version as __version__

def main():
    fire.core.Display = lambda lines, out: print(*lines, file=out)
    fire.Fire(
        {
            "upload": upload,
            'Figshare': Figshare,
        }
	)

if __name__=="_main__":
    main()