# -*- coding: utf-8 -*-
"""
@author: DingWB
"""
BASE_URL = 'https://api.figshare.com/v2/{endpoint}'
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

def download_worker(url,path):
	dirname = os.path.dirname(path)
	if not os.path.exists(dirname):
		os.makedirs(dirname, exist_ok=True)
	if os.path.exists(path):
		logger.info(f"{path} existed")
		return path
	urlretrieve(url, path)
	return path

class Figshare:
	def __init__(self, token=None, private=True,
				 chunk_size=20,threshold=18):
		"""
		figshare class

		Parameters
		----------
		token : str
			if token has already been written to ~/.figshare/token,
			this parameter can be ignored.
		private : bool
			whether to read or write private article, set to False if downloading
			public articles.
		chunk_size: int
			chunk size for uploading (in Mb), default is 20MB
		"""
		self.baseurl = "https://api.figshare.com/v2/{endpoint}'"
		self.token_path=os.path.expanduser("~/.figshare/token")
		if token is None:
			if os.path.exists(self.token_path):
				with open(self.token_path,'r') as f:
					token=f.read().strip()
				self.token = token
			else:
				raise ValueError("Please write figshare token to ~/.figshare/token")
		else:
			self.token=token
			if not os.path.exists(self.token_path):
				logger.info("writing token to ~/.figshare/token")
				with open(self.token_path, 'w') as f:
					f.write(token)
		self.private = private
		self.chunk_size=chunk_size*1024*1024
		self.threshold=threshold
		self.value_attrs = ['title', 'description', 'is_metadata_record', 'metadata_reason',
					   'defined_type', 'funding', 'license', 'doi', 'handle', 'resource_doi',
					   'resource_title', 'group_id']
		self.list_attrs = ['tags', 'keywords', 'references', 'related_materials', 'categories',
					  'categories_by_source_id', 'authors',
					  'custom_fields_list', 'funding_list']
		self.dict_attrs = ['custom_fields', 'timeline']
		self.valid_attrs=self.value_attrs+self.list_attrs+self.dict_attrs
		logger.debug(f"chunk_size: {chunk_size} MB")
		self.max_quota=20

	def raw_issue_request(self, method, url, data=None, binary=False):
		headers = {'Authorization': 'token ' + self.token}
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

	def issue_request(self, method, endpoint, *args, **kwargs):
		return self.raw_issue_request(method, BASE_URL.format(endpoint=endpoint), *args, **kwargs)

	def list_files(self, article_id,version=None, private=None,show=True):
		if private is None:
			private=self.private
		if version is None:
			if private:
				endpoint='/account/articles/{}/files'.format(article_id)
			else:
				endpoint='/articles/{}/files'.format(article_id)
			result = self.issue_request('GET', endpoint)
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
			request = self.get_article(article_id, version)
			return request['files']

	def list_articles(self,show=False):
		result = self.issue_request('GET', 'account/articles')
		if show:
			logger.info('Listing current articles:')
			if result:
				for item in result:
					logger.info(u'  {url} - {title}'.format(**item))
			else:
				logger.warning("No articles found.")
		return result

	def search_articles(self,private=None,**kwargs):
		if private is None:
			private = self.private
		if private:
			title=kwargs['title']
			articles=self.list_articles()
			R = []
			for article in articles:
				if article['title'] == title:
					R.append(article)
		else:
			data={}
			invalid_keys = []
			for key in kwargs:
				if key in self.valid_attrs:
					if key in self.list_attrs:
						if not isinstance(kwargs[key], list):
							raise TypeError(
								f"{key} should be a list,see https://docs.figsh.com/#private_article_create for detail.")
					if key in self.dict_attrs:
						if not isinstance(kwargs[key], dict):
							raise TypeError(
								f"{key} should be a dict, see https://docs.figsh.com/#private_article_create for detail.")
					data[key] = kwargs[key]
				else:
					invalid_keys.append(key)
			if len(invalid_keys) > 0:
				logger.warning(f"Those keys were invalid: {invalid_keys} and will be ignored")
			R = self.issue_request('POST', 'articles/search',data=data)
		return R

	def create_article(self, **kwargs):
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
			if key in self.valid_attrs:
				if key in self.list_attrs:
					if not isinstance(kwargs[key],list):
						raise TypeError(f"{key} should be a list,see https://docs.figsh.com/#private_article_create for detail.")
				if key in self.dict_attrs:
					if not isinstance(kwargs[key],dict):
						raise TypeError(f"{key} should be a dict, see https://docs.figsh.com/#private_article_create for detail.")
				data[key]=kwargs[key]
			else:
				invalid_keys.append(key)
		if len(invalid_keys) > 0:
			logger.warning(f"Those keys were invalid: {invalid_keys} and will be ignored")

		result = self.issue_request('POST', 'account/articles', data=data)
		logger.info('Created article:', result['location'], '\n')
		result = self.raw_issue_request('GET', result['location'])
		return result['id']

	def delete_article(self,article_id):
		result = self.issue_request('DELETE',
									'account/articles/{}'.format(article_id))
		return result

	def delete_file(self,article_id, file_id,private=None):
		if private is None:
			private=self.private
		if private:
			endpoint='/account/articles/{0}/files/{1}'.format(article_id, file_id)
		else:
			endpoint='/articles/{0}/files/{1}'.format(article_id, file_id)
		result = self.issue_request('DELETE',endpoint)
		return result

	def delete_articles_with_title(self, title):
		articles=self.search_articles(title=title)
		for article in articles:
			self.delete_article(article['id'])

	def update_article(self, article_id, **kwargs):
		allowed = self.valid_attrs
		valid_keys = set(kwargs.keys()).intersection(allowed)
		body = {}
		for key in valid_keys:
			body[key] = kwargs[key]
		result = self.issue_request('PUT', 'account/articles/{}'.format(article_id),
									data=json.dumps(body))
		return result

	def get_article(self, article_id, version=None,private=None):
		if private is None:
			private=self.private
		if version is None:
			if private:
				endpoint='/account/articles/{}'.format(article_id)
			else:
				endpoint='/articles/{}'.format(article_id)
		else:
			if private:
				endpoint='/account/articles/{}/versions/{}'.format(article_id,version)
			else:
				endpoint = '/articles/{}/versions/{}'.format(article_id,version)
		result = self.issue_request('GET', endpoint)
		return result

	def list_article_versions(self, article_id, private=None):
		if private is None:
			private=self.private
		if private:
			raise ValueError("Not supported for private")
		else:
			endpoint='/articles/{}/versions'.format(article_id)
		response = self.issue_request('GET', endpoint)
		return response

	def get_file_details(self, article_id, file_id,private=None):
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
		if private is None:
			private=self.private
		if private:
			endpoint='/account/articles/{0}/files/{1}'.format(article_id, file_id)
		else:
			endpoint='/articles/{0}/files/{1}'.format(article_id, file_id)
		response = self.issue_request('GET', endpoint)
		return response

	def download_article(self, article_id, outdir="./",cpu=1):
		outdir=os.path.abspath(os.path.expanduser(outdir))
		# Get list of files
		file_list = self.list_files(article_id,show=False)
		os.makedirs(outdir, exist_ok=True) # This might require Python >=3.2
		if cpu==1:
			for file_dict in file_list:
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

	def get_file_check_data(self, file_name):
		with open(file_name, 'rb') as fin:
			md5 = hashlib.md5()
			size = 0
			data = fin.read(self.chunk_size)
			while data:
				size += len(data)
				md5.update(data)
				data = fin.read(self.chunk_size)
			return md5.hexdigest(), size

	def initiate_new_upload(self, article_id, file_path,folder_name=None):
		basename = os.path.basename(file_path)
		if not folder_name is None:
			name = f"{folder_name}/{basename}"
		else:
			name = basename
		if name in self.existed_files:
			return None
		endpoint = 'account/articles/{}/files'
		endpoint = endpoint.format(article_id)
		md5, size = self.get_file_check_data(file_path)
		if size == 0:
			return False
		# check whether there is enough quota before initiating new upload
		quota_used=self.get_used_quota_private()
		if quota_used > self.threshold or quota_used+size/1024/1024/1024 > self.max_quota:
			logger.info(f"used quota is {quota_used}, try to publish article.")
			try:
				result=self.publish(article_id) # publish article
			except:
				logger.warning("Failed to publish, please publish manually")
				print(f"article_id:{article_id}")
		else:
			logger.info(f"used quota: {quota_used}")
		data = {'name':name,'md5': md5,'size': size}
		result = self.issue_request('POST', endpoint, data=data)
		# logger.info('Initiated file upload:', result['location'], '\n')
		result = self.raw_issue_request('GET', result['location'])
		return result

	def complete_upload(self, article_id, file_id):
		self.issue_request('POST', 'account/articles/{}/files/{}'.format(article_id, file_id))

	def upload_parts(self, file_path, file_info):
		url = '{upload_url}'.format(**file_info)
		result = self.raw_issue_request('GET', url)
		# print('Uploading parts:')
		with open(file_path, 'rb') as fin:
			for part in result['parts']:
				self.upload_part(file_info, fin, part)

	def upload_part(self, file_info, stream, part):
		udata = file_info.copy()
		udata.update(part)
		url = '{upload_url}/{partNo}'.format(**udata)
		stream.seek(part['startOffset'])
		data = stream.read(part['endOffset'] - part['startOffset'] + 1)
		self.raw_issue_request('PUT', url, data=data, binary=True)
		# print(' Uploaded part {partNo} from {startOffset} to {endOffset}'.format(**part))

	def upload_file(self,article_id, file_path,folder_name=None):
		# Then we upload the file.
		file_info = self.initiate_new_upload(article_id, file_path,folder_name)
		if file_info is None:
			logger.info(f"File existed, skipped: {file_path}")
			return None
		if file_info==False:
			logger.info(f"File size is 0, skipped: {file_path}")
			return None
		logger.info(file_path)
		# Until here we used the figshare API; following lines use the figshare upload service API.
		self.upload_parts(file_path,file_info)
		# We return to the figshare API to complete the file upload process.
		self.complete_upload(article_id, file_info['id'])
		# self.list_files(article_id)

	def upload_folder(self,article_id, file_path,pre_folder_name=None): #file_path is a directory
		logger.debug(f"dir: {file_path}")
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
				self.upload_file(article_id, new_file_path,cur_folder_name)
			elif os.path.isdir(new_file_path): # new file path is still a folder, level 2 folder.
				self.upload_folder(article_id, new_file_path,cur_folder_name)
			else:
				logger.warning(f"{new_file_path} is not dir, neither file, not recognized")

	def upload(self,article_id, file_path):
		res = self.list_files(article_id, show=False)
		self.existed_files = [r['name'] for r in res]
		logger.debug(self.existed_files)
		if os.path.isdir(file_path):
			self.upload_folder(article_id, file_path)
		elif os.path.isfile(file_path): #file
			self.upload_file(article_id, file_path)
		else:
			logger.warning(f"{file_path} is not dir, neither file, not recognized")

	def publish(self,article_id):
		endpoint = '/account/articles/{}/publish'.format(article_id)
		result = self.issue_request('POST', endpoint)
		return result

	def get_author_id(self,article_id):
		res=self.get_article(article_id)
		return res['authors'][0]['id']

	def author(self,author_id):
		endpoint = '/account/authors/{}'.format(author_id)
		result = self.issue_request('GET', endpoint)
		return result

	def get_account_info(self):
		result = self.issue_request('GET', '/account')
		return result

	def get_used_quota_private(self):
		result=self.get_account_info()
		return result['used_quota_private'] / 1024 / 1024 / 1024

def upload(
	input_path="./",
	title='title', description='description',
	token=None,output="figshare.tsv",
	threshold=15,chunk_size=20,
	level='INFO'):
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
	token : str
		If ~/.figshare/token existed, this paramter can be ignored.
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

	Returns
	-------

	"""
	logger.level = level
	input_path = os.path.abspath(os.path.expanduser(input_path))
	if "*" not in input_path and os.path.isdir(input_path):
		input_files=[os.path.join(input_path,file) for file in os.listdir(input_path)] # including file and folder
	elif "*" in input_path:
		input_files=glob.glob(input_path)
	else:
		input_files=[input_path]
	fs = Figshare(token=token,chunk_size=chunk_size,threshold=threshold)
	r = fs.search_articles(title=title)
	if len(r) == 0:
		logger.info(f"article: {title} not found, create it")
		aid = fs.create_article(title=title, description=description)
	else:
		logger.info(f"found existed article")
		aid = r[0]['id'] #article id

	for file_path in input_files:
		fs.upload(aid, file_path)
	get_filenames(aid, private=True, output=os.path.expanduser(output))
	logger.info(f"See {output} for the detail information of the uploaded files")

def get_filenames(article_id,private=False,output="figshare.tsv"):
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
	fs = Figshare(private=private)
	# fs.get_article(article_id) #article_id=9273710
	# generating the mapping file from file id to file name
	res = fs.list_files(article_id)
	R = []
	for r in res:
		url = "https://figshare.com/ndownloader/files/" + str(r['id'])
		R.append([r['name'], r['id'], url])
	df = pd.DataFrame(R, columns=['file', 'file_id', 'url'])
	df.to_csv(output, sep='\t', index=False)

def download(article_id,private=False, outdir="./",cpu=1):
	"""
	Download all files for a given figshare article id

	Parameters
	----------
	article_id : int
		figshare article id, for example, article id for this public article:
		https://figshare.com/articles/dataset/9273710 is 9273710.
	private : bool
		whether this is a private article or not.
	outdir : path
		whether to store the downloaded files.

	Returns
	-------

	"""
	fs = Figshare(private=private)
	fs.download_article(article_id, outdir=outdir,cpu=cpu)

if __name__ == "__main__":
	fire.core.Display = lambda lines, out: print(*lines, file=out)
	fire.Fire()