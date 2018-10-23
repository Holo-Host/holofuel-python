
# This file is part of Holo Fuel
# 
# Holo Fuel is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Holo Fuel is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Holo Fuel.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, print_function, division

__author__                      = "Perry Kundert"
__email__                       = "perry.kundert@holo.host"
__copyright__                   = "Copyright (c) 2018 Perry Kundert"
__license__                     = "GPLv3+"

import requests
import json

class restful( object ):
    """Access Holochain dApp via REST API."""
    def __init__( self, url=None, prefix=None ):
        self.url		= [ url or 'http://localhost:3141' ]
        self.prefix		= [ 'fn', 'transaction' ]


class holofuel_restful( restful ):
    def getLedgerState( self ):
        url			= '/'.join( self.url + self.prefix + [ 'getLedgerState' ] )
        r			= requests.get( url )
        assert r.status_code == 200, \
            "Failed w/ HTTP code {} for URL: {}".format( r.status_code, url )
        return json.loads( r.text )
