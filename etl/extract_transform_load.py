#!/usr/bin/env python

"""
Module to support any and all Extract Transform Load operations from
SiriusXm into PySoSirius Historical DB. 
"""

# System packages
from copy import deepcopy
import logging

# installed packages
import pymongo
from pysosirius.sirius_playing import SiriusCurrentlyPlaying

# global, module level logger
log = logging.getLogger(__name__)

class ETL(object):
	"""
	Class for encapsulating all thing ETL for a channel

	Attributes:
        pss_channel (SiriusChannel): Class for channel metadata.
        database (MongoClient): DB connection.
        database_write (bool): True to write to DB.
        collection_name (str): name of channel collection in DB.
        __last_played (:obj:`Dict`, optional): Dict of last played song.

		__init__

        Initialize a wrapper for one channel's ETL functions

        Args:
            pss_channel (SiriusChannel): Sirius channel metadata
            database (:obj:`MongoClient`, optional): DB connex
            database_write (bool): write to db


	"""
	def __init__(self,
				pss_channel,
				database = None,
				database_write = True):
		super(ETL, self).__init__()

		# args
		self.pss_channel = pss_channel
		self.database = database
		self.database_write = database_write

		# computed values
		self.collection_name = "channel_" + str(self.pss_channel.channel)

		# internal data
		self.__last_played = None

		# internal setup
		self.__setup_db_structures()
		self.__update_last_played()

	@property
	def last_played_start(self):
		"""str: datetime of last played song"""

		if self.__last_played:
			return self.__last_played['datetime'][-1]

		return None

	def __update_last_played(self,last_played = {}):
		"""
		Update the last played data member

		Args:
		    last_played: Optional last played document

		Returns:
		    None
		"""

		if last_played:
			self.__last_played = last_played
		elif self.database:

			if 'last_played' in self.database.collection_names():

				self.__last_played = self.database['last_played'].find_one(
											{'_id':self.pss_channel.channel})
	
	def __setup_db_structures(self):
		"""
		Set up db structures for the channel's collection
		"""

		# create channel based indexes
		if self.database and self.database_write:

			collection = self.database[self.collection_name]

			collection.create_index([('artist.name',pymongo.TEXT),
									 ('song.name',pymongo.TEXT),
									 ('channels.id',pymongo.TEXT),
									 ('channels.number',pymongo.TEXT),
									 ('channels.name',pymongo.TEXT)])

			collection.create_index([('datetime', pymongo.DESCENDING)])

	def get_existing(self):
		"""
		Get an existing document int he DB

		Args:
		    None

		Returns:
		    Dict of existing document
		"""

		existing_doc = None

		if self.database:

			# criteria to search index for song match
			existing_filter = {'artist.name': self.pss_channel.currently_playing.artist_name,
								'song.name': self.pss_channel.currently_playing.song_name
								}

			# search english, case insensitive (1 is less strict)
			# TODO: what about spanish channels?
			existing_collation = {'locale': "en",
									'strength': 2
									}

			try:
				# will raise IndexError if no item in the collection exists
				existing_doc = self.database[self.collection_name].find(
								filter=existing_filter).collation(
									existing_collation)[0]
			except IndexError:
				pass
		
		return existing_doc

	def extract_transform_load(self):
		"""
		Driver for the ETL process
		"""

		# if the extraction was successful
		if self.__extract():
			new_doc, doc_updates = self.__transform()

			# theres always a new doc for newly switched to song
			if new_doc:
				log.info('Song: %s',
					self.pss_channel.currently_playing.song_name)
				self.__load(new_doc,doc_updates)
		else:
			log.error('Extracting Data for Channel: %s \n %s \n %s \n',
				self.pss_channel.name,
				self.pss_channel.url,
				self.pss_channel.currently_playing._get_url())

	def __extract(self):
		"""
		Hit sirius server for currently playing
		"""
		
		self.pss_channel.get_currently_playing()

		# return status of extraction
		return self.pss_channel.currently_playing.status

	def __transform(self):
		"""
		Merge XM data and local document structure
		"""

		# helper function to manipulate documents
		def transform_helper(extraction_data,existing_transformed_data=None):
			"""
			Transform an XM doc structure to the new structure or
			merge an XM doc structure and an existing together

			Args:
			    extraction_data: XM data struct
			    existing_transformed_data: to be stored, existing struct

			Returns:
			    Dict of new document
			"""

			ROOT_SONG_KEYS = SiriusCurrentlyPlaying.JSON_ROOT_MSG_DATA_KEYS['song']
			ATTRIBUTE_KEYS = SiriusCurrentlyPlaying.JSON_MSG_DATA_KEYS
			SONG_START_TIME = ROOT_SONG_KEYS + ATTRIBUTE_KEYS['start']

			if existing_transformed_data:

				new_transformed_data = deepcopy(existing_transformed_data)
			else:
				new_transformed_data = {}


			# index based fields
			new_transformed_data['album'] = {'name': SiriusCurrentlyPlaying.get_attribute(ROOT_SONG_KEYS+ATTRIBUTE_KEYS['album'],extraction_data)}
			new_transformed_data['song'] = {'name':  SiriusCurrentlyPlaying.get_attribute(ROOT_SONG_KEYS+ATTRIBUTE_KEYS['song'],extraction_data)}
			new_transformed_data['artist'] = {'name':  SiriusCurrentlyPlaying.get_attribute(ROOT_SONG_KEYS+ATTRIBUTE_KEYS['artist'],extraction_data)}

			# update last played if not already in list
			new_datetime = SiriusCurrentlyPlaying.get_attribute(SONG_START_TIME,extraction_data)
			if new_datetime not in new_transformed_data.get('datetime',[])[::-1]:
				new_transformed_data['datetime'] = new_transformed_data.get('datetime',[]) + [new_datetime]
			
			# update channel data if not already in list
			channel_data = {'id': SiriusCurrentlyPlaying.get_attribute(['channelMetadataResponse','metaData','channelId'],extraction_data),
							'number': SiriusCurrentlyPlaying.get_attribute(['channelMetadataResponse','metaData','channelNumber'],extraction_data),
							'name': SiriusCurrentlyPlaying.get_attribute(['channelMetadataResponse','metaData','channelName'],extraction_data)}

			if channel_data not in new_transformed_data.get('channels',[]):
				new_transformed_data['channels'] = new_transformed_data.get('channels',[]) + [channel_data]

			# non indexed fields
			new_transformed_data['play_count'] = new_transformed_data.get('play_count',0)+1

			image_list = []
			for artwork in SiriusCurrentlyPlaying.get_attribute(['channelMetadataResponse','metaData','currentEvent','song','creativeArts'],extraction_data):

				image_data = {}

				if (artwork.get('type',None) == 'IMAGE'
					and artwork.get('encrypted',None) == False):
					
					image_data['size'] = artwork['size']
					image_data['url'] = artwork['url']
					image_list.append(image_data)
					
			new_transformed_data['artwork'] = image_list

			return new_transformed_data

		# begin the transform
		if self.last_played_start != self.pss_channel.currently_playing.start:
			
			existing_doc = self.get_existing()

			if existing_doc:

				# generate the updated doc
				new_doc = transform_helper(self.pss_channel.currently_playing.data,existing_doc)

				doc_updates = {}
				#doc_updates.clear()

				# index values that should never change once a doc has been created
				# or we don't care to write their updates
				for key,value in new_doc.items():
					if key not in ['_id','album','song','artist','artwork']:
						doc_updates[key] = value

				return (new_doc,doc_updates)

			else:
				# we have a new song so insert it into the collection
				new_doc = transform_helper(self.pss_channel.currently_playing.data)
				return (new_doc,None)

		# its the same song, no new doc/no updates
		return (None,None)

	def __load(self,new_doc,doc_updates = {}):
		"""
		Save the new document or updated document to the db

		Args:
		    new_doc: newly formatted doc to be stored
		    doc_updates: dic of keywords to update an existing doc

		Returns:
		    None
		"""

		# make sure we log the last played on the channel
		# regardless of writing to the db or not
		self.__update_last_played(new_doc)

		if self.database and self.database_write:

			# update the channel specific song documents
			if doc_updates:

				# criteria to search index for song match
				existing_filter = {'artist.name': self.pss_channel.currently_playing.artist_name,
									'song.name': self.pss_channel.currently_playing.song_name
									}

				# search english, case insensitive (1 is less strict)
				# TODO: what about spanish channels?
				existing_collation = {'locale': "en",
										'strength': 2
										}

				self.database[self.collection_name].update_one(existing_filter,
																{'$set': doc_updates},
																collation=existing_collation)
			else:
				self.database[self.collection_name].insert_one(new_doc)

			# update the last played collection doc for this channel
			new_doc['_id'] = self.pss_channel.channel
			last_played_filter = {'_id':self.pss_channel.channel}

			# replace the old last song with the new,last song
			self.database[u'last_played'].replace_one(last_played_filter,
														new_doc,upsert=True)
