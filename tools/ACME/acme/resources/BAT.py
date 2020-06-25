#
#	BAT.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	ResourceType: mgmtObj:Battery
#

from .MgmtObj import *
from Constants import Constants as C
from Validator import constructPolicy
import Utils

# Attribute policies for this resource are constructed during startup of the CSE
attributePolicies = constructPolicy([ 
	'ty', 'ri', 'rn', 'pi', 'acpi', 'ct', 'lt', 'et', 'lbl', 'at', 'aa', 'daci', 
	'mgd', 'obis', 'obps', 'dc', 'mgs', 'cmlk',
	'btl', 'bts'
])


btsNORMAL			 = 1
btsCHARGING			 = 2
btsCHARGING_COMPLETE = 3
btsDAMAGED			 = 4
btsLOW_BATTERY		 = 5
btsNOT_INSTALLED	 = 6
btsUNKNOWN			 = 7


defaultBatteryLevel  = 100
defaultBatteryStatus = btsUNKNOWN

class BAT(MgmtObj):

	def __init__(self, jsn=None, pi=None, create=False):
		super().__init__(jsn, pi, C.tsBAT, C.mgdBAT, create=create, attributePolicies=attributePolicies)

		if self.json is not None:
			self.setAttribute('btl', defaultBatteryLevel, overwrite=False)
			self.setAttribute('bts', defaultBatteryStatus, overwrite=False)

