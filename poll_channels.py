#!/usr/bin/env python

""" 
Used in conjunction with PySoSirius package (necessary channel metadata).
Useful for compiling currently playing song data from Sirius XM 
and storing it a document DB for historical records to be queried later. 

Poll for all PySoSirius channels (sqlite db) with no logging
	python poll_channels.py

Poll specific channels with no logging
	python poll_channels.py -C 56 53

Poll channels with logging
	python poll_channels.py -C 56 -ll INFO

Poll channels no db interaction - useful for testing
for just to getting currently playing data with no need or use
for more than last song played and current song playing
	python poll_channels -C 56 -ll DEBUG --db_write_disabled

"""
import datetime
import time
import threading
import logging
from argparse import ArgumentParser

import pymongo

from pysosirius.pysosirius import PySoSirius
from etl.extract_transform_load import ETL

def extraction(etl_channel):
	"""
	Launch a thread to start compiling played songs per channel

	Args:
	    etl_channel: ETL - wrapper for etl of one channel

	Returns:
	    None

	Raises:
	    None
	"""
	while True:
		etl_channel.extract_transform_load()
		time.sleep(60)

def get_pss_channels(channels=None):
	"""
	Given (optional) channel numbers, get the PySoSirius metadata

	Args:
	    channels: int - List of channel numbers.

	Returns:
	    list of SeriousChannel objects

	Raises:
	    None
	"""

	py_so_sirius = PySoSirius()
	pss_channels = []

	if channels:

		# we want specific channels
		for channel in channels:
			pss_channels.append(py_so_sirius.get_channel(channel=channel))
	else:

		# we want them all
		pss_channels = py_so_sirius.get_channels()

	return pss_channels

def start_channel_compile(channels,database=None,db_write_enabled=True):
	"""
	Launch a threads to start compiling played songs per channel

	Args:
	    channels: SiriusChannel - List of channel objects.
	    database: MongoClient - connection to specific db.
		db_write_enabled: bool - should writing be enabled

	Returns:
	    None

	Raises:
	    None
	"""

	for pss_channel in channels:

		etl_channel = ETL(pss_channel,
						database = database,
						database_write = db_write_enabled)

		# kick off the compile thread
		etl_thread = threading.Thread(name = pss_channel.channel,
									target = extraction,
									args = (etl_channel,))
		etl_thread.daemon = True
		etl_thread.start()

def main(**kwargs):
	"""
	Driver of command line interface. Sets up DB connx and channel metadata
	to prep it for compile.

	kwargs:
	    db_ip: str - ip address for the db connection 
	    db_port: int - port to connect to db
	    db_write_disabled: bool - should we be writing to the db

	Returns:
	    None

	Raises:
	    None
	"""

	# Connect to datbase server
	client = pymongo.MongoClient(kwargs['db_ip'],kwargs['db_port'])

	# connect to database
	database = client['channel_data']

	# get channels of interest
	pss_channels = get_pss_channels(kwargs['channels'])

	# start compile threads
	start_channel_compile(pss_channels,database,not(kwargs['db_write_disabled']))

	# loop infinitum - used to keep daemon threads running
	while True:
		logger.info('Minute: %d',(1440 - datetime.datetime.now().minute))
		time.sleep(60)
		pass

if __name__ == '__main__':
	"""
	Main setup of capturing commandline args, and general setup of logging.
	"""

	parser = ArgumentParser(description='Populate Database from Siriux XM')

	# General args
	parser.add_argument('-ll', '--log_level',
						type=str,
						choices=['DEBUG','INFO','WARNING','ERROR','CRITICAL'],
						help='Set the logging level')

	# Compile args
	parser.add_argument('-C', '--channels',
						type=int,
						nargs = '*',
						help='Override channels to compile')

	# DB Args
	parser.add_argument('-DBIP', '--db_ip',
						type=str,
						help='IP address for db connection',
						default = '127.0.0.1')

	parser.add_argument('-DBP', '--db_port',
						type=int,
						help='Port address for db connection',
						default = '27017')

	parser.add_argument('-DBW', '--db_write_disabled',
						action = 'store_true',
	 					help='True to disable writing to the db')

	# Get all args from commandline
	args = parser.parse_args()
 	args_dict = vars(args)

 	# Set up global logger
 	if args.log_level:
 		logger = logging.getLogger()
		handler = logging.StreamHandler()
		formatter = logging.Formatter(
		        		'[%(levelname)s] [%(threadName)s] %(message)s')
		handler.setFormatter(formatter)
		logger.addHandler(handler)
		logger.setLevel(args.log_level)

 	# remove any args not needed
 	args_dict.pop('log_level')

 	# pass remaining args to main so it can do what it needs
	main(**args_dict)