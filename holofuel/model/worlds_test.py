import time
import random

from . import near
from .trading import actor, market, engine, world, world_realtime, day, hour, second
from .reserve_lifo import reserve_issuing

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

'''
# -----
    
import numpy as np
from sklearn import linear_model
import collections
import math

# For more info about emacs + ob-ipython integration, see: https://github.com/gregsexton/ob-ipython

# Each commodity underlying the currency's price basket must be priced in standardized Units, of a
# specified quality, FOB some market.  The Holo Fuel basket's commodities are measured accross the
# Holo system, and the Median resource is used; this allows the basket to evolve over time, as
# Moore's law reduces the cost of the resource, the Median unit of that resource will likely
# increase (eg. CPU cores), counterbalancing the natural deflationary tendency of tech prices.

commodity_t             = collections.namedtuple(
    'Commodity', [
        'units',
        'quality',
        'notes',
    ] )
commodities             = {
    'holo':         commodity_t( "Host",    "",           "Inclusion in the Holo system" ),
    'cpu':          commodity_t( "Core",    "Median",     "A processing core" ),
    'ram':          commodity_t( "GB",      "Median",     "Processor memory" ),
    'net':          commodity_t( "TB",      "Median",     "Internet bandwidth" ),
    'data':         commodity_t( "TB",      "Median",     "Persistent storage (DHT/DB/file)" ),
}

# The basket represents the computational resource needs of a typical Holochain dApp's "interface"
# Zome.  A small dual-core Holo Host (ie. on a home Internet connection) could perhaps expect to run
# 200 Holo Fuel worth of these at full CPU utilization, 1TB of bandwidth; a quad-core / 8-thread
# perhaps 500 Holo Fuel worth at ~60% CPU (thread) utilization.

iron_count              =   5                   # Real iron req'd to host tradition small App
holo_fanout             =   5                   #   and additional Holo fan-out for DHT redundancy, etc.
hosts                   = iron_count * holo_fanout
basket_target           = 100.0                 # 1 Holo Fuel =~= 1 USD$; USD$100 of cloud hosting per minimal dApp, typ.
basket                  = {
    # Commodity     Amount, Proportion
    'holo':        hosts,           # Holo Host system fan-out and value premium
    'cpu':          1.00,           # Cores, avg. utilization across all iron
    'ram':          1.00,           # GB,    ''
    'net':          0.50,           # TB,    ''
    'data':         0.25,           # TB,    ''
}

# In the wild, prices will fluctuate according to supply/demand and money supply dynamics.  We'll
# start with some artificial weights; some commodities cost more than others, so the same "units"
# worth carry different weight in the currency basket.

weight                  = {
    'holo':        60/100,
    'cpu':          5/100,
    'ram':          5/100,
    'net':         20/100,
    'data':        10/100,
}

# -----

def rnd_std_dst( sigma, mean=0, minimum=None, maximum=None ):
    """Random values with mean, in a standard distribution w/ sigma, clipped to given minimum/maximum."""
    val             = sigma * np.random.randn() + mean
    return val if minimum is None and maximum is None else np.clip( val, a_min=minimum, a_max=maximum )

# To simulate initial pricing, lets start with an estimate of proportion of basket value represented
# by each amount of the basket's commodities.  Prices of each of these commodities is free to float
# in a real market, but we'll start with some pre-determined "weights"; indicating that the amount
# of the specified commodity holds a greater or lesser proportion of the basket's value.
# Regardless, 100 Holo Fuel is guaranteed to buy the entire basket.

prices                  = {}
for k in basket:
    price_mean          = basket_target * weight[k] / basket[k] # target price: 1 Holo Fuel == 1 basket / basket_target
    price_sigma         = price_mean / 10 #  difference allowed; about +/- 10% of target
    prices[k]           = rnd_std_dst( price_sigma, price_mean )

# -----

basket_price            = sum( basket[k] * prices[k] for k in basket )

# -----

amounts_mean            = 1.00
amounts_sigma           = 0.5
error_sigma             = 0.10 # +/- 10% variance in bids (error) vs. price
trades                  = []
number                  = 10000
for _ in range( number ):
    # Each dApp consumes a random standard distribution of the target amount of each commodity
    amounts             = { k: 1 if k == 'holo'
                               else basket[k] * rnd_std_dst( amounts_sigma, amounts_mean, minimum=0 ) / basket['holo']
                            for k in basket }
    price               = sum( amounts[k] * prices[k] for k in amounts )
    error               = price * rnd_std_dst( error_sigma )
    bid                 = price + error
    trades.append( dict( bid = bid, price = price, error = error, amounts = amounts ))

# -----

items                   = [ [ t['amounts'][k] for k in basket ] for t in trades ]
bids                    = [ t['bid'] for t in trades ]

regression              = linear_model.LinearRegression( fit_intercept=False, normalize=False )
regression.fit( items, bids )
select                  = { k: [ int( k == k2 ) for k2 in basket ] for k in basket }
predict                 = { k: regression.predict( select[k] )[0] for k in basket } # deref numpy.array

# -----

basket_predict          = sum( basket[k] * predict[k]  for k in basket )
basket_predict_err_pct	= ( basket_predict - basket_price ) * 100 / basket_price
[ [ "Holo Fuel Price Recovered", "vs. Actual", "Error" ], None,
  [ "$%5.2f / %.2f" % ( basket_predict, basket_target ),
    "%5.2f" % ( basket_price ),
    "%+5.3f%%" % (( basket_predict - basket_price ) * 100 / basket_price ),
    ]]

def test_price_recovery():
    assert -5.0 < basket_predict_err_pct < 5.0

# -----

class credit_static( object ):
    """Simplest, static K-value, unchanging basket and prices."""
    def __init__( self, K, basket, prices ):
        self.K          = K
        self.basket     = basket
        self.prices     = prices

    def value( self, prices=None, basket=None ):
        """Compute the value of a basket at some prices (default: self.basket/prices)"""
        if prices is None: prices = self.prices
        if basket is None: basket = self.basket
        return sum( prices[k] * basket[k] for k in basket )

# Adjust this so that our process value 'basket_value' achieves setpoint 'basket_target'
# Use the global basket, prices defined above.
credit                  = credit_static( K=0.5, basket=basket, prices=prices )

#print( "Global basket: %r, prices: %r" % ( basket, prices ))
#print( "credit.basket: %r, prices: %r" % ( credit.basket, credit.prices ))

duration_hour           = 60 * 60
duration_day            = 24 * duration_hour
duration_month          = 365.25 * duration_day / 12 # 2,629,800s.

used_mean               = 1.0                   # Hourly usage is
used_sigma              = used_mean * 10/100    # +/-10%
reqs_mean               = 2.0                   # Avg. Host is 2x minimal
reqs_sigma              = reqs_mean * 50/100    # +/-50%
reqs_min                = 1/10                  #   but at least this much of minimal dApp

class dApp( object ):
    def __init__( self, duration=duration_month ): # 1 mo., in seconds
        """Select a random basket of computational requirements, some multiple of the minimal dApp
        represented by the Holo Fuel basket (min. 10% of basket, mean 2 x basket), for the specified
        duration.

        The self.wealth is computed to supply a credit line sufficient to fund exactly 1 month of
        dApp Hosting. This is a *simplistic* simulation of credit, but adequate to observe the
        reaction of dApp owners and Hosts to adjusting credit lines.  In the real Holo system, a
        much more complex system of establishing Host/dApp "wealth" and subsequent credit lines, and
        dynamically adjusting automatic Host and dApp pricing will be employed.  The net effect will
        be similar, but the reactions will take longer to emerge than this simulation's effects.

        """
        self.duration   = duration
        self.requires   = { k: rnd_std_dst( sigma=reqs_sigma, mean=reqs_mean, minimum=reqs_min ) \
                                 * credit.basket[k] * duration / duration_month
                             for k in credit.basket }
        # Finally, compute the wealth required to fund this at current credit factor K; work back
        # from the desired credit budget, to the amount of wealth that would produce that at "K".
        # Of course wealth is a "stock", a budget funds a "flow", and we're conflating here. But,
        # this could represent a model where the next round of Hosting's estimated cost is budgetted
        # such that we always have at least one month of available credit to sustain it.
        self.wealth     = credit.value( basket=self.requires ) / credit.K

    def __repr__( self ):
        return "<dApp using %8.2f Holo Fuel / %5.2f mo.: %s" % (
                   credit.value( basket=self.requires ), self.duration/duration_month,
                   ", ".join( "%6.2f %s %s" % ( self.requires[k] * self.duration/duration_month,
                                               commodities[k].units, k ) for k in credit.basket ))

    def available( self, dt=None ):
        """Credit available for dt seconds (1 hr., default) of Hosting."""
        return self.wealth * credit.K * ( dt or duration_hour ) / self.duration

    def used( self, dt=None, mean=1.0, sigma=.1 ):
        """Resources used over period dt (+/- 10% default, but at least 0)"""
        return { k: self.requires[k] * rnd_std_dst( sigma=sigma, mean=mean, minimum=0 ) * dt / self.duration
                 for k in self.requires }

class Host( object ):
    def __init__( self, dApp ):
        self.dApp       = dApp

    def receipt( self, dt=None ):
        """Generate receipt for dt seconds worth of hosting our dApp.  Hosting costs more/less as prices
        fluctuate, and dApp owners can spend more/less depending on how much credit they have
        available.  This spending reduction could be acheived, for example, by selecting a lower
        pricing teir (thus worse performance).
        """
        avail           = self.dApp.available( dt=dt )                # Credit available for this period
        used            = self.dApp.used( dt=dt, mean=used_mean, sigma=used_sigma ) # Hhosting resources used
        value           = credit.value( basket=used )                 # total value of dApp Hosting resources used

        # We have the value of the hosting the dApp used, at present currency.prices.  The Host
        # wants to be paid 'value', but the dApp owner only has 'avail' to pay. When money is
        # plentiful/tight, dApp owners could {up,down}grade their service teir and pay more or less.
        # So, we'll split the difference.  This illustrates the effects of both cost variations and
        # credit availability variations in the ultimate cost of Hosting, and hence in the recovered
        # price information used to adjust credit.K.

        result          = ( avail + value ) / 2,used
        #print( "avail: {}, value: {}, K: {!r},  result: {!r}".format( avail, value, credit.K, result ))
        return result

hosts_count             = 60 * 60 # ~1 Hosting receipt per second
hosts                   = [ Host( dApp() ) for _ in range( hosts_count ) ]
hours_count             = 24

class credit_sine( credit_static ):
    """Compute a sine scale as the basis for simulating various credit system variances."""
    def __init__( self, amp, step, **kwds ):
        self.sine_amp   = amp
        self.sine_theta = 0
        self.sine_step  = step
        self.K_base     = 0
        super( credit_sine, self ).__init__( **kwds )

    def advance( self ):
        self.sine_theta += self.sine_step

    def reset( self ):
        """Restore credit system initial conditions."""
        self.sine_theta = 0

    def scale( self ):
        return 1 + self.sine_amp * math.sin( self.sine_theta )

class credit_sine_K( credit_sine ):
    """Adjusts credit.K on a sine wave."""
    @property
    def K( self ):
        return self.K_base * self.scale()
    @K.setter
    def K( self, value ):
        """Assumes K_base is created when K is set in base-class constructor"""
        self.K_base     = value

class credit_sine_prices( credit_sine ):
    """Adjusts credit.prices on a sine wave."""
    @property
    def prices( self ):
        return { k: self.prices_base[k] * self.scale() for k in self.prices_base }
    @prices.setter
    def prices( self, value ):
        self.prices_base = prices

# Create receipts with a credit.K or .prices fluctuating +/- .5%,  1 cycle per 6 hours
#credit.advance         = lambda: None # if using credit_static...
#credit.sine_amp        = 0
credit                  = credit_sine_prices(
                              K = 0.5,
                            amp = .5/100,
                           step = 2 * math.pi / hosts_count / 6,
                         prices = prices,
                         basket = basket ) # Start w/ the global basket
receipts                = []
for _ in range( hours_count ):
    for h in hosts:
        receipts.append( h.receipt( dt=duration_hour ))
        credit.advance()
credit.reset()

items                   = [ [ rcpt[k] for k in credit.basket ] for cost,rcpt in receipts ]
costs                   = [ cost for cost,rcpt in receipts ]

regression              = linear_model.LinearRegression( fit_intercept=False, normalize=False )
regression.fit( items, costs )
select                  = { k: [ int( k == k2 ) for k2 in credit.basket ] for k in credit.basket }
predict                 = { k: regression.predict( select[k] )[0] for k in credit.basket }

actual_value            = credit.value()
predict_value           = credit.value( prices=predict )

# -----

import json
import traceback
import random

# Make random changes to the pricing of individual computational resources, to simulate
# the independent movement of commodity prices.
adva_mean               = 1.0                   # Parity
adva_sigma              = 1/100                 #  +/- 2% x standard distribution
adva_min                = 98/100                # Trending downward (ie. Moore's law)
adva_max                =102/100                # b/c 102% doesn't fully recover from 98%

class credit_sine_prices_pid_K( credit_sine_prices ):
    """Adjusts credit.K via PID, in response to prices varying randomly, and to a sine wave."""
    def __init__( self, Kpid=None, price_target=None, price_curr=None, now=None, **kwds ):
        """A current price_target (default: 100.0 ) and price_feedback (default: price_target)
        is used to initialize a PID loop.
        """
        super( credit_sine_prices_pid_K, self ).__init__( **kwds )
        self.now        = now or 0 # hours?
        # Default: 100.0 Holo Fuel / basket, defined above
        self.price_target = price_target if price_target is not None else basket_target
        # Default to 0 inflation if no price_curr given
        self.price_curr = price_curr if price_curr is not None else self.price_target
        self.price_curr_trend = [(self.now, self.price_curr)]
        self.inflation  = self.price_curr / self.price_target
        self.inflation_trend = [(self.now, self.inflation)]
        # Bumpless start at setpoint 1.0, present inflation, and output of current K
        # TODO: compute Kpid fr. desired correction factors vs. avg target dt.
        self.K_control  = controller(
                           Kpid = Kpid or ( .1, .1, .001 ),
                       setpoint = 1.0,                  # Target is no {in,de}flation!
                        process = self.inflation,
                         output = self.K,
                            now = self.now )
        self.K_trend    = [(self.now, self.K)]
        self.PID_trend  = [(self.now, (self.K_control.P, self.K_control.I, self.K_control.D))]
        self.price_trend= [(self.now, self.value())]
        self.feedback_trend =[]

    def bumpless( self, price_curr, now ):
        """When taking control of the currency after a period of inactivity, reset the PID
        parameters to ensure a "bumpless" transfer starting from current computed inflation/K.
        """
        self.now        = now
        self.price_curr = price_curr
        self.inflation  = price_curr / self.price_target
        self.K_control.bumpless(
                       setpoint = 1.0,
                        process = self.inflation,
                         output = self.K,
                            now = now )

    def price_feedback( self, price, now, bumpless=False ):
        """Supply a computed basket price at time 'now', and compute K via PID. If we are
        assuming control (eg. after a period of inactivity), reset PID control to bumplessly
        proceed from present state; otherwise, compute K from last time quanta's computed state.
        """
        self.now        = now
        self.price_curr = price
        self.price_curr_trend += [(self.now, self.price_curr)]
        self.inflation  = self.price_curr / self.price_target
        self.inflation_trend += [(self.now, self.inflation)]
        if bumpless:
            self.bumpless( price_curr=self.price_curr, now=now )
        else:
            self.K      = self.K_control.loop(
                        process = self.inflation,
                            now = self.now )
        self.K_trend   += [(self.now, self.K)]
        self.PID_trend += [(self.now, (self.K_control.P, self.K_control.I, self.K_control.D))]
        self.price_trend += [(self.now, self.value())]

    def receipt_feedback( self, receipts, now, bumpless=False ):
        """Extract price_feedback from a sequence of receipts via linear regression.  Assumes that the
        'holo' component is a "baseline" (is assigned all static, non-varying base cost, not
        attributable to varying usage of the other computational resources); it is always a simple
        function of how much wall-clock time the Receipt represents, as a fraction of the 1 'holo'
        Host-month included in the basket.  The remaining values represent how many units (eg. GB
        'ram', TB 'storage', fraction of a 'cpu' Core's time consumed) of each computational
        resource were used by the dApp during the period of the Receipt.
        """
        items           = [ [ r[k] for k in credit.basket ] for c,r in receipts ]
        costs           = [ c                               for c,r in receipts ]
        try:
            regression.fit( items, costs )
            select      = { k: [ int( k == k2 ) for k2 in self.basket ] for k in self.basket }
            predict     = { k: regression.predict( select[k] )[0] for k in self.basket }
            self.price_feedback( self.value( prices=predict ), now=now, bumpless=bumpless )
            self.feedback_trend += [(self.now, { k: self.basket[k] * predict[k]
                                                for k in self.basket })]
        except Exception as exc:
            print( "Regression failed: %s" % ( exc ))
            traceback.print_stack( file=sys.stdout )

    def advance( self ):
        """About once per integral time period (eg. hour), randomly purturb the pricing of one
        commodity in the basket.  We'll manipulate the underlying self.prices_base (which is being
        modulated systematically to produce the base commodity prices).
        """
        super( credit_sine_prices_pid_K, self ).advance()
        if int( getattr( self, 'adv_h', 0 )) != int( self.now ):
            self.adv_h  = int( self.now )
            k           = random.choice( list( prices.keys() ))
            adj         = rnd_std_dst( sigma=adva_sigma, mean=adva_mean,
                                      minimum=adva_min, maximum=adva_max )
            self.prices_base[k] *= adj

# Create the credit system targetting neutral {in,de}flation of 1.0. The underlying basket and prices
# are globals, created above, randomly starting at some offset from neutral inflation.  We are varying
# the amount of credit available, essentially forcing dApp owners to opt for lower or higher tranches
# of service to stay within their available credit.

credit                  = credit_sine_prices_pid_K(
                              K = 0.5,
                            amp = .5/100,
                           step = 2 * math.pi / hosts_count / 6,
                         prices = prices,
                         basket = basket,               # Start w/ the global prices, basket
                   price_target = basket_target,
                     price_curr = credit.value() )      # Est. initial price => inflation

# Run a simulation out over a couple of days.  This will simulate a base Price of a Desired level of
# service (say, a certain Tranche of Hosts w/ a certain level of performance), but will simulate a
# withdrawal of credit from the system (eg. available to the dApp owners), which forces them to
# elect a lower service level (at lower prices), or gain access to a higher level of service (with
# greater available credit) and pay more.  We will also from time to time randomly adjust the
# pricing of one component of the basket relative to all others, to illustrate the effect of
# changing the supply/demand of just one portion of the computational commodities underlying Holo
# Fuel), and observe how the system responds.

hours_count             = 24 * 2
receipts                = []
for x in range( hours_count ):
    for h in hosts:
        receipts.append( h.receipt( dt=duration_hour ))
        if len( receipts ) >= hosts_count \
           and  int(  len( receipts )       * x_divs / hosts_count ) \
             != int(( len( receipts ) - 1 ) * x_divs / hosts_count ):
            # After 1st hr; About to compute next hours / x_divs' receipt! Compute and update
            # prices using last hour's receipts.  The now time (in fractional hours) is length
            hrs         = len( receipts ) / hosts_count
            #print( "After %5.2fh (%02d:%02d): %d receipts, %d K_trend (%f - %f)" % (
            #    hrs, int( hrs ), int( hrs * 60 ) % 60, len( receipts ),
            #    len( credit.K_trend ), credit.K_trend[0][0], credit.K_trend[-1][0] ))
            credit.receipt_feedback( receipts[-hosts_count:], now=hrs,
                                     bumpless=( len( receipts ) == hosts_count ))
        credit.advance() # adjust market prices algorithmically
credit.reset()
#print("K trend: %f - %f" % ( credit.K_trend[0][0], credit.K_trend[-1][0] ))

'''


def test_value_stability():
    """A reserve that adjusts supply to achieve value stability.  The reserve adjusts the amount of Holo
    fuel available.

    Hosts collect (are paid) Holo fuel from dApps, and Retire (sell) it.  Hosts sell their Holo fuel
    into the market, lowering their limit prices 'til it sells, driving prices down.

    Owners of dApp's are Issued (buy) Holo fuel; they'll adjust increase/decrease their price
    depending on how far away from making their payments they are, driving prices up.


    We'll plug in the various Reserve implementation to see how they perform.

    """
    class host( actor ):
        pass
    class dApp( actor ):
        pass
    duration		= 1 * day
    hosts		= 1000
    dApps		= 10
    res			= reserve_issuing( "Holofuel/USD", supply_period=hour, supply_available=1000000 )
    agents		= [ host() for _ in range( hosts ) ] + [ dApp() for _ in range( dApps ) ]
    wld			= world( duration=duration )
    eng			= engine( world=wld, exch=res, agents=agents )
