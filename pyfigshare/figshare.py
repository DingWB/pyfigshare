# -*- coding: utf-8 -*-
"""Core Figshare client and high-level upload/download/list helpers.

@author: DingWB
"""
from __future__ import annotations

import hashlib
import json
import glob
import os
import sys
import stat
import time
import random
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union
from urllib.request import urlretrieve

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError
from loguru import logger

try:  # optional progress bars
	from tqdm.auto import tqdm as _tqdm
except ImportError:  # pragma: no cover - tqdm is optional
	_tqdm = None


def _set_log_level(level: str) -> None:
	"""Configure the loguru logger handlers to honour ``level``.

	This is intended for the CLI entry point; the library itself does not call
	it on import, so importing :mod:`pyfigshare` will not change a host
	application's existing loguru configuration.
	"""
	try:
		logger.remove()
	except ValueError:
		pass
	logger.add(sys.stderr, level=level)


def _redact_body(content: bytes, token: Optional[str]) -> str:
	try:
		text = content.decode("utf-8", errors="replace")
	except Exception:
		return repr(content)
	if token:
		text = text.replace(token, "<REDACTED>")
	return text[:2000]


def download_worker(url: str, path: str) -> str:
	dirname = os.path.dirname(path)
	if dirname and not os.path.exists(dirname):
		os.makedirs(dirname, exist_ok=True)
	if os.path.exists(path):
		logger.info(f"{path} existed")
		return path
	urlretrieve(url, path)
	return path

class Figshare:
	def __init__(
		self,
		token: Optional[str] = None,
		private: bool = True,
		chunk_size: int = 20,
		threshold: int = 18,
		upload_workers: int = 4,
		max_retries: int = 5,
		retry_backoff: float = 1.0,
		mid_publish: bool = False,
	):
		"""figshare client.

		Parameters
		----------
		token : str, optional
			Personal token. If ``None``, read from ``~/.figshare/token`` (or the
			``FIGSHARE_TOKEN`` environment variable).
		private : bool
			Whether subsequent reads/writes target the private (account) endpoints.
		chunk_size : int
			Local read chunk in MB used when computing md5 / size.
		threshold : int
			Quota (in GB) above which ``mid_publish`` will publish the article
			in the middle of an upload to free space. Only honoured when
			``mid_publish=True``.
		upload_workers : int
			**Inner concurrency** — number of threads used to upload the parts
			of a *single* file in parallel. Figshare splits each file into
			parts; this controls how many parts are PUT at the same time.

			Analogy: this is *"how many workers carry one box together"*
			(parallelism within one file). Pair with ``file_workers`` on
			:meth:`upload`/:func:`pyfigshare.upload` for *"how many boxes get
			carried at once"* (parallelism across files).

			Threads share one ``requests.Session`` so the TLS connection is
			reused across part PUTs. Threads are used (not processes) because
			the bottleneck is network I/O. Default 4. Increase for big files
			on fast networks; setting it too high may trigger HTTP 429.
		max_retries : int
			Retries per part on transient errors (5xx / 429 / connection).
		retry_backoff : float
			Base seconds for exponential backoff between part-upload retries.
		mid_publish : bool
			If True, auto-publish the article when used quota crosses
			``threshold`` (legacy behaviour). Default is False, which is safer
			because publishing is irreversible.
		"""
		if chunk_size <= 0:
			raise ValueError("chunk_size must be > 0")
		if upload_workers < 1:
			raise ValueError("upload_workers must be >= 1")
		if max_retries < 0:
			raise ValueError("max_retries must be >= 0")
		self.baseurl = "https://api.figshare.com/v2/{endpoint}"
		self.token_path = os.path.expanduser("~/.figshare/token")
		if token is None:
			token = os.environ.get("FIGSHARE_TOKEN")
		if token is None:
			if os.path.exists(self.token_path):
				self._warn_if_token_world_readable(self.token_path)
				with open(self.token_path, 'r') as f:
					token = f.read().strip()
			else:
				raise ValueError(
					"No figshare token provided. Pass `token=...`, set the "
					"FIGSHARE_TOKEN env var, or run `figshare set-token`."
				)
		self.token = token
		self.private = private
		self.chunk_size = int(chunk_size) * 1024 * 1024
		self.threshold = threshold
		self.upload_workers = int(upload_workers)
		self.max_retries = int(max_retries)
		self.retry_backoff = float(retry_backoff)
		self.mid_publish = bool(mid_publish)
		self.value_attrs = ['title', 'description', 'is_metadata_record', 'metadata_reason',
					   'defined_type', 'funding', 'license', 'doi', 'handle', 'resource_doi',
					   'resource_title', 'group_id']
		self.list_attrs = ['tags', 'keywords', 'references', 'related_materials', 'categories',
					  'categories_by_source_id', 'authors',
					  'custom_fields_list', 'funding_list']
		self.dict_attrs = ['custom_fields', 'timeline']
		self.valid_attrs = self.value_attrs + self.list_attrs + self.dict_attrs
		self.max_quota = 20
		# {name: {"id": int, "md5": str, "size": int}}
		self.existed_files: Dict[str, Dict[str, Any]] = {}
		self.target_folder: Optional[str] = None
		# Lock guarding mutations of `existed_files` from worker threads.
		self._existed_files_lock = threading.Lock()
		# Optional progress callback: called as cb(event, **kwargs).
		self.progress_cb: Optional[Callable[..., None]] = None
		# Persistent HTTP session with a connection pool sized for our worker
		# count, so concurrent part PUTs don't repeatedly redo the TLS handshake.
		self.session = requests.Session()
		pool = max(self.upload_workers * 2, 4)
		adapter = HTTPAdapter(pool_connections=pool, pool_maxsize=pool, max_retries=0)
		self.session.mount("https://", adapter)
		self.session.mount("http://", adapter)
		self.session.headers.update({"Authorization": f"token {self.token}"})

	@staticmethod
	def _warn_if_token_world_readable(path):
		try:
			mode = os.stat(path).st_mode
		except OSError:
			return
		if mode & (stat.S_IRWXG | stat.S_IRWXO):
			logger.warning(
				f"Token file {path} is accessible by group/other; "
				"consider `chmod 600` to protect it."
			)

	def raw_issue_request(self, method, url, data=None, binary=False):
		# Authorization header is set on the session; no need to repeat it here.
		if data is not None and not binary:
			data = json.dumps(data)
		response = self.session.request(method, url, data=data)
		try:
			response.raise_for_status()
			try:
				parsed = json.loads(response.content)
			except ValueError:
				parsed = response.content
		except HTTPError as error:
			logger.warning(error)
			logger.debug(f"Body: {_redact_body(response.content, self.token)}")
			raise
		return parsed

	def _retry_after(self, response: "requests.Response") -> Optional[float]:
		hdr = response.headers.get("Retry-After") if response is not None else None
		if not hdr:
			return None
		try:
			return max(0.0, float(hdr))
		except (TypeError, ValueError):
			return None

	def issue_request(self, method, endpoint, *args, **kwargs):
		return self.raw_issue_request(method, self.baseurl.format(endpoint=endpoint), *args, **kwargs)

	def get_article(self, article_id, version=None,private=None):
		if private is None:
			private=self.private
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
		result = self.issue_request('GET', endpoint)
		return result

	def list_files(self, article_id, version=None, private=None, show=True):
		request = self.get_article(article_id, version, private)
		if show:
			for item in request['files']:
				logger.info('  {id} - {name}'.format(**item))
		return request['files']

	def list_articles(self,show=False):
		result = self.issue_request('GET', "account/articles")
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
		logger.info(f"Created article: {result['location']}")
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
			endpoint='account/articles/{0}/files/{1}'.format(article_id, file_id)
		else:
			endpoint='articles/{0}/files/{1}'.format(article_id, file_id)
		result = self.issue_request('DELETE',endpoint)
		return result

	def delete_all_files(self,article_id,private=None,version=None):
		files=self.list_files(article_id,version=version, private=private,show=False)
		for file in files:
			file_id=file['id']
			logger.info(f"Deleting file: {file['name']}")
			self.delete_file(article_id,file_id,private=private)

	def delete_folder(self, article_id, folder_name, version=None, private=True):
		if not folder_name.endswith('/'):
			folder_name = folder_name + '/'
		files = self.list_files(article_id, version=version, private=private, show=False)
		for file in files:
			file_id = file['id']
			file_name = file['name']
			if not file_name.startswith(folder_name):
				continue
			logger.info(f"deleting file {file_name}")
			self.delete_file(article_id, file_id, private=private)

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

	def list_article_versions(self, article_id, private=None):
		if private is None:
			private=self.private
		if private:
			raise ValueError("Not supported for private")
		else:
			endpoint='articles/{}/versions'.format(article_id)
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
			endpoint='account/articles/{0}/files/{1}'.format(article_id, file_id)
		else:
			endpoint='articles/{0}/files/{1}'.format(article_id, file_id)
		response = self.issue_request('GET', endpoint)
		return response

	def download_article(self, article_id, outdir="./",cpu=1,folder=None):
		outdir=os.path.abspath(os.path.expanduser(outdir))
		# Get list of files
		file_list = self.list_files(article_id,show=False)
		# Prepare headers for private downloads
		# headers = {'Authorization': 'token ' + self.token} if self.private else None
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
				# url=file_dict['download_url'] if not self.private else f"https://figshare.com/ndownloader/files/{file_dict['id']}"
				# download with optional Authorization header for private files
				download_worker(file_dict['download_url'], path)
		else:
			with ProcessPoolExecutor(cpu) as executor:
				futures = {}
				for file_dict in file_list:
					if not folder is None and folder!=file_dict['name'].split('/')[0]:
						continue
					# url=file_dict['download_url'] if not self.private else f"https://figshare.com/ndownloader/files/{file_dict['id']}"
					future = executor.submit(
						download_worker,
						file_dict['download_url'],
						os.path.join(outdir, file_dict['name']),
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

	def initiate_new_upload(self, article_id, file_path,folder_name=None,overwrite=False):
		basename = os.path.basename(file_path) #.replace(' ','_')
		if folder_name is not None:
			name = f"{folder_name}/{basename}"
		else:
			name = basename
		if self.target_folder is not None:
			name=f"{self.target_folder}/{name}"
		# Compute local checksum/size up front so we can compare with the remote
		# file (when `overwrite=True`) before doing any deletion or upload.
		md5, size = self.get_file_check_data(file_path)
		if size == 0:
			return False
		if name in self.existed_files:
			if not overwrite:
				return None
			remote = self.existed_files[name]
			remote_md5 = remote.get('md5') if isinstance(remote, dict) else None
			remote_size = remote.get('size') if isinstance(remote, dict) else None
			if remote_md5 and remote_md5 == md5 and remote_size == size:
				logger.info(f"Identical file already on figshare, skipped: {name}")
				return None
			old_file_id = remote['id'] if isinstance(remote, dict) else remote
			logger.info(f"Overwriting existing file: {name} (id={old_file_id})")
			try:
				self.delete_file(article_id, old_file_id)
			except Exception as e:
				logger.warning(f"Failed to delete existing file {name}: {e}")
			del self.existed_files[name]
		endpoint = 'account/articles/{}/files'.format(article_id)
		# check whether there is enough quota before initiating new upload
		if self.mid_publish:
			quota_used = self.get_used_quota_private()
			if quota_used > self.threshold or quota_used + size / 1024 / 1024 / 1024 > self.max_quota:
				logger.info(f"used quota is {quota_used} GB, publishing article to free space.")
				try:
					self.publish(article_id)
				except Exception as e:
					logger.warning(f"Failed to publish article {article_id}: {e}. Please publish manually.")
		data = {'name':name,'md5': md5,'size': size}
		try:
			result = self.issue_request('POST', endpoint, data=data)
		except Exception as e:
			logger.error(
				f"Failed to initiate upload (file_path={file_path}, name={name}, size={size}): {e}"
			)
			raise
		result = self.raw_issue_request('GET', result['location'])
		return result

	def complete_upload(self, article_id, file_id):
		self.issue_request('POST', 'account/articles/{}/files/{}'.format(article_id, file_id))

	def upload_parts(self, file_path, file_info):
		url = '{upload_url}'.format(**file_info)
		parts = self.raw_issue_request('GET', url)['parts']
		workers = min(self.upload_workers, len(parts)) if parts else 1
		cb = self.progress_cb
		if cb:
			cb('parts_total', name=file_info.get('name'), n=len(parts))
		if workers <= 1:
			with open(file_path, 'rb') as fin:
				for part in parts:
					self.upload_part(file_info, fin, part)
					if cb:
						cb('part_done', name=file_info.get('name'))
			return
		# Parallel path: each worker opens its own file handle so seeks don't
		# race. Failures are surfaced by re-raising the first one.
		logger.debug(f"Uploading {len(parts)} parts with {workers} workers: {file_path}")
		def _do(part):
			with open(file_path, 'rb') as fin:
				self.upload_part(file_info, fin, part)
		with ThreadPoolExecutor(max_workers=workers) as pool:
			futures = [pool.submit(_do, p) for p in parts]
			for fut in as_completed(futures):
				fut.result()  # propagate exceptions
				if cb:
					cb('part_done', name=file_info.get('name'))

	def upload_part(self, file_info, stream, part):
		udata = file_info.copy()
		udata.update(part)
		url = '{upload_url}/{partNo}'.format(**udata)
		stream.seek(part['startOffset'])
		data = stream.read(part['endOffset'] - part['startOffset'] + 1)
		self._put_part_with_retry(url, data, part_no=part.get('partNo'))

	def _put_part_with_retry(self, url, data, part_no=None):
		"""PUT a single part with exponential-backoff retries on transient errors."""
		last_exc: Optional[BaseException] = None
		for attempt in range(self.max_retries + 1):
			wait_override: Optional[float] = None
			try:
				self.raw_issue_request('PUT', url, data=data, binary=True)
				return
			except HTTPError as e:
				resp = getattr(e, 'response', None)
				status = getattr(resp, 'status_code', None)
				# Retry on 5xx and 429; bail out on 4xx (auth, bad request, etc.).
				if status is not None and status < 500 and status != 429:
					raise
				wait_override = self._retry_after(resp)
				last_exc = e
			except (requests.ConnectionError, requests.Timeout) as e:
				last_exc = e
			if attempt < self.max_retries:
				if wait_override is not None:
					delay = wait_override + random.uniform(0, 0.5)
				else:
					delay = self.retry_backoff * (2 ** attempt) + random.uniform(0, 0.5)
				logger.warning(
					f"part {part_no} upload failed (attempt {attempt+1}/{self.max_retries+1}): "
					f"{last_exc}; retrying in {delay:.1f}s"
				)
				time.sleep(delay)
		assert last_exc is not None
		raise last_exc

	def upload_file(self,article_id, file_path,folder_name=None,overwrite=False):
		# Then we upload the file.
		try:
			file_info = self.initiate_new_upload(article_id, file_path,folder_name,overwrite=overwrite)
		except Exception as e:
			logger.error(f"Error for file {file_path}, skipped: {e}")
			return None
		if file_info is None:
			return None
		if file_info is False:
			logger.info(f"File size is 0, skipped: {file_path}")
			return None
		logger.info(file_path)
		# Until here we used the figshare API; following lines use the figshare upload service API.
		self.upload_parts(file_path,file_info)
		# We return to the figshare API to complete the file upload process.
		self.complete_upload(article_id, file_info['id'])
		# Refresh the in-memory cache so that subsequent uploads in the same
		# call see this file as already-existing (esp. for overwrite=True).
		with self._existed_files_lock:
			self.existed_files[file_info['name']] = {
				'id': file_info['id'],
				'md5': file_info.get('computed_md5') or file_info.get('supplied_md5'),
				'size': file_info.get('size'),
			}

	def upload_folder(self,article_id, file_path,pre_folder_name=None,overwrite=False): #file_path is a directory
		logger.debug(f"dir: {file_path}")
		assert os.path.isdir(file_path), 'file_path must be a folder'
		folder_name = os.path.basename(file_path)
		if pre_folder_name is not None:
			cur_folder_name=f"{pre_folder_name}/{folder_name}"
		else:
			cur_folder_name=folder_name
		logger.info(cur_folder_name)
		for file in os.listdir(file_path):
			new_file_path=os.path.join(file_path,file)
			if os.path.isfile(new_file_path):
				self.upload_file(article_id, new_file_path,cur_folder_name,overwrite=overwrite)
			elif os.path.isdir(new_file_path): # new file path is still a folder, level 2 folder.
				self.upload_folder(article_id, new_file_path,cur_folder_name,overwrite=overwrite)
			else:
				logger.warning(f"{new_file_path} is not dir, neither file, not recognized")

	def check_files(self,article_id):
		res = self.list_files(article_id, show=False)
		self.existed_files = {
			r['name']: {
				'id': r['id'],
				'md5': r.get('computed_md5') or r.get('supplied_md5'),
				'size': r.get('size'),
			}
			for r in res
		}
		logger.debug(self.existed_files)

	def upload(self, article_id, file_path, overwrite=False, file_workers=1):
		"""Upload a file or directory to ``article_id``.

		Concurrency cheat-sheet
		-----------------------
		``upload_workers`` (set on the ``Figshare`` instance) and
		``file_workers`` (passed here) are **two independent thread pools**:

		  - ``upload_workers`` = how many parts of *one file* go up in
		    parallel ("workers per box").
		  - ``file_workers``   = how many *different files* go up in
		    parallel when ``file_path`` is a directory ("how many boxes at
		    once"). Ignored for single-file uploads.

		Total in-flight HTTP PUTs is roughly
		``file_workers * upload_workers``. Don't go much above ~32 or
		figshare will start throttling with 429s.

		Parameters
		----------
		article_id : int
			Target figshare article id.
		file_path : str
			A single file or a directory. Directories are walked recursively.
		overwrite : bool
			If True, replace remote files of the same name. Files whose md5
			and size already match the remote copy are still skipped.
		file_workers : int
			How many *different files* to upload at the same time when
			``file_path`` is a directory (default 1 = serial). Use a higher
			value when uploading many small files; for a few big files, raise
			``upload_workers`` instead. Ignored for single-file uploads.
		"""
		if os.path.isdir(file_path):
			if file_workers and file_workers > 1:
				specs = []
				self._collect_files(file_path, pre_folder_name=None, out=specs)
				self._upload_specs(article_id, specs, overwrite=overwrite,
								   file_workers=file_workers)
			else:
				self.upload_folder(article_id, file_path, overwrite=overwrite)
		elif os.path.isfile(file_path):
			self.upload_file(article_id, file_path, overwrite=overwrite)
		else:
			logger.warning(f"{file_path} is not dir, neither file, not recognized")

	def _collect_files(self, file_path, pre_folder_name, out):
		assert os.path.isdir(file_path)
		folder_name = os.path.basename(file_path)
		cur = f"{pre_folder_name}/{folder_name}" if pre_folder_name else folder_name
		for entry in os.listdir(file_path):
			new_path = os.path.join(file_path, entry)
			if os.path.isfile(new_path):
				out.append((new_path, cur))
			elif os.path.isdir(new_path):
				self._collect_files(new_path, cur, out)

	def _upload_specs(self, article_id, specs, overwrite, file_workers):
		logger.info(f"Uploading {len(specs)} files with file_workers={file_workers}")
		with ThreadPoolExecutor(max_workers=file_workers) as pool:
			futures = {
				pool.submit(self.upload_file, article_id, p, folder, overwrite): p
				for (p, folder) in specs
			}
			for fut in as_completed(futures):
				path = futures[fut]
				try:
					fut.result()
				except Exception as e:
					logger.error(f"Upload failed for {path}: {e}")

	def publish(self,article_id):
		endpoint = 'account/articles/{}/publish'.format(article_id)
		result = self.issue_request('POST', endpoint)
		return result

	def get_author_id(self,article_id):
		res=self.get_article(article_id)
		return res['authors'][0]['id']

	def author(self,author_id):
		endpoint = 'account/authors/{}'.format(author_id)
		result = self.issue_request('GET', endpoint)
		return result

	def get_account_info(self):
		result = self.issue_request('GET', '/account')
		return result

	def get_used_quota_private(self):
		result=self.get_account_info()
		return result['used_quota_private'] / 1024 / 1024 / 1024

def upload(
	input_path: str = "./",
	title: str = 'title',
	description: str = 'description',
	token: Optional[str] = None,
	output: str = "figshare.tsv",
	publish: bool = True,
	threshold: int = 18,
	chunk_size: int = 20,
	level: Optional[str] = None,
	target_folder: Optional[str] = None,
	overwrite: bool = False,
	upload_workers: int = 4,
	max_retries: int = 5,
	file_workers: int = 1,
	mid_publish: bool = False,
	dry_run: bool = False,
	failed_output: Optional[str] = None,
	progress: bool = False,
) -> None:
	"""Upload files or directories to a figshare article.

	Concurrency model
	-----------------
	Uploads use **two nested layers of threads** (both
	``concurrent.futures.ThreadPoolExecutor``); processes are *not* used
	here because the bottleneck is network I/O, not CPU.

	- ``upload_workers`` (inner): threads that PUT the parts of a single
	  file in parallel. They share one ``requests.Session`` so the TLS
	  connection is reused across parts.
	- ``file_workers`` (outer): threads that upload *different files*
	  concurrently when the input is a directory. Ignored for single
	  files.

	The maximum number of in-flight HTTP PUTs is therefore roughly
	``file_workers * upload_workers``. Setting either value too high can
	trigger figshare's rate limit (HTTP 429); the client honours
	``Retry-After`` and exponentially backs off, but throughput may not
	improve past a few dozen concurrent connections.

	Parameters
	----------
	input_path : str
		File path, directory, or quoted glob pattern (e.g. ``"./data/*.csv"``).
	title, description : str
		Article metadata; the article is created if it doesn't already exist.
	token : str, optional
		Figshare token; falls back to ``FIGSHARE_TOKEN`` env var or
		``~/.figshare/token``.
	output : path
		TSV listing successfully-uploaded files (``name, file_id, url``).
	publish : bool
		Publish the article when uploading is finished.
	threshold : int
		Quota threshold (GB); only honoured when ``mid_publish=True``.
	chunk_size : int
		Local md5/size hashing chunk in MB.
	level : str, optional
		If set, reconfigure the loguru logger to this level. Library callers
		should leave this as ``None``; the CLI sets it explicitly.
	target_folder : str, optional
		Remote folder prefix for all uploaded files.
	overwrite : bool
		Replace remote files of the same name (md5+size match still skips).
	upload_workers : int
		**Inner pool** — threads PUTting the parts of *one* file in
		parallel ("workers per box"). Default 4.
	max_retries : int
		Retries per part on transient errors (5xx / 429 / connection).
	file_workers : int
		**Outer pool** — threads uploading *different files* in parallel
		when the input expands to multiple files ("how many boxes at
		once"). Default 1 (serial). Use ``-W`` for many small files;
		use ``-w`` (``upload_workers``) for a few big files. The total
		number of simultaneous HTTP PUTs is roughly
		``file_workers * upload_workers`` — keep this under ~32 to avoid
		rate-limit (429) responses from figshare.
	mid_publish : bool
		If True, auto-publish in the middle of an upload when the quota would
		overflow. Default False (safer).
	dry_run : bool
		Compute md5/size for each input file and report what would be uploaded
		without creating the article or transferring data.
	failed_output : path, optional
		If set, write failed (path, error) entries to this TSV.
	progress : bool
		Show tqdm progress bars (requires the ``tqdm`` package).
	"""
	if level is not None:
		_set_log_level(level)
	input_path = os.path.abspath(os.path.expanduser(input_path))
	if "*" not in input_path and os.path.isdir(input_path):
		input_files = [os.path.join(input_path, f) for f in os.listdir(input_path)]
	elif "*" in input_path:
		input_files = sorted(glob.glob(input_path))
	else:
		if not os.path.exists(input_path):
			raise FileNotFoundError(f"input_path does not exist: {input_path}")
		input_files = [input_path]
	if not input_files:
		logger.warning(f"No input files matched: {input_path}")
		return

	if dry_run:
		_dry_run_report(input_files, target_folder=target_folder, chunk_size=chunk_size)
		return

	fs = Figshare(
		token=token,
		chunk_size=chunk_size,
		threshold=threshold,
		upload_workers=upload_workers,
		max_retries=max_retries,
		mid_publish=mid_publish,
	)
	r = fs.search_articles(title=title)
	if len(r) == 0:
		logger.info(f"article: {title!r} not found, creating it")
		article_id = fs.create_article(title=title, description=description)
	else:
		logger.info("found existing article")
		article_id = r[0]['id']

	fs.check_files(article_id)
	fs.target_folder = target_folder

	progress_bar = None
	if progress and _tqdm is not None:
		progress_bar = _tqdm(total=0, unit="part", desc="upload", dynamic_ncols=True)

		def _cb(event, **kwargs):
			if event == 'parts_total':
				progress_bar.total = (progress_bar.total or 0) + kwargs.get('n', 0)
				progress_bar.refresh()
			elif event == 'part_done':
				progress_bar.update(1)
		fs.progress_cb = _cb
	elif progress and _tqdm is None:
		logger.warning("`progress=True` requested but tqdm is not installed; "
					   "install with `pip install tqdm`.")

	failed: List[Tuple[str, str]] = []
	try:
		for file_path in input_files:
			try:
				fs.upload(article_id, file_path, overwrite=overwrite,
						  file_workers=file_workers)
			except Exception as e:
				logger.error(f"Upload failed for {file_path}: {e}")
				failed.append((file_path, str(e)))
	finally:
		if progress_bar is not None:
			progress_bar.close()

	if failed and failed_output:
		with open(os.path.expanduser(failed_output), "w") as fh:
			fh.write("path\terror\n")
			for path, err in failed:
				fh.write(f"{path}\t{err}\n")
		logger.warning(f"Wrote {len(failed)} failure(s) to {failed_output}")

	if publish:
		fs.publish(article_id)
	list_files(article_id, private=False, output=os.path.expanduser(output))
	logger.info(f"See {output} for the detail information of the uploaded files")


def _dry_run_report(input_files, target_folder, chunk_size):
	"""Print what an upload run would do without contacting figshare."""
	def walk(p):
		if os.path.isfile(p):
			yield p
		elif os.path.isdir(p):
			for root, _, files in os.walk(p):
				for f in files:
					yield os.path.join(root, f)

	def _md5(path, chunk):
		h = hashlib.md5()
		size = 0
		with open(path, "rb") as fh:
			while True:
				buf = fh.read(chunk)
				if not buf:
					break
				size += len(buf)
				h.update(buf)
		return h.hexdigest(), size

	chunk = chunk_size * 1024 * 1024
	total = 0
	sys.stdout.write("path\tremote_name\tsize\tmd5\n")
	for base in input_files:
		for p in walk(base):
			rel = os.path.relpath(p, os.path.dirname(base)) if os.path.isdir(base) else os.path.basename(p)
			rel = rel.replace(os.sep, "/")
			name = f"{target_folder}/{rel}" if target_folder else rel
			md5, size = _md5(p, chunk)
			total += size
			sys.stdout.write(f"{p}\t{name}\t{size}\t{md5}\n")
	logger.info(f"dry-run total: {total/1024/1024:.1f} MiB")

def list_files(article_id,private=False,version=None,output=None):
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
	res = fs.list_files(article_id,version=version,show=False)
	R = []
	for r in res:
		url = "https://figshare.com/ndownloader/files/" + str(r['id'])
		R.append([r['name'], r['id'], url])
	df = pd.DataFrame(R, columns=['file', 'file_id', 'url'])
	if output is not None:
		df.to_csv(output, sep='\t', index=False)
	else:
		df.to_csv(sys.stdout, sep='\t', index=False)

def download(article_id,private=False, outdir="./",cpu=1,folder=None):
	"""
	Download all files for a given figshare article id.

	Unlike :func:`upload`, downloads use a ``ProcessPoolExecutor`` (true
	processes, hence the ``cpu`` parameter name) because each file is
	fetched with ``urllib.request.urlretrieve`` independently and there is
	no shared HTTP session to benefit from threads.

	Parameters
	----------
	article_id : int
		figshare article id, for example, article id for this public article:
		https://figshare.com/articles/dataset/9273710 is 9273710.
	private : bool
		whether this is a private article or not.
	outdir : path
		directory where downloaded files will be written.
	cpu : int
		Number of **processes** to use for parallel downloads (default 1).
	folder : str, optional
		If set, only download files whose top-level remote folder equals
		this name.
	"""
	fs = Figshare(private=private)
	fs.download_article(article_id, outdir=outdir,cpu=cpu,folder=folder)

if __name__ == "__main__":
	from .cli import main
	sys.exit(main())