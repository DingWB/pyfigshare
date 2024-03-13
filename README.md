# Installation
pip install git+https://github.com/DingWB/pyfigshare.git

# or
pip install pyfigshare

# Usage
## (1). setup token
Login to https://figshare.com, create account, click profile -> Applications -> Create Personal Tokens
```
mkdir -p ~/.figshare
vim ~/.figshare/token
# paste the personal token in ~/.figshare/token
```
Alternatively, instead paste the token into ~/.figshare/token, one can also pass parameter token to Figshare class.

## (2). Create article and upload files onto figshare
```shell
figshare upload -h
```
```text
INFO: Showing help with the command 'figshare upload -- --help'.

NAME
    figshare upload

SYNOPSIS
    figshare upload <flags>

FLAGS
    -i, --input_path=INPUT_PATH
        Default: './'
    --title=DATASET_TITLE
        Default: 'title'
    --description=DESCRIPTION
        Default: 'description'
    --token=TOKEN
        Type: Optional[]
        Default: None
    -o, --output=OUTPUT
        Default: 'figshare.tsv'
    -r, --rewrite=REWRITE
        Default: False
    --threshold=THRESHOLD
        Default: 15
```
```shell
# To use the command line, one have to paste token into ~/.figshare/token
figshare upload -i test_data/ --title test1
# upload folder test_data onto figshare and give a title "test1"
```

## (3) Get private or public article information 
### List private or public article file names
```shell
figshare get_filenames 9273710
```
```text
Listing files for article 9273710:
  16871153 - pone.0220029.s001.pdf
  16871156 - pone.0220029.s002.pdf
```
### List article detail information
```shell
figshare Figshare --private False get_article -h
```
```text
INFO: Showing help with the command 'figshare Figshare --private False get_article -- --help'.

NAME
    figshare Figshare --private False get_article

SYNOPSIS
    figshare Figshare --private False get_article ARTICLE_ID <flags>

POSITIONAL ARGUMENTS
    ARTICLE_ID

FLAGS
    -v, --version=VERSION
        Type: Optional[]
        Default: None
    -p, --private=PRIVATE
        Type: Optional[]
        Default: None

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
```

```shell
figshare Figshare --private False get_article 9273710
```

## (3) delete article
### delete article with given article id
```shell
figshare Figshare --private True delete_article <article_id>
```

### delete article with given title
```shell
figshare Figshare --private True delete_articles_with_title test1
```

## (4) download all files for a given article id
```shell
figshare download 9273710 -o downlnoaded_data
```

## Other functions
```shell
figshare Figshare --private True -h
```

```text
INFO: Showing help with the command 'figshare Figshare --private True - -- --help'.

NAME
    figshare Figshare --private True

SYNOPSIS
    figshare Figshare --private True - GROUP | COMMAND | VALUE

GROUPS
    GROUP is one of the following:

     dict_attrs

     list_attrs

     valid_attrs

     value_attrs

COMMANDS
    COMMAND is one of the following:

     author

     complete_upload

     create_article
       Create a new article with attributes (see: https://docs.figsh.com/#private_article_create for detail), for example

     delete_article

     delete_articles_with_title

     delete_file

     download_article

     get_account_info

     get_article

     get_author_id

     get_file_check_data

     get_file_details
       Get the details about a file associated with a given article.

     get_used_quota_private

     initiate_new_upload

     issue_request

     list_article_versions

     list_articles

     list_files

     publish

     raw_issue_request

     search_articles

     update_article

     upload

     upload_part

     upload_parts

VALUES
    VALUE is one of the following:

     baseurl

     private
       whether to read or write private article, set to False if downloading public articles.

     token
       if token has already been written to ~/.figshare/token, this parameter can be ignored.

     token_path
```

# More information
pip install git+https://github.com/cognoma/figshare.git
https://help.figshare.com/article/how-to-use-the-figshare-api
https://colab.research.google.com/drive/13CAM8mL1u7ZsqNhfZLv7bNb1rdhMI64d?usp=sharing#scrollTo=affected-source
