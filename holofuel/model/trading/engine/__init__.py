
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

import logging

class engine( object ):
    """The basic engine runs everything according to the world's time defined periods."""
    def __init__( self, world=None, exch=None, agents=None, **kwds ):
        super( engine, self ).__init__( **kwds )
        self.world		= world
        self.exchange		= exch
        self.agents		= agents

    def run( self ):
        """ Give every agent a chance to do something on every time quanta, and then let
        the exchange solve for matching trades placed during that quanta."""
        for now in self.world.periods():
            for agent in self.agents:
                agent.run( exch=self.exchange, now=now )
            self.exchange.execute_all( now=now )
