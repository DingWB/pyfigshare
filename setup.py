# -*- coding: utf-8 -*-
"""
Created on Thu may 5 11:27:17 2022

@author: DingWB
"""
from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="pyfigshare",
	use_scm_version=True,  # {'version_scheme': 'python-simplified-semver',"local_scheme": "no-local-version"},
	setup_requires=['setuptools_scm'],
    description="A Python package to interact with figshare",
    author="Wubin Ding",
    author_email="ding.wu.bin.gm@gmail.com",
    url="https://github.com/DingWB/pyfigshare",
    # packages=['pyfigshare'],  # pyfigshare
	# package_dir={'': 'pyfigshare'},
	license='MIT',
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
	packages=find_packages(exclude=('docs',)),
	install_requires=['fire','pandas','requests'],
	include_package_data=True,
	package_data={
		'': ['*.txt', '*.tsv', '*.csv', '*ipynb']
	},
	entry_points={
			'console_scripts':
				['figshare=pyfigshare:main',],
	},
)
