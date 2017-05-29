from setuptools import setup, find_packages

setup(
	name='pysosiriusmongo',
	version='0.0.5',
	description='PySoSirius SiriusXM Song Storage',
	url='https://github.com/T-Santos/PySoSiriusMongo',
	author='Tyler Santos',
	author_email='1tsantos7+pysosirius@Gmail.com',
	license='MIT',
	packages=['pysosiriusmongo','pysosiriusmongo.etl'],
	# Project uses BeautifulSoup, requests and selenium to
	# parse webpages for new info not stored in the local db
	install_requires=['pysosirius','pymongo'],
	keywords="Sirius SiriusXM XM Music MongoDB",	
	classifiers=[
		# How mature is this project? Common values are
		'Development Status :: 1 - Planning',

		# Indicate who your project is intended for
		'Intended Audience :: Developers',

		# Pick your license as you wish (should match "license" above)
		 'License :: OSI Approved :: MIT License',

		# Specify the Python versions you support here. In particular, ensure
		# that you indicate whether you support Python 2, Python 3 or both.
		'Programming Language :: Python :: 2.7'
	])