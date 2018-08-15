import time
import random

from . import near
from trading import market, world_realtime, second, engine

def test_world_realtime():
    duration		= 1 * second
    delay		= random.uniform( .05, .2 )
    scale		= random.uniform( 0.5, 2.5 )
    wld			= world_realtime( duration=duration, scale=scale )

    times		= []
    class market_delay( market ):
        """A market that sleeps for 100ms on each execution"""
        def execute_all( self, now=None, **kwds ):
            super( market_delay, self ).execute_all( **kwds )
            times.append( now )
            time.sleep( delay )

    mkt			= market_delay( "EUR/USD" )
    eng			= engine( world=wld, exch=mkt, agents=[] )
    eng.run()

    # We should be w'in +/- 1 of our estimated number of quanta
    iterations		= duration / delay / scale
    assert iterations - 1 <= len( times ) <= iterations + 1

    # We could stop almost 1 delay * scale short of our duration (if
    # the next quanta would have put us over)
    assert duration - delay * scale < ( times[-1] - times[0] ) < duration
