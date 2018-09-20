#!/usr/bin/env python

"""
trading		-- Market trading simulation framework
  .agent        -- Minimal trading/exchange agent
  .actor	-- A basic actor in a stock market/exchange

"""

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

import collections
import logging
import math
import random

from .. import timer, scale, near

from .exchgs import * # market, ...
from .consts import * # day, ...

need_t				= collections.namedtuple( 
    'Need', [
        'priority', 	# Sort needs by priority
        'deadline', 	# Then by deadline (if None, will compute on first execution)
        'security',	# The security name
        'cycle', 	# The needs cyclical time
        'amount',	#   and the amount additionally required per cycle
        ] )


class agent( object ):
    """A basic trading agent.  Simply records its trades, keeps track of its net
    assets.  Has a preferred currency, which will be deduced on first trade if
    not specified.

    Default is no lower bound on quanta (always execute), and default start is a
    random fraction of the desired quanta (so agents with identical target
    quanta start at a random point during the first quanta).

    """
    def __init__( self, identity=None, assets=None, currency=None, now=None,
                  start=None, quanta=None, **kwds ):
        super( agent, self ).__init__( **kwds )
        self.identity		= identity or hex( id( self ))
        self.currency		= currency # May be None 'til deduced
        self.trades		= []
        self.assets		= {}   			# { 'something': 1000, 'another': 500 }
        self.balances		= {}   			# { 'USD': 1000, 'CAD': -1.23 }
        if assets:
            self.assets.update( assets )
        self.now		= None			# We have not executed previously
        self.dt			= 0
        if quanta is None:
            quanta		= 0
        if start is None:
            start		= quanta * random.random()
        self.start		= start
        self.quanta		= quanta

    def __str__( self ):
        return self.identity

    # 
    # sells_to/buys_from -- Used by market_selective to pair agreeable buyers/sellers
    # 
    def sells_to( self, another ):
        """This actor will sell to another actor."""
        return True

    def buys_from( self, another ):
        """This actor will buy from another actor"""
        return True
    
    @property
    def balance( self ):
        """self.balance -- access/adjust balance in preferred currency.  Will return
        0 'til self.currency set (or deduced in first trade).

        """
        return 0 if self.currency is None else self.balances.get( self.currency, 0 )
    @balance.setter
    def balance( self, value ):
        assert self.currency is not None, \
            "No agent currency defined/deduced; cannot change balance"
        if self.balance: # Currency balance not 0
            logging.warning( "{:<20s} balance adjusted from {}${:9.4f} to {:9.4f}".format(
                str( self ), self.currency, self.balance, value ))
        self.balances[self.currency] = value

    def run( self, exch, now=None ):
        """When start/quanta times are satisfied, compute the time quanta 'dt' since last execution, update
        current 'now', and return True, indicating that agent should execute its behavior.

        """
        if now is None:
            now			= timer()
        if now >= self.start:
            if self.now is None or now - self.now >= self.quanta:	# Ignores self.quanta on first execution
                self.now	= now
                self.dt		= now - ( self.start if self.now is None else self.now )
                return True
        return False

    def record( self, order, comment=None ):
        """
        Buy/sell the specified amount of security, at the given price.  If
        amount is -'ve, then this is a sale.  Selling short, buying on margin is
        allowed.
        """
        self.trades.append( order )
        if self.currency is None:
            self.currency	= order.currency
        logging.info( "%-20s %-5s %6d %10s @ %3s$%9.4f%s" % (
                self, "sells" if order.amount < 0 else "buys",
                abs( order.amount ), order.security, order.currency, order.price,
                ": " + comment if comment else ""))
        try:
            self.assets[order.security] += order.amount
        except KeyError:
            self.assets[order.security]  = order.amount
        try:
            self.balances[order.currency] += -order.amount * order.price
        except KeyError:
            self.balances[order.currency]  = -order.amount * order.price

    def volume( self, security=None, period=None, now=None ):
        """Compute the total buy/sell volumes over the period (ending 'now', or self.now)."""
        buy,sell		= 0,0
        now			= now if now is not None else self.now
        for order in reversed( self.trades ):
            if period and order.time < now - period:
                break
            if security and order.security == security:
                if order.amount < 0:
                    sell       -= order.amount
                else:
                    buy	       += order.amount
        return buy,sell


class actor( agent ):
    """Each actor produces and/or requires certain amounts of commodities
    (eg. food, goods, housing, labour) per time period.  The market should reach
    an equilibrium price for all of these, depending on their desirability
    (demand -- how many need it, and how much is needed) and rarity (supply --
    how many produce it, and how much is produced).

    Rather than directly simulating demand and supply to arrive at equilibrium
    prices, and controlling monetary systems to reach equilibrium PPM
    (Purchasing Power of Money), we create simple independent actors that
    actually try to sell the commodities they produce, to build a monetary
    balance, to fulfil their needs.  These commodities in supply and demand by
    independent actors create marketplace price and monetary purchasing power
    equilibrium.


    Different commodities have different levels of urgency, and will cause the
    actor to buy or sell at different prices.  For example, food must be sold at
    whatever the market will pay (or it will spoil), and must be bought at
    whatever the market prices it at (or the actor will starve).

    Labour will normally be sold at a certain price level, if the actor has
    excess money to purchase food/housing.  However, if the actor has no money
    for food/housing, the actor will sell labour at whatever the market will
    pay.  An actor with excess money may invest in education, to be able to
    deliver more desirable labour.

    Each time the actor is run, it may go into the market to buy/sell something;
    if other actors are in the market simultaneously with a corresponding
    sell/buy, then a trade may take place.

    Assumes that a trading.exchange is being used, since multiple securities
    will generally be in "needs". However, will work with a single
    trading.market.


    Default actor quanta is once per day (eg. somewhat like a person).  Default
    starting time is a random portion of the quanta.  It is assumed that the
    quanta will be adjusted to produce trading periods appropriate for the
    'needs' deadline/cycle being simulated; no attempt to adjust amounts by each
    quanta's specific dt is made.

    """
    def __init__( self, identity=None, target=None,
                  needs=None, balance=None, minimum=0., now=None,
                  quanta=None, **kwds ):
        if quanta is None:
            quanta		= day
        super( actor, self ).__init__( identity=identity, quanta=quanta, **kwds )

        # These are the target levels (if any) and assets holdings
        self.target		= {}			# { 'something': 350, ...}
        if target:
            self.target.update( target )
        self.needs		= needs			# [ need_t(...), ... ]
        if balance is not None:
            self.balance	= balance		# Credit balance (must specify currency to set)
        self.minimum		= minimum		#  and target minimum

    def record( self, order, comment=None ):
        super( actor, self ).record( order=order, comment=comment )

    def run( self, exch, now=None ):
        """Whenever we should run (according to start/interval), do whatever this
        actor does in this market, adjusting any open trades.

        A basic actor has assets, and a list of needs, each with a cycle and
        priority relative to others.  For example, he might sell labor to buy
        food to live.

        The base class does nothing but compute the self.dt since the last run,
        and update self.now, and arrange to acquire the upcoming needs.  As the
        deadline for a need approaches, the urgency to acquire the need
        increases.  Assets that are not needed will be sold, if necessary, to
        raise capital to supply the needs.

        The basic actor tries to acquire things earlier, at a price below the
        current market rate, if possible.

        """
        if not super( actor, self ).run( exch=exch, now=now ):
            return False
        self.acquire_needs( exch )
        self.cover_balance( exch )
        self.fix_portfolio( exch )
        return True

    def acquire_needs( self, exch ):
        """Iterate over needs by priority first, then deadline.  The 'target'
        amount is the base amount of the security we must have on hand; when a
        need expires, it is added to target.

        Issue market trade orders for those securities we have an upcoming need
        for, modulating our bid depending on the urgency of the need.

        A need with a deadline of None has its next cyclical deadline computed,
        from now.

        """
        needs			= [] # replacements self.needs
        for n in sorted( self.needs ):
            # First, see if this need's deadline has arrived; if so, record that the need was
            # expended (eg. food eaten, rent due, assets allocated...) by increasing the target for
            # that need, and reschedule the need.  A need w/ deadline == None will have its next
            # deadline computed on first execution.
            if n.deadline is not None and self.now < n.deadline:
                needs.append( n ) # Deadline not yet expired; re-schedule
            else:
                # Deadline None/expired; compute next deadline, add amount to target if expired
                if n.deadline is not None:
                    try:    self.target[n.security] += n.amount
                    except: self.target[n.security]  = n.amount
                    logging.info( "%s increased target for %s to %7.2f" % (
                        self, n.security, self.target[n.security] ))
                # And lets use/schedule an updated need_t w/ the newly computed deadline
                n		= need_t( n.priority,
                                          ( self.now if n.deadline is None else n.deadline ) + n.cycle, 
                                          n.security, n.cycle, n.amount )
                needs.append( n )

            # See if we are short of the amount required by the next deadline,
            # and try to acquire if so, with increasing urgency.
            wants		= self.target.get( n.security, 0 )
            holds		= self.assets.get( n.security, 0 )
            short		= n.amount + wants - holds
            if short <= 0:
                logging.info( "%s has full target %5d of %s: %5d/%5d" % (
                    self, n.amount, n.security, holds, wants ))
                exch.close( agent=self, security=n.security )
            else:
                # Hmm. We're short.  Adjust our offered purchase price based on
                # how much of the need's cycle remains.  If the deadline passes,
                # the difference will go -'ve, and the result will be > 1.  If
                # the deadline is a full cycle (or more) away, the difference
                # will go to 1. (or more), and the result will be < 0.  Convert
                # this into a price factor, ranging from ~10% under to ~5% over
                # current market asking price (greatest of bid, ask and latest).
                proportion	= 1. - ( n.deadline - self.now ) / n.cycle
                factor		= scale( proportion, (0., 1.), (0.90, 1.05))
                price_tuple	= exch.price( n.security ) # bid,ask,last
                price		= max( 0 if p is None else p.price for p in price_tuple )
                offer		= factor * price # If no market yet, offer could be $0 per unit.
                logging.info(
                    "%15s needs %d %s; bidding $%7.4f (%7.4f of $%7.4f price)" % (
                        self, short, n.security, offer,
                        factor, price if price else math.nan ))
                # Enter the trade for the required item, updating existing orders
                exch.enter( trade_t( security=n.security, price=offer, currency=exch.currency,
                                           time=self.now, amount=short,
                                           agent=self ),
                            update=True )
        # Finally, update our needs w/ the refreshed list computed (new deadlines, etc.)
        self.needs		= needs

    def cover_balance( self, exch ):
        """
        Total up everything we are bidding on, and see if we have enough.  Sell
        something, if not...

        This sums up all open buys and sells!  Basically, the more cash we have
        on hand, the less likely we are to sell assets, and the more we'll
        charge for them.
        """
        value			= 0.
        buying			= []
        for order in exch.open( self ):
            value	       += order.amount * order.price
            if order.amount > 0:
                buying.append( order.security )
        # eg.       0   - 100   < -75  --> $ 25 over limit
        #         500   - 200   < 400  --> $100 over limit
        if self.balance - value < self.minimum: # .minimum count be -math.inf
            # We're trying to buy more stuff than we can afford.  Sell to raise required capital
            #                           -75  -   0          + 100 == 25
            #                           400  - 500          + 200 == 100
            self.raise_capital( self.minimum - self.balance + value - self.minimum, exch, exclude=buying )

    def check_holdings( self, exch, exclude=None ):
        """Return the value of our holdings beyond our target levels on the given
        exchange, except those in the exclude list.

        Will not return holdings for which there is no current market (ie. no
        bid/ask/last price), because we may want to sell at market price.

        """
        excess 			= {}
        for sec,bal in self.assets.items():
            if exclude and sec in exclude:
                continue
            price_tuple		= exch.price( sec )
            price		= max( 0 if p is None else p.price for p in price_tuple )
            if near( price, 0 ):
                continue
            # There is bidding on this security.  Compute the value of
            # our excess amount of each security we hold.
            excess[sec]		= price * (self.assets[sec] - self.target.get( sec, 0 ))
        return excess

    def raise_capital( self, value, exch, exclude=None ):
        """
        Raise cash by selling the assets (not in the exclude list) with the
        greatest excess value, at market rates!

        For anything we are not currently short of, sell small amounts
        at high prices when not in need of cash, and larger amounts at
        lower prices when in need.
        """
        logging.warning(
            "%s wants to raise an additional $%7.2f; presently has $%7.2f" % (
                self, value, self.balance ))

        excess			= self.check_holdings( exch, exclude=exclude )

        for sec,val in sorted( excess.items(), key=lambda sv: -sv[1] ):
            # Sell some of the securities at current market rate (no price) we
            # have the most excess value of, 'til we have enough.  We'll have to
            # guess approximately how many units, because we don't know exactly
            # what the sale price will be.
            overage 		= (self.assets[sec] - self.target.get( sec, 0 ))
            amount 		= min( value // excess[sec] + 1, overage )
            estimate 		= amount * excess[sec] / overage   # units * $/unit
            print( "Sell %d of %d excess %s (worth ~%7.2f) for about %7.2f" % (
                amount, overage, sec, val, estimate  ))
            exch.enter( trade_t( security=sec, price=math.nan, currency=exch.currency,
                                       time=self.now, amount=-amount,
                                       agent=self ),
                        update=True )
            value 	       -= estimate
            if value <= 0:
                break

    def fix_portfolio( self, exch ):
        pass

class actor_inflation_pump( actor ):
    """Consults credit.inflation to decide buy/sell decisions, and tries to adjust
    holdings to shrink during inflation and grow during deflation.

    TODO: Must 
    """
    def __init__( self, identity=None, credit=None, **kwds ):
        super( actor_inflation_pump, self ).__init__( identity=identity, **kwds )
        self.credit		= credit
        
    def fix_portfolio( self, exch ):
        """
        The default behaviour is to buy low, and sell high.

        With a commodity backed currency system, when the price of the
        "reference" basket of commodities representing one unit of currency is
        priced above or below its defined value, this is a signal to either sell
        commodities to "too much" currency (ie. at inflated prices, when money
        is too cheap), or buy commodities for "too little" money (in times of
        deflation, where money is too expensive).

        So, we'll use the currency's Inflation index as a signal to either
        acquire or sell commodities into the market.  Since we can't really
        deduce which commodity is overpriced, we'll just sell the ones we have
        the most excess supplies of (and we aren't actively trying to acquire at
        the present time).  This makes sense, because we trust that the credit
        system is going to tighten or ease credit, in general, to quench
        inflation or deflation -- this will effect every commodity, not just the
        one that might be at the root of the in/deflation.
        """
        print( "Inflation == %7.2f" % ( self.credit.inflation ))

        holdings 		= self.check_holdings( exch )
        print( repr( holdings.items() ))
        for sec,val in sorted( holdings.items(), key=lambda sv: -sv[1], reverse=True ):
            print( "fix: %s: holds %s" % ( sec, val ))
            amount 		= 1
            if self.credit.inflation < 1.0:
                # Prices too low; buy at market!
                exch.enter( trade_t( security=sec, price=math.nan, currency=exch.currency,
                                           time=self.now, amount=amount,
                                           agent=self ))
            else:
                # Prices too high; sell into the market; just a bit 
                exch.enter( trade_t( security=sec, price=math.nan, currency=exch.currency,
                                           time=self.now, amount=-amount,
                                           agent=self ))


class producer( actor ):
    def __init__( self, security, cycle, output,
                  now=None, name=None, balance=0., assets=None, **kwds ):
        actor.__init__( self, now=now, name=name, balance=balance, assets=assets, **kwds )

        self.crop		= crop
        self.cycle		= cycle
        self.output		= output

        self.harvested		= self.now

    def run( self, exch, now=None ):
        """
        Produce a certain commodity on a certain cycle, with a certain range of
        output.  Performs all the tasks of a base actor, plus produces
        something, if the actor can meet his needs.

        If he has excess cash, he might expand production.
        """
        super( producer, self ).run( exch=exch, now=now )
        
        while self.now >= self.harvested + self.cycle:
            self.harvested     += self.cycle
            produced		= random.uniform( *self.output )
            self.record( trade_t( security=self.crop, price=0., currency=exch.currency,
                                amount=produced, now=self.harvested ),
                         "%s harvests %d %s" % ( 
                    self, produced, self.crop ))

