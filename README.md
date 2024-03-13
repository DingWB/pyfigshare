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
        Default: 15ffml
```
```shell
# To use the command line, one have to paste token into ~/.figshare/token
figshare upload -i test_data/ --title test1
# upload folder test_data onto figshare and give a title "test1"
```

## (3) Get private or public article ifnormation 
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
```text
files:               [{"id": 16871153, "name": "pone.0220029.s001.pdf", "size": 337156, "is_link_only": false, "download_url": "https://ndownloader.figshare.com/files/16871153", "supplied_md5": "9ff7376f5cb1c3a3290b1e65e61ed9a5", "computed_md5": "9ff7376f5cb1c3a3290b1e65e61ed9a5", "mimetype": "application/pdf"}, {"id": 16871156, "name": "pone.0220029.s002.pdf", "size": 323724, "is_link_only": false, "download_url": "https://ndownloader.figshare.com/files/16871156", "supplied_md5": "ac0113f2c5b8f6a5f7a46791b691d066", "computed_md5": "ac0113f2c5b8f6a5f7a46791b691d066", "mimetype": "application/pdf"}]
custom_fields:       []
authors:             [{"id": 7140029, "full_name": "Michael DiBartolomeis", "is_active": false, "url_name": "_", "orcid_id": ""}, {"id": 7140032, "full_name": "Susan Kegley", "is_active": false, "url_name": "_", "orcid_id": ""}, {"id": 325079, "full_name": "Pierre Mineau", "is_active": false, "url_name": "_", "orcid_id": ""}, {"id": 4373767, "full_name": "Rosemarie Radford", "is_active": false, "url_name": "_", "orcid_id": ""}, {"id": 7140035, "full_name": "Kendra Klein", "is_active": false, "url_name": "_", "orcid_id": ""}]
figshare_url:        https://plos.figshare.com/articles/dataset/An_assessment_of_acute_insecticide_toxicity_loading_AITL_of_chemical_pesticides_used_on_agricultural_land_in_the_United_States/9273710
download_disabled:   false
description:         <div><p>We present a method for calculating the Acute Insecticide Toxicity Loading (AITL) on US agricultural lands and surrounding areas and an assessment of the changes in AITL from 1992 through 2014. The AITL method accounts for the total mass of insecticides used in the US, acute toxicity to insects using honey bee contact and oral LD<sub>50</sub> as reference values for arthropod toxicity, and the environmental persistence of the pesticides. This screening analysis shows that the types of synthetic insecticides applied to agricultural lands have fundamentally shifted over the last two decades from predominantly organophosphorus and N-methyl carbamate pesticides to a mix dominated by neonicotinoids and pyrethroids. The neonicotinoids are generally applied to US agricultural land at lower application rates per acre; however, they are considerably more toxic to insects and generally persist longer in the environment. We found a 48- and 4-fold increase in AITL from 1992 to 2014 for oral and contact toxicity, respectively. Neonicotinoids are primarily responsible for this increase, representing between 61 to nearly 99 percent of the total toxicity loading in 2014. The crops most responsible for the increase in AITL are corn and soybeans, with particularly large increases in relative soybean contributions to AITL between 2010 and 2014. Oral exposures are of potentially greater concern because of the relatively higher toxicity (low LD<sub>50</sub>s) and greater likelihood of exposure from residues in pollen, nectar, guttation water, and other environmental media. Using AITL to assess oral toxicity by class of pesticide, the neonicotinoids accounted for nearly 92 percent of total AITL from 1992 to 2014. Chlorpyrifos, the fifth most widely used insecticide during this time contributed just 1.4 percent of total AITL based on oral LD<sub>50</sub>s. Although we use some simplifying assumptions, our screening analysis demonstrates an increase in pesticide toxicity loading over the past 26 years, which potentially threatens the health of honey bees and other pollinators and may contribute to declines in beneficial insect populations as well as insectivorous birds and other insect consumers.</p></div>
funding:             null
funding_list:        []
version:             1
status:              public
size:                660880
created_date:        2019-08-06T17:24:11Z
modified_date:       2023-05-31T14:59:37Z
is_public:           true
is_confidential:     false
is_metadata_record:  false
confidential_reason:
metadata_reason:
license:             {"value": 1, "name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}
tags:                ["LD 50", "AITL method accounts", "screening analysis", "N-methyl carbamate pesticides", "honey bee contact", "pesticide toxicity loading", "insecticide toxicity loading", "2014. Oral exposures", "Acute Insecticide Toxicity Loading"]
categories:          [{"id": 13, "title": "Genetics", "parent_id": 48, "path": "", "source_id": "", "taxonomy_id": 10}, {"id": 15, "title": "Neuroscience", "parent_id": 48, "path": "", "source_id": "", "taxonomy_id": 10}, {"id": 21, "title": "Biotechnology", "parent_id": 48, "path": "", "source_id": "", "taxonomy_id": 10}, {"id": 272, "title": "Environmental Sciences not elsewhere classified", "parent_id": 33, "path": "", "source_id": "", "taxonomy_id": 10}, {"id": 873, "title": "Chemical Sciences not elsewhere classified", "parent_id": 38, "path": "", "source_id": "", "taxonomy_id": 10}, {"id": 39, "title": "Ecology", "parent_id": 33, "path": "", "source_id": "", "taxonomy_id": 10}, {"id": 734, "title": "Biological Sciences not elsewhere classified", "parent_id": 48, "path": "", "source_id": "", "taxonomy_id": 10}]
references:          ["https://doi.org/10.1371/journal.pone.0220029"]
has_linked_file:     false
citation:            DiBartolomeis, Michael; Kegley, Susan; Mineau, Pierre; Radford, Rosemarie; Klein, Kendra (2019). An assessment of acute insecticide toxicity loading (AITL) of chemical pesticides used on agricultural land in the United States. PLOS ONE. Dataset. https://doi.org/10.1371/journal.pone.0220029
related_materials:   [{"id": 12063626, "identifier": "10.1371/journal.pone.0220029", "title": "An assessment of acute insecticide toxicity loading (AITL) of chemical pesticides used on agricultural land in the United States", "relation": "IsSupplementTo", "identifier_type": "DOI", "is_linkout": true, "link": "https://doi.org/10.1371/journal.pone.0220029"}]
is_embargoed:        false
embargo_date:        null
embargo_type:        null
embargo_title:
embargo_reason:
embargo_options:     []
id:                  9273710
title:               An assessment of acute insecticide toxicity loading (AITL) of chemical pesticides used on agricultural land in the United States
doi:                 10.1371/journal.pone.0220029
handle:
url:                 https://api.figshare.com/v2/articles/9273710
published_date:      2019-08-06T17:24:11Z
thumb:               https://s3-eu-west-1.amazonaws.com/ppreviews-plos-725668748/16871153/thumb.png
defined_type:        3
defined_type_name:   dataset
group_id:            107
url_private_api:     https://api.figshare.com/v2/account/articles/9273710
url_public_api:      https://api.figshare.com/v2/articles/9273710
url_private_html:    https://figshare.com/account/articles/9273710
url_public_html:     https://plos.figshare.com/articles/dataset/An_assessment_of_acute_insecticide_toxicity_loading_AITL_of_chemical_pesticides_used_on_agricultural_land_in_the_United_States/9273710
timeline:            {"posted": "2019-08-06T17:24:11", "publisherPublication": "2019-08-06T17:24:08", "firstOnline": "2019-08-06T17:24:11"}
resource_title:      An assessment of acute insecticide toxicity loading (AITL) of chemical pesticides used on agricultural land in the United States
resource_doi:        10.1371/journal.pone.0220029
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
       Create a new article with attributes (see: https://docs.figsh.com/#private_article_create for detail), for example: { "title": "Test article title", "description": "Test description of article", "is_metadata_record": true, "metadata_reason": "hosted somewhere else", "tags": [ "tag1", "tag2" ], "keywords": [ "tag1", "tag2" ], "references": [ "http://figshare.com", "http://api.figshare.com" ], "related_materials": [ { "id": 10432, "identifier": "10.6084/m9.figshare.1407024", "identifier_type": "DOI", "relation": "IsSupplementTo", "title": "Figshare for institutions brochure", "is_linkout": false } ], "categories": [ 1, 10, 11 ], "categories_by_source_id": [ "300204", "400207" ], "authors": [ { "name": "John Doe" }, { "id": 1000008 } ], "custom_fields": { "defined_key": "value for it" }, "custom_fields_list": [ { "name": "key", "value": "value" } ], "defined_type": "media", "funding": "", "funding_list": [ { "id": 0, "title": "string" } ], "license": 1, "doi": "", "handle": "", "resource_doi": "", "resource_title": "", "timeline": { "firstOnline": "2015-12-31", "publisherPublication": "2015-12-31", "publisherAcceptance": "2015-12-31" }, "group_id": 0 }

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

# More informations
pip install git+https://github.com/cognoma/figshare.git
https://help.figshare.com/article/how-to-use-the-figshare-api
https://colab.research.google.com/drive/13CAM8mL1u7ZsqNhfZLv7bNb1rdhMI64d?usp=sharing#scrollTo=affected-source
