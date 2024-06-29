import os,sys
import fire
from .figshare import (
	search_articles,upload,show_files,download,get_account_info,
	publish,get_file_details,list_article_versions,
	delete_articles_with_title,delete_all_files,
	delete_file,delete_article,list_articles
)
from ._version import version as __version__

def main():
    fire.core.Display = lambda lines, out: print(*lines, file=out)
    fire.Fire(serialize=lambda x:print(x) if not x is None else print(""))

if __name__=="__main__":
    main()
