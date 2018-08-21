
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

from .. import timer
from ..consts import day

class engine( object ):
    """The basic engine runs everything according to the world's time defined periods."""
    def __init__( self, world=None, exch=None, agents=None, **kwds ):
        super( engine, self ).__init__( **kwds )
        self.world		= world
        self.exchange		= exch
        self.agents		= agents

    def cycle( self, now ):
        for agent in self.agents:
            started		= timer()
            if agent.run( exch=self.exchange, now=now ):
                duration	= timer() - started
                logging.debug( "%s Agent %15s executed in %7.4fs",
                               self.world.format_now( now ), str( agent ), duration )
        self.exchange.execute_all( now=now )
        
    def run( self ):
        """ Give every agent a chance to do something on every time quanta, and then let
        the exchange solve for matching trades placed during that quanta."""
        for now in self.world.periods():
            self.cycle( now )


class engine_status( object ):
    """A mixin for an engine that logs a status on some interval (default: daily), eg.

        class my_engine( engine_status, engine ):
            pass
        with my_engine( ... ) as eng:
            eng.run()

    Override status method to output whatever status you want; just logs orders by default.
    """
    def __init__( self, status_period=None, **kwds ):
        super( engine_status, self ).__init__( **kwds )
        self.status_period	= day if status_period is None else status_period
        self.pernum		= None

    def __enter__( self ):
        return self
        
    def __exit__( self, *exc ):
        self.status()
        return False # Suppress no exceptions

    def status( self, now ):
        logging.info( "%s Orders:\n%s",
                      "Exit" if now is None else self.world.format_now( now ),
                      self.exchange.format_book() )

    def cycle( self, now ):
        super( engine_status, self ).cycle( now )
        pernow			= int( now // self.status_period )
        if pernow != self.pernum:
            self.pernum		= pernow
            self.status( now )
