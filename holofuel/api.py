
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
    def __init__( self, *args ): # eg. 'http://localhost:3141', 'fn', 'transaction'
        self.base		= list( args ) or [ 'http://localhost:3141', 'fn', 'transaction' ]

    def url( self, *args ):
        """Pass the term(s) of the URL; eg. url( 'v1', 'some', 'endpoint' )  """
        return '/'.join( self.base + list( args ))

    def post( self, *args, **kwds ):
        """Post a request to the API endpoint specified in *args", with the request data/json in keywords
        (passed to requests.post, unmodified).  Raw POST data (eg. string) in the data=...,
        json=... will be encoded to a JSON string for POST.

        For example:
            self.post( 'endpoint', json={ "a": 1 } )

        """
        url			= self.url( *args )
        r			= requests.post( url, **kwds )
        assert r.status_code == 200, \
            "Failed w/ HTTP code {} for URL: {} w/ data {!r}".format( r.status_code, url, data )
        return r


class holofuel_restful( restful ):

    def setLimits( self, data ):
        """The setLimits API expects JSON data, and returns response encoded as JSON"""
        return self.post( 'setLimits', json=data ).json()

    def getLedgerState( self ):
        return self.post( 'getLedgerState' ).json()
