import os,sys
import fire
from .figshare import (
	upload,list_files,download,Figshare
)
from ._version import version as __version__

def main():
    fire.core.Display = lambda lines, out: print(*lines, file=out)
    fire.Fire({
		'upload':upload,'list_files':list_files,'download':download,
		'Figshare':Figshare,
	},serialize=lambda x:print(x) if not x is None else print("")
	)

if __name__=="__main__":
    main()
