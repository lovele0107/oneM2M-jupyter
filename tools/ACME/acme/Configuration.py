#
#	Configuration.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	Managing CSE configurations
#


import logging, configparser, re
from Constants import Constants as C


defaultConfigFile			= 'acme.ini'
defaultImportDirectory		= './init'
version						= '0.4.0'


class Configuration(object):
	_configuration				= {}

	@staticmethod
	def init(args = None):
		global _configuration

		import Utils	# cannot import at the top because of circel import

		# resolve the args, of any
		argsConfigfile			= args.configfile if args is not None and 'configfile' in args else defaultConfigFile
		argsLoglevel			= args.loglevel if args is not None and 'loglevel' in args else None
		argsDBReset				= args.dbreset if args is not None and 'dbreset' in args else False
		argsDBStorageMode		= args.dbstoragemode if args is not None and 'dbstoragemode' in args else None
		argsImportDirectory		= args.importdirectory if args is not None and 'importdirectory' in args else None
		argsAppsEnabled			= args.appsenabled if args is not None and 'appsenabled' in args else None
		argsRemoteCSEEnabled	= args.remotecseenabled if args is not None and 'remotecseenabled' in args else None


		config = configparser.ConfigParser(	interpolation=configparser.ExtendedInterpolation(),
											converters={'list': lambda x: [i.strip() for i in x.split(',')]}	# Convert csv to list
										  )
		config.read(argsConfigfile)

		try:
			Configuration._configuration = {
				'configfile'					: argsConfigfile,

				#
				#	HTTP Server
				#

				'http.listenIF'						: config.get('server.http', 'listenIF', 				fallback='127.0.0.1'),
				'http.port' 						: config.getint('server.http', 'port', 					fallback=8080),
				'http.root'							: config.get('server.http', 'root', 					fallback=''),
				'http.address'						: config.get('server.http', 'address', 					fallback='http://127.0.0.1:8080'),
				'http.multiThread'					: config.getboolean('server.http', 'multiThread', 		fallback=True),

				#
				#	Database
				#

				'db.path'							: config.get('database', 'path', 						fallback='./data'),
				'db.inMemory'						: config.getboolean('database', 'inMemory', 			fallback=False),
				'db.cacheSize'						: config.getint('database', 'cacheSize', 				fallback=0),		# Default: no caching
				'db.resetAtStartup' 				: config.getboolean('database', 'resetAtStartup',		fallback=False),

				#
				#	Logging
				#

				'logging.enable'					: config.getboolean('logging', 'enable', 				fallback=True),
				'logging.enableFileLogging'			: config.getboolean('logging', 'enableFileLogging', 	fallback=True),
				'logging.file'						: config.get('logging', 'file', 						fallback='./logs/cse.log'),
				'logging.level'						: config.get('logging', 'level', 						fallback='debug'),
				'logging.size'						: config.getint('logging', 'size', 						fallback=100000),
				'logging.count'						: config.getint('logging', 'count', 					fallback=10),		# Number of log files

				#
				#	CSE
				#

				'cse.type'							: config.get('cse', 'type',								fallback='IN'),		# IN, MN, ASN
				'cse.spid'							: config.get('cse', 'serviceProviderID',				fallback='acme'),
				'cse.csi'							: config.get('cse', 'cseID',							fallback='/id-in'),
				'cse.ri'							: config.get('cse', 'resourceID',						fallback='id-in'),
				'cse.rn'							: config.get('cse', 'resourceName',						fallback='cse-in'),
				'cse.resourcesPath'					: config.get('cse', 'resourcesPath', 					fallback=defaultImportDirectory),
				'cse.expirationDelta'				: config.getint('cse', 'expirationDelta', 				fallback=60*60*24*365),	# 1 year, in seconds
				'cse.originator'					: config.get('cse', 'originator',						fallback='CAdmin'),
				'cse.enableApplications'			: config.getboolean('cse', 'enableApplications', 		fallback=True),
				'cse.enableNotifications'			: config.getboolean('cse', 'enableNotifications', 		fallback=True),
				'cse.enableRemoteCSE'				: config.getboolean('cse', 'enableRemoteCSE', 			fallback=True),
				'cse.enableTransitRequests'			: config.getboolean('cse', 'enableTransitRequests',		fallback=True),
				'cse.sortDiscoveredResources'		: config.getboolean('cse', 'sortDiscoveredResources',	fallback=True),
				'cse.checkExpirationsInterval'		: config.getint('cse', 'checkExpirationsInterval',		fallback=60),		# Seconds

				#
				#	CSE Security
				#
				'cse.security.enableACPChecks'		: config.getboolean('cse.security', 'enableACPChecks', 	fallback=True),
				'cse.security.adminACPI'			: config.get('cse.security', 'adminACPI', 				fallback='acpAdmin'),
				'cse.security.defaultACPI'			: config.get('cse.security', 'defaultACPI', 			fallback='acpDefault'),
				'cse.security.csebaseAccessACPI'	: config.get('cse.security', 'csebaseAccessACPI', 		fallback='acpCSEBaseAccess'),

				#
				#	Remote CSE
				#

				'cse.remote.address'				: config.get('cse.remote', 'address', 					fallback=''),
				'cse.remote.root'					: config.get('cse.remote', 'root', 						fallback=''),
				'cse.remote.csi'					: config.get('cse.remote', 'cseID', 					fallback=''),
				'cse.remote.rn'						: config.get('cse.remote', 'resourceName', 				fallback=''),
				'cse.remote.checkInterval'			: config.getint('cse.remote', 'checkInterval', 			fallback=30),		# Seconds

				#
				#	Registrations
				#

				'cse.registration.allowedAEOriginators'	: config.getlist('cse.registration', 'allowedAEOriginators',	fallback=['C*','S*']),
				'cse.registration.allowedCSROriginators': config.getlist('cse.registration', 'allowedCSROriginators',	fallback=[]),


				#
				#	Statistics
				#

				'cse.statistics.writeIntervall'		: config.getint('cse.statistics', 'writeIntervall',		fallback=60),		# Seconds


				#
				#	Defaults for Container Resources
				#

				'cse.cnt.mni'						: config.getint('cse.resource.cnt', 'mni', 				fallback=10),
				'cse.cnt.mbs'						: config.getint('cse.resource.cnt', 'mbs', 				fallback=10000),

				#
				#	Defaults for Access Control Policies
				#

				'cse.acp.pv.acop'					: config.getint('cse.resource.acp', 'permission', 		fallback=63),
				'cse.acp.pvs.acop'					: config.getint('cse.resource.acp', 'selfPermission', 	fallback=51),
				'cse.acp.addAdminOrignator'			: config.getboolean('cse.resource.acp', 'addAdminOrignator',	fallback=True),


				#
				#	Web UI
				#

				'cse.webui.enable'					: config.getboolean('cse.webui', 'enable', 				fallback=True),
				'cse.webui.root'					: config.get('cse.webui', 'root', 						fallback='/webui'),


				#
				#	App: Statistics AE
				#
	
				'app.statistics.enable'				: config.getboolean('app.statistics', 'enable', 		fallback=True),
				'app.statistics.aeRN'				: config.get('app.statistics', 'aeRN', 					fallback='statistics'),
				'app.statistics.aeAPI'				: config.get('app.statistics', 'aeAPI', 				fallback='ae-statistics'),
				'app.statistics.fcntRN'				: config.get('app.statistics', 'fcntRN', 				fallback='statistics'),
				'app.statistics.fcntCND'			: config.get('app.statistics', 'fcntCND', 				fallback='acme.statistics'),
				'app.statistics.fcntType'			: config.get('app.statistics', 'fcntType', 				fallback='acme:csest'),
				'app.statistics.originator'			: config.get('app.statistics', 'originator',			fallback='C'),
				'app.statistics.intervall'			: config.getint('app.statistics', 'intervall', 			fallback=10),		# seconds

				#
				#	App: CSE Node 
				#

				'app.csenode.enable'				: config.getboolean('app.csenode', 'enable', 			fallback=True),
				'app.csenode.nodeRN'				: config.get('app.csenode', 'nodeRN', 					fallback='cse-node'),
				'app.csenode.nodeID'				: config.get('app.csenode', 'nodeID', 					fallback='cse-node'),
				'app.csenode.originator'			: config.get('app.csenode', 'originator',				fallback='CAdmin'),
				'app.csenode.batteryLowLevel'		: config.getint('app.csenode', 'batteryLowLevel',		fallback=20),		# percent
				'app.csenode.batteryChargedLevel'	: config.getint('app.csenode', 'batteryChargedLevel',	fallback=100),		# percent
				'app.csenode.intervall'				: config.getint('app.csenode', 'updateIntervall', 		fallback=60),		# seconds

			}
		except Exception as e:	# about when findings errors in configuration
			print('Error in configuration file: %s - %s' % (argsConfigfile, str(e)))
			return False

		# Read id-mappings
		if  config.has_section('server.http.mappings'):
			Configuration._configuration['server.http.mappings'] = config.items('server.http.mappings')
			#print(config.items('server.http.mappings'))

		# Some clean-ups and overrites

		# CSE type
		cseType = Configuration._configuration['cse.type'].lower()
		if  cseType == 'asn':
			Configuration._configuration['cse.type'] = C.cseTypeASN
		elif cseType == 'mn':
			Configuration._configuration['cse.type'] = C.cseTypeMN
		else:
			Configuration._configuration['cse.type'] = C.cseTypeIN

		# Loglevel from command line
		logLevel = Configuration._configuration['logging.level'].lower()
		logLevel = (argsLoglevel or logLevel) 	# command line args override config
		if logLevel == 'off':
			Configuration._configuration['logging.enable'] = False
			Configuration._configuration['logging.level'] = logging.DEBUG
		elif logLevel == 'info':
			Configuration._configuration['logging.level'] = logging.INFO
		elif logLevel == 'warn':
			Configuration._configuration['logging.level'] = logging.WARNING
		elif logLevel == 'error':
			Configuration._configuration['logging.level'] = logging.ERROR
		else:
			Configuration._configuration['logging.level'] = logging.DEBUG


		# Override DB reset from command line
		if argsDBReset is True:
			Configuration._configuration['db.resetAtStartup'] = True

		# Override DB storage mode from command line
		if argsDBStorageMode is not None:
			Configuration._configuration['db.inMemory'] = argsDBStorageMode == 'memory'

		# Override import directory from command line
		if argsImportDirectory is not None:
			Configuration._configuration['cse.resourcesPath'] = argsImportDirectory

		# Override app enablement
		if argsAppsEnabled is not None:
			Configuration._configuration['cse.enableApplications'] = argsAppsEnabled

		# Override remote CSE enablement
		if argsRemoteCSEEnabled is not None:
			Configuration._configuration['cse.enableRemoteCSE'] = argsRemoteCSEEnabled

		# Correct urls
		Configuration._configuration['cse.remote.address'] = Utils.normalizeURL(Configuration._configuration['cse.remote.address'])
		Configuration._configuration['http.address'] = Utils.normalizeURL(Configuration._configuration['http.address'])
		Configuration._configuration['http.root'] = Utils.normalizeURL(Configuration._configuration['http.root'])
		Configuration._configuration['cse.remote.root'] = Utils.normalizeURL(Configuration._configuration['cse.remote.root'])


		#
		#	Some sanity and validity checks
		#


		# check the csi format
		rx = re.compile('^/[^/\s]+') # Must start with a / and must not contain a further / or white space
		if re.fullmatch(rx, (val:=Configuration._configuration['cse.csi'])) is None:
			print('Configuration Error: Wrong format for [cse]:cseID: %s' % val)
			return False
		if re.fullmatch(rx, (val:=Configuration._configuration['cse.remote.csi'])) is None:
			print('Configuration Error: Wrong format for [cse.remote]:cseID: %s' % val)
			return False
		if len(Configuration._configuration['cse.remote.csi']) > 0 and len(Configuration._configuration['cse.remote.rn']) == 0:
			print('Configuration Error: Missing configuration [cse.remote]:resourceName')
			return False


		# Everything is fine
		return True


	@staticmethod
	def print():
		result = 'Configuration:\n'
		for kv in Configuration._configuration.items():
			result += '  %s = %s\n' % kv
		return result


	@staticmethod
	def all():
		return Configuration._configuration


	@staticmethod
	def get(key):
		if not Configuration.has(key):
			return None
		return Configuration._configuration[key]


	@staticmethod
	def set(key, value):
		Configuration._configuration[key] = value


	@staticmethod
	def has(key):
		return key in Configuration._configuration