# coding: utf-8
from setuptools import setup, find_packages
from setuptools.extension import Extension
from distutils.extension import Extension
from codecs import open
from os import path
import glob
import re
import sys

from gqlib import __version__
here = path.abspath(path.dirname("__file__"))

with open(path.join(here, "DESCRIPTION.md"), encoding="utf-8") as description:
	description = long_description = description.read()

	name="gqlib"
	version = __version__

	if sys.version_info.major != 3:
		raise EnvironmentError("""{toolname} is a python module that requires python3, and is not compatible with python2.""".format(toolname=name))

	setup(
		name=name,
		version=version,
		description=description,
		long_description=long_description,
		url="https://github.com/cschu/gqlib",
		author="Christian Schudoma",
		author_email="cschu1981@gmail.com",
		license="MIT",
		classifiers=[
			"Development Status :: 4 - Beta",
			"Topic :: Scientific/Engineering :: Bio-Informatics",
			"License :: OSI Approved :: MIT License",
			"Operating System :: POSIX :: Linux",
			"Programming Language :: Python :: 3.7",
			"Programming Language :: Python :: 3.8",
			"Programming Language :: Python :: 3.9",
			"Programming Language :: Python :: 3.10",
		],
		zip_safe=False,
		keywords="large reference data genomic feature quantification",
		packages=find_packages(exclude=["test"]),
		install_requires=[line.strip() for line in open("requirements.txt", "rt")],
		entry_points={
			# "console_scripts": [
			# 	"gffquant=gffquant.__main__:main",
			# 	"gffindex=gffquant.gff_indexer:main",
			# 	"collate_counts=gffquant.bin.collate_counts:main",
			# 	"split_table=gffquant.bin.split_table:main",
			# 	"build_gene_database=gffquant.bin.build_gene_database:main",
			# 	"build_domain_database=gffquant.bin.build_domain_database:main",
			# 	"build_bed_database=gffquant.bin.build_bed_database:main",
			# 	"build_custom_database=gffquant.bin.build_custom_database:main",
			# 	"collate_studies=gffquant.bin.collate_studies:main",
			# ],
		},
		package_data={},
		include_package_data=True,
		data_files=[],
	)
