import os,sys
import fire
from .figshare import (
	Figshare,upload,list_files,download
)
from ._version import version as __version__

def main():
    fire.core.Display = lambda lines, out: print(*lines, file=out)
    fire.Fire(
		{
			"upload": upload,
			'Figshare': Figshare,
			'download':download,
			'list_files':list_files,
		}
	)

if __name__=="__main__":
    main()
