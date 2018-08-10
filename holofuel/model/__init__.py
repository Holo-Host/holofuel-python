
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
__email__                       = "perry@kundert.ca"
__copyright__                   = "Copyright (c) 2018 Perry Kundert"
__license__                     = "GPLv3+"

__all__                         = ["control", "trading"]

import sys
import time
import math

# 
# model.timer
# 
# Select platform appropriate timer function
# 
if sys.platform == 'win32':
    # On Windows, the best timer is time.clock
    timer 			= time.clock
else:
    # On most other platforms the best timer is time.time
    timer			= time.time

# 
# model.nan	-- IEEE NaN (Not a Number)
# model.isnan	-- True iff the provided value is nan
# model.inf	-- IEEE inf (Infinity)
# model.isinf	-- True iff the provided value is inf
# 
#     Augment math with some useful constants.  Note that IEEE NaN is the
# only floating point number that won't equal itself.
# 
#     Numpy has these, but we can't assume it is available.
# 
if hasattr( math, 'nan' ):
    nan                         = math.nan
else:
    nan                         = float( 'nan' )
    math.nan                    = nan
if hasattr( math, 'isnan' ):
    isnan                       = math.isnan
else:
    def isnan( f ):
        return f != f
    math.isnan = isnan

if hasattr( math, 'inf' ):
    inf				= math.inf
else:
    inf				= float( 'inf' )
    math.inf			= inf
if hasattr( math, 'isinf' ):
    isinf			= math.isinf
else:
    def isinf( f ):
        return abs( f ) == inf
    math.isinf = isinf

# 
# model.near    -- True iff the specified values are within 'significance' of each-other
# 
def near( a, b, significance = 1.0e-4 ):
    """ Returns True iff the difference between the values is within the factor 'significance' of
    one of the original values.  Default is to within 4 decimal places. """
    return abs( a - b ) <= significance * max( abs( a ), abs( b ))

# 
# model.clamp   -- Clamps a value to within a tuple of limits.
# 
#     Limits that are None/math.nan are automatically ignored, with no special code (comparisons
# against NaN always return False).
# 
#     The ordering of 'lim' is assumed to be (min, max).  We don't attempt to reorder, because 'lim'
# may contain NaN.
# 
def clamp( val, lim ):
    """ Limit val to between 2 (optional None or if nan, because no value is < or > nan) limits """
    if ( lim[0] is not None and val < lim[0] ):
        return lim[0]
    if ( lim[1] is not None and val > lim[1] ):
        return lim[1]
    return val

# 
# sort order key=... methods
# 
# natural	-- Strings containing numbers sort in natural order
# nan_first	-- NaN/None sorts lower than any number
# nan_last	-- NaN/None sorts higher than any number
# 
def natural( string ):
    '''
    A natural sort key helper function for sort() and sorted() without
    using regular expressions or exceptions.

    >>> items = ('Z', 'a', '10th', '1st', '9')
    >>> sorted(items)
    ['10th', '1st', '9', 'Z', 'a']
    >>> sorted(items, key=natural)
    ['1st', '9', '10th', 'a', 'Z']    
    '''
    it = type( 1 )
    r = []
    for c in string:
        if c.isdigit():
            d = int( c )
            if r and type( r[-1] ) == it: 
                r[-1] = r[-1] * 10 + d
            else: 
                r.append( d )
        else:
            r.append( c.lower() )
    return r

def non_value( number ):
    return number is None or isnan( number )

def nan_first( number ):
    if non_value( number ):
        return -inf
    return number

def nan_last( number ):
    if non_value( number ):
        return inf
    return number

# 
# scale         -- Transform a value from one range to another, without clipping
#
#     No math.nan allowed or zero-sized domains or ranges.  Works for either increasing or
# decreasing ordering of domains or ranges.  If clamped, we will ensure that the rng is (re)ordered
# appropriately.
# 
#     If non-unity exponent is provided, then the input domain is raised to the appropriate power
# during the mapping.  This allows us to map something like (25,40)->(0,1) with a curve such as:
# 
#   1 |              .
#     |             .
#     |           ..
#     |        ...
#     |   .....
#   0 +---------------
#     2              4
#     5              0
# 
# 
def scale( val, dom, rng, clamped=False, exponent=1 ):
    """Map 'val' from domain 'dom', to new range 'rng', optionally with an exponential scaling.  If a
    non-unity exponent is provided, then the input value is also clamped to the input domain (and
    its order is asserted) since raising -'ve values to arbitrary exponents will usually have very
    unexpected results.  Otherwise, at unity exponent, allow -'ve values and out-of-order ranges.

    """
    if exponent != 1:
        assert dom[1] > dom[0], "Scaling %s non-linearly requires an ordered domain: %s" % ( val, dom )
        if clamped:
            val			= clamp( val, (min(dom),max(dom)) )
        else:
            assert dom[0] <= val <= dom[1], "Scaling %s non-linearly requires value in domain: %s" % ( val, dom )
    else:
        assert dom[1] != dom[0], "Scaling %s requires a non-zero domain: %s" % ( val, dom )
    result                      = ( rng[0]
                                    + ( val    - dom[0] ) ** exponent
                                    * ( rng[1] - rng[0] )
                                    / ( dom[1] - dom[0] ) ** exponent )
    if clamped:
        result                  = clamp( result, (min(rng),max(rng)))
    return result


