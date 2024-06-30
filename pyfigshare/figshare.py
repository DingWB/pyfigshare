# -*- coding: utf-8 -*-
"""
@author: DingWB
"""
import hashlib
import json
import glob
import requests
from requests.exceptions import HTTPError
import os,sys
import pandas as pd
from urllib.request import urlretrieve
import fire
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from loguru import logger
logger.level = "INFO"
lock_file=os.path.expanduser("~/.figshare/.lock")
BASE_URL = "https://api.figshare.com/v2/{endpoint}"
VALUE_ATTRS = ['title', 'description', 'is_metadata_record', 'metadata_reason',
			   'defined_type', 'funding', 'license', 'doi', 'handle', 'resource_doi',
			   'resource_title', 'group_id']
LIST_ATTRS = ['tags', 'keywords', 'references', 'related_materials', 'categories',
			  'categories_by_source_id', 'authors',
			  'custom_fields_list', 'funding_list']
DICT_ATTRS = ['custom_fields', 'timeline']
VALID_ATTRS=VALUE_ATTRS+LIST_ATTRS+DICT_ATTRS
MAX_QUOTA=20
global TOKEN,CHUNK_SIZE,THRESHOLD
CHUNK_SIZE=20
THRESHOLD=15
if os.path.exists(os.path.expanduser("~/.figshare/token")):
	with open(os.path.expanduser("~/.figshare/token"), 'r') as f:
		TOKEN = f.read().strip()
else:
	raise ValueError("Please write figshare token to ~/.figshare/token")

def raw_issue_request(method, url, data=None, binary=False):
	headers = {'Authorization': 'token ' + TOKEN}
	if data is not None and not binary:
		data = json.dumps(data)
	response = requests.request(method, url, headers=headers, data=data)
	try:
		response.raise_for_status()
		try:
			data = json.loads(response.content)
		except ValueError:
			data = response.content
	except HTTPError as error:
		logger.warning(error)
		logger.info('Body:\n', response.content)
		raise
	return data

def issue_request(method, endpoint, *args, **kwargs):
	return raw_issue_request(method, BASE_URL.format(endpoint=endpoint), *args, **kwargs)

def get_article(article_id, version=None,private=False):
	if version is None:
		if private:
			endpoint='account/articles/{}'.format(article_id)
		else:
			endpoint='articles/{}'.format(article_id)
	else:
		if private:
			endpoint='account/articles/{}/versions/{}'.format(article_id,version)
		else:
			endpoint = 'articles/{}/versions/{}'.format(article_id,version)
	result = issue_request('GET', endpoint)
	return result

def list_files(article_id,version=None, private=False,show=True):
	if version is None:
		if private:
			endpoint="account/articles/{}/files".format(article_id)
		else:
			endpoint="articles/{}/files".format(article_id)
		result = issue_request('GET', endpoint)
		if show:
			logger.info('Listing files for article {}:'.format(article_id))
		if result:
			for item in result:
				if show:
					logger.info('  {id} - {name}'.format(**item))
		else:
			if show:
				logger.warning('  No files.')
		return result
	else:
		request = get_article(article_id, version)
		return request['files']

def list_articles(show=False):
	result = issue_request('GET', "account/articles")
	if show:
		logger.info('Listing current articles:')
		if result:
			for item in result:
				logger.info(u'  {url} - {title}'.format(**item))
		else:
			logger.warning("No articles found.")
	return result

def search_articles(private=True,title=None,**kwargs):
	if private:
		articles=list_articles()
		R = []
		for article in articles:
			if article['title'] == title:
				R.append(article)
	else:
		kwargs['title']=title
		data={}
		invalid_keys = []
		for key in kwargs:
			if key in VALID_ATTRS:
				if key in LIST_ATTRS:
					if not isinstance(kwargs[key], list):
						raise TypeError(
							f"{key} should be a list,see https://docs.figsh.com/#private_article_create for detail.")
				if key in DICT_ATTRS:
					if not isinstance(kwargs[key], dict):
						raise TypeError(
							f"{key} should be a dict, see https://docs.figsh.com/#private_article_create for detail.")
				data[key] = kwargs[key]
			else:
				invalid_keys.append(key)
		if len(invalid_keys) > 0:
			logger.warning(f"Those keys were invalid: {invalid_keys} and will be ignored")
		R = issue_request('POST', 'articles/search',data=data)
	return R

def create_article(**kwargs):
	"""
	Create a new article with attributes (see: https://docs.figsh.com/#private_article_create
		for detail), for example:
		{
			  "title": "Test article title",
			  "description": "Test description of article",
			  "is_metadata_record": true,
			  "metadata_reason": "hosted somewhere else",
			  "tags": [
				"tag1",
				"tag2"
			  ],
			  "keywords": [
				"tag1",
				"tag2"
			  ],
			  "references": [
				"http://figshare.com",
				"http://api.figshare.com"
			  ],
			  "related_materials": [
				{
				  "id": 10432,
				  "identifier": "10.6084/m9.figshare.1407024",
				  "identifier_type": "DOI",
				  "relation": "IsSupplementTo",
				  "title": "Figshare for institutions brochure",
				  "is_linkout": false
				}
			  ],
			  "categories": [
				1,
				10,
				11
			  ],
			  "categories_by_source_id": [
				"300204",
				"400207"
			  ],
			  "authors": [
				{
				  "name": "John Doe"
				},
				{
				  "id": 1000008
				}
			  ],
			  "custom_fields": {
				"defined_key": "value for it"
			  },
			  "custom_fields_list": [
				{
				  "name": "key",
				  "value": "value"
				}
			  ],
			  "defined_type": "media",
			  "funding": "",
			  "funding_list": [
				{
				  "id": 0,
				  "title": "string"
				}
			  ],
			  "license": 1,
			  "doi": "",
			  "handle": "",
			  "resource_doi": "",
			  "resource_title": "",
			  "timeline": {
				"firstOnline": "2015-12-31",
				"publisherPublication": "2015-12-31",
				"publisherAcceptance": "2015-12-31"
			  },
			  "group_id": 0
			}
	Parameters
	----------
	args :

	Returns
	-------

	"""
	data = {}
	kwargs.setdefault('title', 'title')
	kwargs.setdefault('categories_by_source_id',['310204'])
	kwargs.setdefault('tags',['dataset based'])
	kwargs.setdefault('description', kwargs['title'])
	invalid_keys=[]
	for key in kwargs:
		if key in VALID_ATTRS:
			if key in LIST_ATTRS:
				if not isinstance(kwargs[key],list):
					raise TypeError(f"{key} should be a list,see https://docs.figsh.com/#private_article_create for detail.")
			if key in DICT_ATTRS:
				if not isinstance(kwargs[key],dict):
					raise TypeError(f"{key} should be a dict, see https://docs.figsh.com/#private_article_create for detail.")
			data[key]=kwargs[key]
		else:
			invalid_keys.append(key)
	if len(invalid_keys) > 0:
		logger.warning(f"Those keys were invalid: {invalid_keys} and will be ignored")

	result = issue_request('POST', 'account/articles', data=data)
	logger.info('Created article:', result['location'], '\n')
	result = raw_issue_request('GET', result['location'])
	return result['id']

def delete_article(article_id):
	result = issue_request('DELETE',
								'account/articles/{}'.format(article_id))
	return result

def delete_file(article_id, file_id,private=False):
	if private:
		endpoint='account/articles/{0}/files/{1}'.format(article_id, file_id)
	else:
		endpoint='articles/{0}/files/{1}'.format(article_id, file_id)
	result = issue_request('DELETE',endpoint)
	return result

def delete_all_files(article_id,private=False,version=None):
	files=list_files(article_id,version=version, private=private,show=False)
	for file in files:
		file_id=file['id']
		logger.info(f"Deleting file: {file['name']}")
		delete_file(article_id,file_id,private=private)

def delete_folder(article_id, folder_name,version=None,private=False):
	if not folder_name.endswith('/'):
		folder_name=folder_name+'/'
	files = list_files(article_id, version=version, private=private, show=False)
	for file in files:
		file_id = file['id']
		file_name=file['name']
		if not file_name.startswith(folder_name):
			continue
		logger.info(f"deleting file {file_name}")
		delete_file(article_id, file_id, private=private)

def delete_articles_with_title(title,private=True):
	articles=search_articles(title=title,private=private)
	for article in articles:
		delete_article(article['id'])

def update_article(article_id, **kwargs):
	allowed = VALID_ATTRS
	valid_keys = set(kwargs.keys()).intersection(allowed)
	body = {}
	for key in valid_keys:
		body[key] = kwargs[key]
	result = issue_request('PUT', 'account/articles/{}'.format(article_id),
								data=json.dumps(body))
	return result

def list_article_versions(article_id, private=False):
	if private:
		raise ValueError("Not supported for private")
	else:
		endpoint='articles/{}/versions'.format(article_id)
	response = issue_request('GET', endpoint)
	return response

def get_file_details(article_id, file_id,private=False):
	""" Get the details about a file associated with a given article.

	Parameters
	----------
	article_id : str or int
		Figshare article ID

	file_id : str or int
		File id

	Returns
	-------
	response : dict
		HTTP request response as a python dict

	"""
	if private:
		endpoint='account/articles/{0}/files/{1}'.format(article_id, file_id)
	else:
		endpoint='articles/{0}/files/{1}'.format(article_id, file_id)
	response = issue_request('GET', endpoint)
	return response

def get_file_check_data( file_name):
	global CHUNK_SIZE
	with open(file_name, 'rb') as fin:
		md5 = hashlib.md5()
		size = 0
		data = fin.read(CHUNK_SIZE)
		while data:
			size += len(data)
			md5.update(data)
			data = fin.read(CHUNK_SIZE)
		return md5.hexdigest(), size

def unlock():
	if os.path.exists(lock_file):
		logger.debug("unlocking...")
		os.remove(lock_file)  # unlock

def lock():
	os.system(f"touch {lock_file}")
	logger.debug("Locked..")

def initiate_new_upload(article_id, file_path,folder_name=None):
	global THRESHOLD
	basename = os.path.basename(file_path) #.replace(' ','_')
	if not folder_name is None:
		name = f"{folder_name}/{basename}"
	else:
		name = basename
	endpoint = 'account/articles/{}/files'
	endpoint = endpoint.format(article_id)
	md5, size = get_file_check_data(file_path)
	if size == 0:
		logger.info(f"File size is 0, skipped: {file_path}")
		return False
	if size/1024/1024/1024 > MAX_QUOTA:
		logger.error(f"single file must be < 20G, see file: {file_path}")
		return False
	# check whether there is enough quota before initiating new upload
	quota_used=get_used_quota()
	if quota_used > THRESHOLD or quota_used+size/1024/1024/1024 > MAX_QUOTA:
		logger.info(f"used quota is {quota_used}, try to publish article.")
		try:
			result=publish(article_id) # publish article
			unlock() #if publish successfully then unlock
		except:
			logger.debug("Failed to publish, wait for other processer to be finished")
			lock()
			# print(f"article_id:{article_id}")
	while os.path.exists(lock_file):
		time.sleep(30)
	data = {'name':name,'md5': md5,'size': size}
	try:
		result = issue_request('POST', endpoint, data=data)
	except:
		logger.debug(f"Unknown error for: file_path: {file_path}, name: {name}, size: {size}")
	# logger.info('Initiated file upload:', result['location'], '\n')
	result = raw_issue_request('GET', result['location'])
	return result

def complete_upload(article_id, file_id):
	issue_request('POST', 'account/articles/{}/files/{}'.format(article_id, file_id))
	try:
		result = publish(article_id)  # publish article
		unlock()  # if publish successfully then unlock
	except:
		pass

def upload_parts(file_path, file_info):
	url = '{upload_url}'.format(**file_info)
	result = raw_issue_request('GET', url)
	# print('Uploading parts:')
	with open(file_path, 'rb') as fin:
		for part in result['parts']:
			upload_part(file_info, fin, part)

def upload_part(file_info, stream, part):
	udata = file_info.copy()
	udata.update(part)
	url = '{upload_url}/{partNo}'.format(**udata)
	stream.seek(part['startOffset'])
	data = stream.read(part['endOffset'] - part['startOffset'] + 1)
	raw_issue_request('PUT', url, data=data, binary=True)
	# print(' Uploaded part {partNo} from {startOffset} to {endOffset}'.format(**part))

def upload_worker(article_id, file_path,folder_name=None):
	# Then we upload the file.
	try:
		file_info = initiate_new_upload(article_id, file_path,folder_name)
	except:
		logger.error(f"Error for file: {file_path}, skipped..")
		return None
	if file_info==False:
		return None
	logger.info(file_path)
	# Until here we used the figshare API; following lines use the figshare upload service API.
	upload_parts(file_path,file_info)
	# We return to the figshare API to complete the file upload process.
	complete_upload(article_id, file_info['id'])
	# list_files(article_id)

def prepare_upload_folder(article_id, file_path,pre_folder_name=None): #file_path is a directory
	# logger.debug(f"dir: {file_path}")
	global EXITED_FILES
	assert os.path.isdir(file_path), 'file_path must be a folder'
	folder_name = os.path.basename(file_path)
	if not pre_folder_name is None:
		cur_folder_name=f"{pre_folder_name}/{folder_name}"
	else:
		cur_folder_name=folder_name
	logger.info(cur_folder_name)
	for file in os.listdir(file_path):
		new_file_path=os.path.join(file_path,file)
		if os.path.isfile(new_file_path):
			basename = os.path.basename(new_file_path)  # .replace(' ','_')
			name = f"{cur_folder_name}/{basename}"
			if name in EXITED_FILES:
				logger.info(f"File existed, skipped: {new_file_path}")
			else:
				# upload_file(article_id, new_file_path,cur_folder_name)
				yield [new_file_path,cur_folder_name]
		elif os.path.isdir(new_file_path): # new file path is still a folder, level 2 folder.
			yield from prepare_upload_folder(article_id, new_file_path,cur_folder_name)
		else:
			logger.warning(f"{new_file_path} is not dir, neither file, not recognized")

def prepare_upload_file_path(article_id, file_path):
	global EXITED_FILES
	if os.path.isdir(file_path):
		yield from prepare_upload_folder(article_id, file_path)
	elif os.path.isfile(file_path): #file
		name = os.path.basename(file_path) #folder name is None
		if name in EXITED_FILES:
			logger.info(f"File existed, skipped: {file_path}")
		else:
			# upload_file(article_id, file_path)
			yield [file_path, None]
	else:
		logger.warning(f"{file_path} is not dir, neither file, not recognized")

def prepare_upload(article_id, input_files):
	global EXITED_FILES
	res = list_files(article_id, show=False)
	EXITED_FILES = [r['name'] for r in res]
	logger.debug(EXITED_FILES)
	for file_path in input_files:
		yield from prepare_upload_file_path(article_id, file_path)

def publish(article_id):
	endpoint = 'account/articles/{}/publish'.format(article_id)
	result = issue_request('POST', endpoint)
	return result

def get_author_id(article_id):
	res=get_article(article_id)
	return res['authors'][0]['id']

def author(author_id):
	endpoint = 'account/authors/{}'.format(author_id)
	result = issue_request('GET', endpoint)
	return result

def get_account_info():
	result = issue_request('GET', '/account')
	return result

def get_used_quota():
	result=get_account_info()
	return result['used_quota_private'] / 1024 / 1024 / 1024

def download_worker(url,path):
	dirname = os.path.dirname(path)
	if not os.path.exists(dirname):
		os.makedirs(dirname, exist_ok=True)
	if os.path.exists(path):
		logger.info(f"{path} existed")
		return path
	urlretrieve(url, path)
	return path

def download(article_id, outdir="./",cpu=1,folder=None):
	outdir=os.path.abspath(os.path.expanduser(outdir))
	# Get list of files
	file_list = list_files(article_id,show=False)
	os.makedirs(outdir, exist_ok=True) # This might require Python >=3.2
	if cpu==1:
		for file_dict in file_list:
			if not folder is None and folder!=file_dict['name'].split('/')[0]:
				continue
			path=os.path.join(outdir, file_dict['name'])
			dirname= os.path.dirname(path)
			if not os.path.exists(dirname):
				os.makedirs(dirname,exist_ok=True)
			if os.path.exists(path):
				logger.info(f"{path} existed")
				continue
			logger.info(file_dict['name'])
			urlretrieve(file_dict['download_url'], path)
	else:
		with ProcessPoolExecutor(cpu) as executor:
			futures = {}
			for file_dict in file_list:
				if not folder is None and folder!=file_dict['name'].split('/')[0]:
					continue
				future = executor.submit(
					download_worker,
					url=file_dict['download_url'],
					path=os.path.join(outdir, file_dict['name'])
				)
				futures[future] = file_dict['name']

			for future in as_completed(futures):
				file_name = futures[future]
				path = future.result()
				logger.info(file_name)

def upload(
	input_path="./",
	title='title', description='description',
	output="figshare.tsv",
	threshold=15,chunk_size=20,
	level='INFO',cpu=1,target_folder=None):
	"""
	Upload files or directory to figshare

	Parameters
	----------
	input_path : str
		folder name, or single file path, or file pattern passed to glob (should be
		quote using "", and * must be included).
	title : str
		article title, if not existed this article, it will be created.
	description : str
		article description.
	output : path
		After the uploading is finished, the file id,url and filename will be
		written into this output file.
	rewrite : bool
		whether to overwrite the files on figshare if existed.
	threshold : int [GB]
		There is only 20 GB availabel for private storage, when uploading a
		big datasets (>20Gb), if the total quota usage is grater than  this
		threshold, the article will be published so that the 20GB usaged quata
		will be reset to 0.
	chunk_size: int
		chunk size for uploading [20 MB]
	level: str
		loguru log level: DEBUG, INFO, WARNING, ERROR
	cpu: int
	target_folder:str
		upload the input_path to the target_folder under article

	Returns
	-------

	"""
	global CHUNK_SIZE,THRESHOLD,logger
	CHUNK_SIZE=chunk_size
	THRESHOLD=threshold
	logger.level = level
	input_path = os.path.abspath(os.path.expanduser(input_path))
	if "*" not in input_path and os.path.isdir(input_path):
		input_files=[os.path.join(input_path,file) for file in os.listdir(input_path)] # including file and folder
	elif "*" in input_path:
		input_files=glob.glob(input_path)
	else:
		input_files=[input_path]
	r = search_articles(title=title,private=True)
	if len(r) == 0:
		logger.info(f"article: {title} not found, create it")
		article_id = create_article(title=title, description=description)
	else:
		logger.info(f"found existed article")
		article_id = r[0]['id'] #article id
	unlock() #unlock
	if target_folder.endswith('/'):
		target_folder=target_folder[:-1]
	if cpu == 1:
		for file_path,folder_name in prepare_upload(article_id, input_files):
			if not target_folder is None:
				folder_name=f"{target_folder}/{folder_name}" if not folder_name is None else target_folder
			upload_worker(article_id, file_path,folder_name)
	else:
		with ProcessPoolExecutor(cpu) as executor:
			futures = {}
			for file_path,folder_name in prepare_upload(article_id, input_files):
				if not target_folder is None:
					folder_name = f"{target_folder}/{folder_name}" if not folder_name is None else target_folder
				future = executor.submit(
					upload_worker,
					article_id=article_id, file_path=file_path,
					folder_name=folder_name,
				)
				futures[future] = file_path

			for future in as_completed(futures):
				file_name = futures[future]
				path = future.result()
				logger.info(file_name)
	publish(article_id) #publish article after the uploading is done.
	show_files(article_id, private=False, output=os.path.expanduser(output))
	logger.info(f"See {output} for the detail information of the uploaded files")

def show_files(article_id,private=False,version=None,output=None):
	"""
	Get all files id, url and filenames for a given article id.

	Parameters
	----------
	article_id : int
		figshare article id, for example, article id for this public article:
		https://figshare.com/articles/dataset/9273710 is 9273710.
	private : bool
		whether this is a private article or not.
	output : path
		write the filenames, url and file id into this output.

	Returns
	-------

	"""
	res = list_files(article_id,version=version,private=private,show=False)
	R = []
	for r in res:
		url = "https://figshare.com/ndownloader/files/" + str(r['id'])
		R.append([r['name'], r['id'], url])
	df = pd.DataFrame(R, columns=['file', 'file_id', 'url'])
	if not output is None:
		df.to_csv(output, sep='\t', index=False)
	else:
		sys.stdout.write('\t'.join([str(i) for i in df.columns.tolist()]) + '\n')
		for i, row in df.iterrows():
			try:
				sys.stdout.write('\t'.join([str(i) for i in row.tolist()]) + '\n')
			except:
				sys.stdout.close()

if __name__ == "__main__":
	fire.core.Display = lambda lines, out: print(*lines, file=out)
	fire.Fire(serialize=lambda x:print(x) if not x is None else print(""))