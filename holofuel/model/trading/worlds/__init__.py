
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

import datetime
import logging

from .. import timer

from ..consts import * # day, ...

class world( object ):
    """The basic world that runs its clock with no delay."""
    def __init__( self, duration=day, start=None, quanta=minute, **kwds ):
        super( world, self ).__init__( **kwds )
        self.start		= start or 0
        self.duration		= duration
        self.quanta		= quanta	# Could be None for some worlds
        self.reset()

    def __str__( self ):
        return "World starting @ {} w/ duration {}, quanta {}: {}".format(
            self.start, self.duration, self.quanta, self.now )

    @property
    def done( self ):
        return self.duration is not None and self.now >= self.start + self.duration

    def reset( self ):
        self.now		= self.start

    def advance( self ):
        self.now	       += self.quanta

    def periods( self ):
        """Generate the sequence of time quanta 'til done, beginning with the start timestamp."""
        print( "Simulating {}".format( str( self )))
        while not self.done:
            yield self.now
            self.advance()

    def format_offset( self, dt, ms=True, symbols=('','') ):
        """Convert a floating point number of -'ve/+'ve seconds into 'h:mm:ss.sss'"""
        return ( ( symbols[0] if dt < 0 else symbols[1] )
                 + "%2dd "
                 + "%2d:%02d:"
                 + ( "%06.3f" if ms else "%02d" )) % (
            int( abs( dt ) // day ),
            int( abs( dt ) % day  // hour ),
            int( abs( dt ) % hour // minute ),
            abs( dt ) % minute )

    def format_now( self, now, ms=True ):
        return self.format_offset( now, ms=ms )
        
class world_realtime( world ):
    """We advance in real-time x <scale> for the specified duration. """
    def __init__( self, duration=minute, start=None, quanta=None, scale=None, **kwds ):
        assert quanta is None, \
            "The realtime world's quanta cannot be specified; perhaps use scale instead?"
        if start is None:
            start		= timer()	# Default to Wall-clock time
        super( world_realtime, self ).__init__( duration=duration, start=start, quanta=quanta, **kwds )
        self._scale		= scale if scale else 1 # None/0 --> advance in real time.

    def __str__( self ):
        return "real-time x {} ".format( self.scale ) + super( world_realtime, self ).__str__()

    @property
    def scale( self ):
        return self._scale
    @scale.setter
    def scale( self, value ):
        """When adjusting scale, we need to create a new fake 'start' time, such that the adjusted duration scale results
        in the current 'now' time.

        """
        if value != self._scale:
            duration		= self.now - self.start # eg. 1hr at scale x 1
            duration	       *= self._scale / value	#   at new scale x 2, duration now .5hr
            if duration:
                self.start	= self.now - duration	#   so, make-believe we started 1/2 ago instead
            self.scale		= value
    
    def advance( self ):
        """Advances 'now' time at some multiple of real-time."""
        duration		= timer() - self.start
        self.now		= self.start + duration * self.scale
    
    def format_now( self, now, ms=True ):
        return ' + '.join( ( datetime.utcfromtimestamp( self.start ).strftime( '%Y-%m-%d %H:%M:%S UTC' ),
                             super( world_realtime, self ).format_now( now - self.start, ms=ms ) ) )

