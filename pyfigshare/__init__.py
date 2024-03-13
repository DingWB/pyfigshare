import os,sys
import fire
from .figshare import (
	Figshare,upload,get_filenames,download
)
from ._version import version as __version__

def main():
    fire.core.Display = lambda lines, out: print(*lines, file=out)
    fire.Fire(
		{
			"upload": upload,
			'Figshare': Figshare,
			'download':download,
			'get_filenames':get_filenames,
		}
	)

if __name__=="__main__":
    main()
