#
#	RemoteCSEManager.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	This entity handles the registration to remote CSEs as well as the management
#	of remotly registered CSEs in this CSE. It also handles the forwarding of
#	transit requests to remote CSEs.
#


import requests, json, urllib.parse
from typing import List, Tuple
from flask import Request
from Configuration import Configuration
from Logging import Logging
from Constants import Constants as C
import Utils, CSE
from resources import CSR, CSEBase
from resources.Resource import Resource
from helpers.BackgroundWorker import BackgroundWorker


class RemoteCSEManager(object):

	def __init__(self) -> None:
		self.csetype 					= Configuration.get('cse.type')
		self.isConnected 				= False
		self.remoteAddress				= Configuration.get('cse.remote.address')
		self.remoteRoot 				= Configuration.get('cse.remote.root')
		self.remoteCsi					= Configuration.get('cse.remote.csi')
		self.remoteCseRN				= Configuration.get('cse.remote.rn')
		self.originator					= Configuration.get('cse.csi')	# Originator is the own CSE-ID
		self.worker:BackgroundWorker	= None
		self.checkInterval				= Configuration.get('cse.remote.checkInterval')
		self.cseCsi						= Configuration.get('cse.csi')
		self.remoteCSEURL				= '%s%s/~%s/%s' % (self.remoteAddress, self.remoteRoot, self.remoteCsi, self.remoteCseRN)
		self.remoteCSRURL				= '%s%s' % (self.remoteCSEURL, self.cseCsi)
		Logging.log('RemoteCSEManager initialized')


	def shutdown(self) -> None:
		self.stop()
		Logging.log('RemoteCSEManager shut down')


	#
	#	Connection Monitor
	#

	# Start the monitor in a thread. 
	def start(self) -> None:
		if not Configuration.get('cse.enableRemoteCSE'):
			return;
		Logging.log('Starting remote CSE connection monitor')
		self.worker = BackgroundWorker(self.checkInterval, self.connectionMonitorWorker, 'remoteConnectionMonitor')
		self.worker.start()


	# Stop the monitor. Also delete the CSR resources on both sides
	def stop(self) -> None:
		if not Configuration.get('cse.enableRemoteCSE'):
			return;
		Logging.log('Stopping remote CSE connection monitor')

		# Stop the thread
		if self.worker is not None:
			self.worker.stop()

		# Remove resources
		if self.csetype in [ C.cseTypeASN, C.cseTypeMN ]:
			self._deleteRemoteCSR()	# delete remote CSR. Ignore result
		csr, rc, _ = self._retrieveLocalCSR()	# retrieve local CSR
		if rc == C.rcOK:
			self._deleteLocalCSR(csr[0])		# delete local CSR


	#
	#	Check the connection, and presence and absence of CSE and CSR in a 
	#	thread periodically.
	#	
	#	It works like this for connections for an ASN or MN to the remote CSE:
	#	
	#	Is there is a local <remoteCSE> for a remote <CSEBase>?
	#		- Yes: Is there a remote <remoteCSE>?
	#			- Yes: 
	#				- Retrieve the remote <CSEBase>.
	#				- Has the remote <CSEBase> been modified?
	#					- Yes: 
	#						- Update the local <remoteCSE>
	#				- Retrieve the local <CSEBase>
	#				- Has the local <CSEBase> been modified?
	#					- Yes: 
	#						-Update the remote <remoteCSE>
	#			- No: 
	#				- Delete a potential local <remoteCSE>
	#				- Create a remote <remoteCSE>
	#					- Success:
	#						- Retrieve the remote <CSEBase>
	#						- Create a local <remoteCSE> for it
	#		- No: 
	#			- Delete a potential remote <remoteCSE>
	#			- Create a new remote <remoteCSE>
	#				- Success:
	#					- Retrieve the remote <CSEBase>
	#					- Create a local <remoteCSE> for it
	#					- Create a local <acp> for the local <remoteCSE>
	#					- Create a local <acp> for the local <CSEBase> with the remote cseID
	#		

	def connectionMonitorWorker(self) -> bool:
		Logging.logDebug('Checking connections to remote CSEs')
		try:
			# Check the current state of the connection to the "upstream" CSEs
			if self.csetype in [ C.cseTypeASN, C.cseTypeMN ]:
				self._checkOwnConnection()

			# Check the liveliness of other CSR connections
			if self.csetype in [ C.cseTypeMN, C.cseTypeIN ]:
				self._checkCSRLiveliness()
		except Exception as e:
			Logging.logErr('Exception: %s' % e)
			# import traceback
			# Logging.logErr(traceback.format_exc())
			return True
		return True


	# Check the connection for this CSE to the remote CSE.
	def _checkOwnConnection(self) -> None:
		# first check whether there is already a local CSR
		localCSRs, rc, _ = self._retrieveLocalCSR()
		localCSR = localCSRs[0] # hopefully, there is only one upstream CSR+
		if rc == C.rcOK:
			remoteCSR, rc, _ = self._retrieveRemoteCSR()	# retrieve own
			if rc == C.rcOK:
				# own CSR is still in remote CSE, so check for changes in remote CSE
				remoteCSE, rc, _ = self._retrieveRemoteCSE()
				if rc == C.rcOK:
					if remoteCSE.isModifiedSince(localCSR):	# remote CSE modified
						self._updateLocalCSR(localCSR, remoteCSE)
						Logging.log('Local CSR updated')
				localCSE, _, _ = Utils.getCSE()
				if localCSE.isModifiedSince(remoteCSR):	# local CSE modified
					self._updateRemoteCSR(localCSE)
					Logging.log('Remote CSR updated')

			else:
				# Potential disconnect
				self._deleteLocalCSR(localCSR)	# ignore result
				_, rc, _ = self._createRemoteCSR()
				if rc == C.rcCreated:
					remoteCSE, rc, _ = self._retrieveRemoteCSE()
					if rc == C.rcOK:
						self._createLocalCSR(remoteCSE)
						Logging.log('Remote CSE connected')
				else:
					Logging.log('Remote CSE disconnected')
		
		else:
			# No local CSR, so try to delete an optional remote one and re-create everything. 
			_, rc, _ = self._deleteRemoteCSR()					# delete potential remote CSR
			if rc in [C.rcDeleted, C.rcNotFound]:
				_, rc, _ = self._createRemoteCSR()				# create remote CSR
				if rc == C.rcCreated:
					remoteCSE, rc, _ = self._retrieveRemoteCSE()	# retrieve remote CSE
					if rc == C.rcOK:
						self._createLocalCSR(remoteCSE) 		# create local CSR including ACPs to local CSR and local CSE
						Logging.log('Remote CSE connected')


	#	Check the liveliness of all remote CSE's that are connected to this CSE.
	#	This is done by trying to retrie a remote CSR. If it cannot be retrieved
	#	then the related local CSR is removed.
	def _checkCSRLiveliness(self) -> None:
		localCsrs, rc, msg = self._retrieveLocalCSR(own=False)
		for localCsr in localCsrs:
			for url in (localCsr.poa or []):
				if Utils.isURL(url):
					cse, rc, msg = self._retrieveRemoteCSE(url='%s%s' % (url, localCsr.csi ))
					if rc != C.rcOK:
						Logging.logWarn('Remote CSE unreachable. Removing CSR: %s' % localCsr.rn if localCsr is not None else '')
						self._deleteLocalCSR(localCsr)


	#
	#	Local CSR
	#

	def _retrieveLocalCSR(self, csi: str = None, own: bool = True) -> Tuple[List[Resource], int, str]:
		localCsrs = CSE.dispatcher.directChildResources(pi=Configuration.get('cse.ri'), ty=C.tCSR)
		if csi is None:
			csi = self.remoteCsi
		Logging.logDebug('Retrieving local CSR: %s' % csi)
		if own:
			for localCsr in localCsrs:
				if (c := localCsr.csi) is not None and c == csi:
					return [localCsr], C.rcOK, None
			return [None], C.rcBadRequest, 'local CSR not found'
		else:
			result = []
			for localCsr in localCsrs:
				if (c := localCsr.csi) is not None and c == csi:
					continue
				result.append(localCsr)
			return result, C.rcOK, None


	def _createLocalCSR(self, remoteCSE: Resource) -> Tuple[Resource, int, str]:
		Logging.logDebug('Creating local CSR: %s' % remoteCSE.ri)

		# copy local CSE attributes into a new CSR
		localCSE, _, _ = Utils.getCSE()
		csr = CSR.CSR(pi=localCSE.ri, rn=remoteCSE.ri)	# remoteCSE.ri as name!
		self._copyCSE2CSE(csr, remoteCSE)
		csr['ri'] = remoteCSE.ri 						# set the ri to the remote CSE's ri
		
		# add local CSR and ACP's
		if (res := CSE.dispatcher.createResource(csr, localCSE))[0] is None:
			return res # Problem
		if not CSE.registration.handleCSRRegistration(csr, remoteCSE.csi):
			return None, C.rcBadRequest, 'cannot register CSR'
		return CSE.dispatcher.updateResource(csr, doUpdateCheck=False)



	def _updateLocalCSR(self, localCSR: Resource, remoteCSE: Resource) -> Tuple[Resource, int, str]:
		Logging.logDebug('Updating local CSR: %s' % localCSR.rn)
		# copy attributes
		self._copyCSE2CSE(localCSR, remoteCSE)
		return CSE.dispatcher.updateResource(localCSR)


	def _deleteLocalCSR(self, localCSR: Resource) -> Tuple[Resource, int, str]:
		Logging.logDebug('Deleting local CSR: %s' % localCSR.ri)

		if not CSE.registration.handleCSRDeRegistration(localCSR):
			return None, C.rcBadRequest, 'cannot deregister CSR'

		# Delete local CSR
		return CSE.dispatcher.deleteResource(localCSR)


	#
	#	Remote CSR 
	#

	def _retrieveRemoteCSR(self) -> Tuple[Resource, int, str]:
		Logging.logDebug('Retrieving remote CSR: %s' % self.remoteCsi)
		jsn, rc, msg = CSE.httpServer.sendRetrieveRequest(self.remoteCSRURL, self.originator)
		if rc not in [C.rcOK]:
			return None, rc, msg
		return CSR.CSR(jsn), C.rcOK, None


	def _createRemoteCSR(self) -> Tuple[Resource, int, str]:
		Logging.logDebug('Creating remote CSR: %s' % self.remoteCsi)
		
		# get local CSEBase and copy relevant attributes
		localCSE, _, _ = Utils.getCSE()
		csr = CSR.CSR(rn=localCSE.ri) # ri as name!
		self._copyCSE2CSE(csr, localCSE)
		csr['ri'] = self.cseCsi							# override ri with the own cseID
		csr['cb'] = Utils.getIdFromOriginator(localCSE.csi)	# only the stem
		for _ in ['ty','ri', 'ct', 'lt']: del(csr[_])	# remove a couple of attributes
		data = json.dumps(csr.asJSON())

		# Create the <remoteCSE> in the remote CSE
		Logging.logDebug('Creating remote CSR at: %s url: %s' % (self.remoteCsi, self.remoteCSEURL))	
		jsn, rc, msg = CSE.httpServer.sendCreateRequest(self.remoteCSEURL, self.originator, ty=C.tCSR, data=data)
		if rc not in [C.rcCreated, C.rcOK]:
			if rc != C.rcAlreadyExists:
				Logging.logDebug('Error creating remote CSR: %d' % rc)
			return None, rc, 'cannot create remote CSR'
		Logging.logDebug('Remote CSR created: %s' % self.remoteCsi)

		return None, C.rcCreated, None


	def _updateRemoteCSR(self, localCSE: Resource) -> Tuple[Resource, int, str]:
		Logging.logDebug('Updating remote CSR: %s' % self.remoteCsi)
		csr = CSR.CSR()
		self._copyCSE2CSE(csr, localCSE)
		del csr['acpi']			# remove ACPI (don't provide ACPI in updates...a bit)
		data = json.dumps(csr.asJSON())

		jsn, rc, msg = CSE.httpServer.sendUpdateRequest(self.remoteCSRURL, self.originator, data=data)
		if rc not in [C.rcUpdated, C.rcOK]:
			if rc != C.rcAlreadyExists:
				Logging.logDebug('Error updating remote CSR: %d' % rc)
			return None, rc, 'cannot update remote CSR'
		Logging.logDebug('Remote CSR updated: %s' % self.remoteCsi)
		return CSR.CSR(jsn), C.rcUpdated, None



	def _deleteRemoteCSR(self) -> Tuple[Resource, int, str]:
		Logging.logDebug('Deleting remote CSR: %s url: %s' % (self.remoteCsi, self.remoteCSRURL))
		jsn, rc, msg = CSE.httpServer.sendDeleteRequest(self.remoteCSRURL, self.originator)
		if rc not in [C.rcDeleted, C.rcOK]:	
			return None, rc, 'cannot delete remote CSR'
		Logging.log('Remote CSR deleted: %s' % self.remoteCsi)
		return None, C.rcDeleted, None


	#
	#	Remote CSE
	#

	# Retrieve the remote CSE
	def _retrieveRemoteCSE(self, url: str = None) -> Tuple[Resource, int, str]:
		url = (url or self.remoteCSEURL)
		Logging.logDebug('Retrieving remote CSE from: %s url: %s' % (self.remoteCsi, url))	
		jsn, rc, msg = CSE.httpServer.sendRetrieveRequest(url, self.originator)
		if rc not in [C.rcOK]:
			return None, rc, msg
		return CSEBase.CSEBase(jsn), C.rcOK, None


	#########################################################################

	#
	#	Handling of Transit requests. Forward requests to the resp. remote CSE's.
	#

	def handleTransitRetrieveRequest(self, request: Request, id: str, origin: str) -> Tuple[dict, int, str]:
		""" Forward a RETRIEVE request to a remote CSE """
		if (url := self._getForwardURL(id)) is None:
			return None, C.rcNotFound, 'forward URL not found for id: %s' % id
		if len(request.args) > 0:	# pass on other arguments, for discovery
			url += '?' + urllib.parse.urlencode(request.args)
		Logging.log('Forwarding Retrieve/Discovery request to: %s' % url)
		return CSE.httpServer.sendRetrieveRequest(url, origin)


	def handleTransitCreateRequest(self, request: Request, id: str, origin: str, ty: int) -> Tuple[dict, int, str]:
		""" Forward a CREATE request to a remote CSE. """
		if (url := self._getForwardURL(id)) is None:
			return None, C.rcNotFound, 'forward URL not found for id: %s' % id
		Logging.log('Forwarding Create request to: %s' % url)
		return CSE.httpServer.sendCreateRequest(url, origin, data=request.data, ty=ty)


	def handleTransitUpdateRequest(self, request: Request, id: str, origin: str) -> Tuple[dict, int, str]:
		""" Forward an UPDATE request to a remote CSE. """
		if (url := self._getForwardURL(id)) is None:
			return None, C.rcNotFound, 'forward URL not found for id: %s' % id
		Logging.log('Forwarding Update request to: %s' % url)
		return CSE.httpServer.sendUpdateRequest(url, origin, data=request.data)


	def handleTransitDeleteRequest(self, id: str, origin: str) -> Tuple[dict, int, str]:
		""" Forward a DELETE request to a remote CSE. """
		if (url := self._getForwardURL(id)) is None:
			return None, C.rcNotFound, 'forward URL not found for id: %s' % id
		Logging.log('Forwarding Delete request to: %s' % url)
		return CSE.httpServer.sendDeleteRequest(url, origin)


	def isTransitID(self, id: str) -> bool:
		""" Check whether an ID is a targeting a remote CSE via a CSR. """
		if Utils.isSPRelative(id):
			ids = id.split("/")
			return len(ids) > 0 and ids[0] != self.cseCsi[1:]
		elif Utils.isAbsolute(id):
			ids = id.split("/")
			return len(ids) > 2 and ids[2] != self.cseCsi[1:]
		return False


	def _getForwardURL(self, path: str) -> str:
		""" Get the new target URL when forwarding. """
		r, pe = self._getCSRFromPath(path)
		if r is not None and (poas := r.poa) is not None and len(poas) > 0:
			return '%s/~/%s' % (poas[0], '/'.join(pe[1:]))	# TODO check all available poas.
		return None


	def _getCSRFromPath(self, id: str) -> Tuple[Resource, List[str]]:
		""" Try to get a CSR even from a longer path (only the first 2 path elements are relevant). """
		if id is None:
			return None, None
		ids = id.split("/")
		Logging.logDebug("CSR ids: %s" % ids)
		if Utils.isSPRelative(id):
			r, _, _ = CSE.dispatcher._retrieveResource(ri=ids[1])
		elif Utils.isAbsolute(id):
			r, _, _ = CSE.dispatcher._retrieveResource(ri=ids[2])
		else:
			r, _, _ = CSE.dispatcher._retrieveResource(ri=id)
		return r, ids

		#pathElements = id.split('/')
		#if len(pathElements) <= 2:
		#	return (None, None)
		#if pathElements[0] == '_' and len(pathElements) >= 5:	# handle SP absolute addressing
		#	id = '%s/%s' % (pathElements[3], pathElements[4])
		#elif pathElements[0] == '~' and len(pathElements) >= 4:	# handle SP relative addressing
		#	id = '%s/%s' % (pathElements[2], pathElements[3])
		#else:
		#	id = '%s/%s' % (pathElements[0], pathElements[1])
		#(r, rc) = CSE.dispatcher.retrieveResource(id)
		#return (r, pathElements)


	#########################################################################


	def _copyCSE2CSE(self, target: Resource, source: Resource) -> None:
		if 'csb' in source:
			target['csb'] = self.remoteCSEURL
		if 'csi' in source:
			target['csi'] = source.csi
		if 'cst' in source:
			target['cst'] = source.cst
		if 'csz' in source:
			target['csz'] = source.csz
		if 'lbl' in source:
			target['lbl'] = source.lbl
		if 'nl' in source:
			target['nl'] = source.nl
		if 'poa' in source:
			target['poa'] = source.poa
		# if 'rn' in source:
		# 	target['rn'] = source.rn
		if 'rr' in source:
			target['rr'] = source.rr
		if 'srt' in source:
			target['srt'] = source.srt
		if 'srv' in source:
			target['srv'] = source.srv
		if 'st' in source:
			target['st'] = source.st

