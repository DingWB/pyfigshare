import os,sys
import fire
from .figshare import (
	search_articles,upload,show_files,download,get_account_info,
	publish,get_file_details,list_article_versions,
	delete_articles_with_title,delete_all_files,
	delete_file,delete_article,list_articles,upload_worker
)
from ._version import version as __version__

def main():
    fire.core.Display = lambda lines, out: print(*lines, file=out)
    fire.Fire({
		'search_articles':search_articles,
		'upload':upload,'show_files':show_files,'download':download,
		'get_file_details':get_file_details,'list_article_versions':list_article_versions,
		'delete_articles_with_title':delete_articles_with_title,
		'delete_all_files':delete_all_files,'delete_file':delete_file,
		'delete_article':delete_article,'list_articles':list_articles,
		'upload_worker':upload_worker,
	},serialize=lambda x:print(x) if not x is None else print("")
	)

if __name__=="__main__":
    main()
