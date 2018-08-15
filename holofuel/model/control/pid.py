
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

__author__                      = "Perry Kundert"
__email__                       = "perry.kundert@holo.host"
__copyright__                   = "Copyright (c) 2018 Perry Kundert"
__license__                     = "GPLv3+"

import collections
import math

from .. import timer, clamp


Kpid_t                  = collections.namedtuple( 'Kpid_t', ['Kp', 'Ki', 'Kd'] )
Lout_t                  = collections.namedtuple( 'Lout_t', ['lo', 'hi'] )

# 
# pid.controller
# 
class controller( object ):
    """Simple PID loop with Integral anti-windup, bumpless transfer."""
    def __init__( self, Kpid, setpoint=None, process=None, output=None,
                  Lout=( None, None ), now=None ):
        self.Kpid       = Kpid( 1, 1, 1 ) if Kpid is None else Kpid_t( *Kpid )
        # Convert Lout limits None to math.nan, which never satisfied </> comparison
        lo,hi           = (None,None) if Lout is None else Lout
        self.Lout	= Lout_t(( math.nan if lo is None else lo ),
                                 ( math.nan if hi is None else hi ))
        self.setpoint   = setpoint or 0
        self.process    = process or 0
        self.output     = output or 0
        self.bumpless( setpoint=setpoint, process=process, output=output, now=now )

    def bumpless( self, setpoint=None, process=None, output=None, now=None ):
        """Bumpless control transfer; compute I required to maintain steady-state output,
        and P such that a subsequent loop with idential setpoint/process won't produce a
        Differential output.
        """
        if setpoint is not None or self.setpoint is None:
            self.setpoint = setpoint or 0
        if process is not None or self.process is None:
            self.process = process or 0
        if output is not None or self.output is None:
            self.output  = output or 0

        self.now        = timer() if now is None else now

        self.P          = self.setpoint - self.process
        self.I		= 0
        if self.Kpid.Ki:
            self.I      = ( self.output - self.P * self.Kpid.Kp ) / self.Kpid.Ki
        self.D          = 0

    def loop( self, setpoint=None, process=None, now=None ):
        """Any change in setpoint? If our error (P - self.P) is increasing in a direction, and the
        setpoint moves in that direction, cancel that amount of the rate of change.  Quench Integral
        wind-up, if the output is saturated in either direction.  Finally clip the output drive
        to saturation limits.
        """
        dS              = 0
        if setpoint is not None:
            dS          = setpoint - self.setpoint
            self.setpoint = setpoint
        if process is not None:
            self.process = process
        if now is None:
            now         = timer()
        if now > self.now: # No contribution if no +'ve dt!
            dt          = now - self.now
            self.now    = now
            P           = self.setpoint - self.process # Proportional: setpoint and process value error
            I           = self.I + P * dt              # Integral:     total error under curve over time
            D           = ( P - self.P - dS ) / dt     # Derivative:   rate of change of error (net dS)
            self.output = P * self.Kpid.Kp + I * self.Kpid.Ki + D * self.Kpid.Kd
            self.P      = P
            if not ( self.output < self.Lout.lo and I < self.I ) and \
               not ( self.output > self.Lout.hi and I > self.I ):
                self.I  = I # Integral anti-windup; ignore I if saturated, and I moving in wrong direction
            self.D      = D
        return self.drive

    @property
    def drive( self ):
        """Limit drive by clamping raw self.output to any limits established in self.Lout"""
        if self.Lout.lo is None and self.Lout.hi is None:
            return self.output
        return clamp( self.output, self.Lout )

    def __repr__( self ):
       return "<%r: %+8.6f %s %+8.6f --> %+8.6f (%+8.6f) P: %+8.6f * %+8.6f, I: %+8.6f * %+8.6f, D: %+8.6f * %+8.6f>" % (
           self.now, self.process,
           '>' if self.process > self.setpoint else '<' if self.process > self.setpoint else '=',
           self.setpoint, self.drive, self.output,
           self.P, self.Kpid.Kp, self.I, self.Kpid.Ki, self.D, self.Kpid.Kd )
