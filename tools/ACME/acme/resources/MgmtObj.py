#
#	MgmtObj.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	ResourceType: ManagementObject (base class for specializations)
#

from .Resource import *
import Utils


class MgmtObj(Resource):

	def __init__(self, jsn: dict, pi: str, mgmtObjType: str, mgd: int, create: bool = False, attributePolicies: dict = None) -> None:
		super().__init__(mgmtObjType, jsn, pi, C.tMGMTOBJ, create=create, attributePolicies=attributePolicies)
		
		if self.json is not None:
			self.setAttribute('mgd', mgd, overwrite=True)


	# Enable check for allowed sub-resources
	def canHaveChild(self, resource: Resource) -> bool:
		return super()._canHaveChild(resource, [ C.tSUB ])