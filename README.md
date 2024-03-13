# figshare

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
    --dataset_title=DATASET_TITLE
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
        Default: 15ffml
```
```shell
# To use the command line, one have to paste token into ~/.figshare/token

```

# More informations
pip install git+https://github.com/cognoma/figshare.git
https://help.figshare.com/article/how-to-use-the-figshare-api
https://colab.research.google.com/drive/13CAM8mL1u7ZsqNhfZLv7bNb1rdhMI64d?usp=sharing#scrollTo=affected-source
