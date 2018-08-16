#!/usr/bin/env python

"""
trading		-- Market simulation framework
  .market	-- A market in one security
  .exchange	-- Many simultaneous securities markets

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
import itertools
import logging

from .. import nan_first, nan_last, timer, non_value

trade_t				= collections.namedtuple( 
    'Trade', [ 
        'security', 
        'price',
        'currency',
        'time', 
        'amount', 
        'agent',
        ] )


prices_t			= collections.namedtuple(
    'Prices', [
        'bid', 
        'ask',
        'last',
        ] )


# The sell and buy order books are ordered in ascending 'price', and
# opposite 'time' order.  This is because the first entries of the
# sell book are used first, and the last entries of the buy book are
# used first, and we want to ensure that entries with equal prices are
# always consumed in ascending time-order (oldest entry first).

def sell_book_key( order ):
    return ( nan_first( order.price ), -order.time )


def buy_book_key( order ):
    return ( nan_last( order.price ), order.time )


class market( object ):
    """Implements a market for the named security.  Uses the "Security/Currency" naming convention or
    'currency' keyword; default is 'USD'.  Attempts to solve the set of trades available for
    completion at the given moment.  The market supports fixed-price (>= $0.00) and market-price
    (None or NaN) bids.

    buying = [
            ("wheat", 4.05,  2.,  500, <agent B>)   # @2. A buy  of 500 bu. at $4.00
            ]

    selling = [
            ("wheat", 4.10,  5., -100, <agent E>)   # @5. A sell of 100 bu. at $4.10
            ("wheat", 4.01,  3., -200, <agent D>)   # @3. A sell of 100 bu. at $4.01
            ("wheat", 4.00,  1., -250, <agent A>)   # @1. A sell of 250 bu. at $4.15
            ("wheat", 4.00,  2., -200, <agent C>)   # @2. A sell of 100 bu. at $4.00
            ]


    This market would use the 2 $4.00 sellers, in time order, then part of the 4.01 seller to
    satisfy the $4.05 buyer.

    When a buyer is matched by a seller, whoever put their order on the market first defines the
    trade price.  The lowest priced and oldest seller gets sold first:

        200/200 @ $4.00 from <agent C>
        250/250 @ $4.00 from <agent A>
         50/200 @ $4.01 from <agent D>

    Market-price orders are always processed before fixed-price orders.

    """
    def __init__( self, name, currency=None, now=None, **kwds ):
        super( market, self ).__init__( **kwds ) # Multiple Inheritance support
        # Get the base Security name from eg. 'Security/USD'
        self.name 		= name.split( '/', 1 )[0] if '/' in name else name
        self.currency		= currency or ( name.split( '/', 1 )[1] if '/' in name else 'USD' )
        self.now 		= now if now is not None else timer()
        self.buying 		= []
        self.selling 		= []
        self.last		= None
        self.transaction	= 0

    def format_book( self, width=40 ):
        """Print buy/sell order book w/ incl. depth chart."""
        open		= list( self.open() )
        biggest		= max( [ order.amount for order in open ] if open else [0] ) # python2 compatibility for python3 max( ..., default=0 )
        return '\n'.join(
            "{:<20s} {:4} {:9d} @ {}${:7.4f} {}".format( str( order.agent ),
                "buy" if order.amount > 0 else "sell", abs( order.amount ),
                order.currency, order.price, '*' * ( width * abs( order.amount ) // biggest if biggest else 0 ))
            for order in open )

    def __repr__( self ):
        """A market's representation is its full order book."""
        return self.format_book()

    def open( self, agent=None ):
        """Yield all currently open trades by this agent; buys will have a +'ve amount, sells a -'ve amount."""
        for order in itertools.chain( self.buying, self.selling ):
            if agent is None or order.agent is agent:
                yield order

    def close( self, agent ):
        """
        Remove all open trades by agent.
        """
        self.buying  = [ order for order in self.buying  if order.agent is not agent ]
        self.selling = [ order for order in self.selling if order.agent is not agent ]

    def buy( self, agent, amount, price=None, now=None, update=True ):
        if now is None:
            now 		= timer()
        self.enter( trade_t( self.name, price, self.currency, now, amount, agent ), update=update )

    def sell( self, agent, amount, price=None, now=None, update=True ):
        if now is None:
            now 		= timer()
        self.enter( trade_t( self.name, price, self.currency, now, -amount, agent ), update=update )

    def enter( self, order, update=True ):
        """
        Enter a trade order.  If a trade exists (either buy or sell) and update is True, we'll
        replace it (closing all existing trades).  A -'ve amount indicates a sell.

        Sorts orders by price, then time.  Market orders (buy/sell at any price) are sorted to
        appear "before" limit orders in their respective buying/selling order books.  All selling
        amounts remain -'ve!
        """
        if update:
            self.close( order.agent )
        if order.amount >= 0:
            self.buying.append( order )
            self.buying.sort( key=buy_book_key )
        else:
            self.selling.append( order )
            self.selling.sort( key=sell_book_key )

    def price( self ):
        """Return the current market price spread; bid, ask and last orders.  Ignores market-price
        (NaN/None) bids/asks.  Remember that the sell (ask) will have -'ve amounts!

        """
        bid			= None
        for order in reversed( self.buying ):
            if not non_value( order.price ):
                bid		= order
                break
        ask			= None
        for order in self.selling:
            if not non_value( order.price ):
                ask		= order
                break
        return prices_t( bid, ask, self.last )

    def execute_all( self, now=None, record=True ):
        """Execute all trades; If appropriate (record is True), we will also execute the order.agent.record( order )."""
        for order in self.execute( now=now ):
            if record:
                order.agent.record( order )

    def execute( self, now=None ):
        """Yield all possible trading transactions, adjust books.  Not thread-safe.  Performs
        market-price orders first, sorted by age.  Then, limit-price orders.  Remember that all
        amounts in the selling book are -'ve!
        
        The caller must record the trades with each trade's agent, as appropriate.  Normally, this
        would be something like (assuming 'mkt' is a market object, and the trade.agent supplied has
        a .record method which takes a trade):
        
            for order in mkt.execute():
                order.agent.record( order )
                # ... do other stuff with the order

        Largely ported from fms/fms/markets/continuousorderdriven.py, with handling for market-price
        and limit-price bid/ask added.

        Market sell (ask) prices are defined by the highest available buy (bid) price, and market
        buy (bid) prices are defined by the lowest available sell (ask) price.  If none are
        available, then the last order price is used.  It doesn't make sense to use bid prices if
        there are no price limit asks in the market, as this would allow a buyer to set his own
        price in a thin market.

        """
        if now is None:
            now			= timer()
        while ( self.buying and self.selling 
                and ( non_value( self.selling[0].price )			# either are market trades
                      or non_value( self.buying[-1].price )
                      or self.selling[0].price <= self.buying[-1].price )):	# or, limit prices overlap
            # Trades available, and lowest seller at or below greatest buyer (or one or both is None
            # or NaN, meaning market price).  If both buyer and seller are trading with market-price
            # orders, then the oldest order gets the advantage; market buyers pay highest available
            # seller limit, market sellers get lowest available buyer limit.  If no limit-price
            # orders exist, then no trade can be made on current prices_t(there is no market); use the
            # last order traded, if any.
            amount 		= min( self.buying[-1].amount, -self.selling[0].amount )

            if self.buying[-1].time < self.selling[0].time:
                # Buyer placed trade before seller; buyer gets better price (seller's ask limit price)
                price 		= self.selling[0].price
                if non_value( price ):
                    # Except if it's a market-price ask; then buyer pays his own bid limit price.
                    # If both are market price, the buyer will still get the priority; the best sell
                    # (ask) limit price.
                    price	= self.buying[-1].price
                    search	= self.selling
            else:
                # Seller placed trade at/after buyer; seller gets better price (buyer's bid limit price)
                price 		= self.buying[-1].price
                if non_value( price ):
                    # Except if it's a market-price bid; then seller pays his own ask price.  If both are market,
                    # then seller still gets priority; he'll get the best available buy (bid) limit price.
                    price	= self.selling[0].price
                    search	= reversed( self.buying )
            if non_value( price ):
                # Both are market-price orders; search order gives advantage to the oldest trade
                for order in search:
                    if not non_value( order.price ):
                        price	= order.price
                        break
            if non_value( price ):
                # Price is *still* None/NaN: No current market exists; use last trade
                if self.last is None:
                    break
                price		= self.last.price

            logging.info( "market %s at %7.2f" % ( self.name, price ))
            self.transaction   += 1
            buy = self.last 	= trade_t( self.name, price, self.currency, now,  amount, self.buying[-1].agent )
            sell		= trade_t( self.name, price, self.currency, now, -amount, self.selling[0].agent )

            if amount == self.buying[-1].amount:
                del self.buying[-1]
            else:
                self.buying[-1] = trade_t( self.buying[-1].security, self.buying[-1].price, self.buying[-1].currency,
                                           self.buying[-1].time, self.buying[-1].amount - amount,
                                           self.buying[-1].agent )
            if amount == -self.selling[0].amount:
                del self.selling[0]
            else:
                self.selling[0] = trade_t( self.selling[0].security, self.selling[0].price, self.selling[0].currency,
                                           self.selling[0].time, self.selling[0].amount + amount,
                                           self.selling[0].agent )
            yield buy
            yield sell


class exchange( object ):
    """Implements an exchange comprised of any number of securities markets, in the specified currency
    (deduce from "Exchange/Currency" naming convention, or default to 'USD').  New markes are
    created as required, when trades for a new security are entered.

    Much the same as a market, but most methods require a security name.  All markets must operate
    in the exchange's currency.

    """
    def __init__( self, name, currency=None, **kwds ):
        super( exchange, self ).__init__( **kwds )
        self.name	        = name
        self.currency		= currency or ( name.split('/',1)[1] if '/' in name else 'USD' )
        self.markets		= {}

    def __repr__( self ):
        return "\n".join( (repr( m ) for m in self.markets.values()))
        
    def open( self, agent ):
        """
        Yeilds all open orders for the agent, in all markets.
        """
        for mkt in self.markets.values():
            for ord in mkt.open( agent ):
                yield ord

    def buy( self, security, agent, amount, price, now=None, update=True ):
        if security not in self.markets:
            self.markets[security] = market( '/'.join(( security, self.currency )), currency=self.currency )
        self.markets[security].buy( agent, amount, price, now=now, update=update )

    def sell( self, security, agent, amount, price, now=None, update=True ):
        if security not in self.markets:
            self.markets[security] = market( '/'.join(( security, self.currency )), currency=self.currency )
        self.markets[security].buy( agent, amount, price, now=now, update=update )

    def enter( self, order, update=True ):
        if order.security not in self.markets:
            # Unless such a market already exists, disallow creating markets in other currencies
            assert order.currency == self.currency, \
                "Unable to enter orders for {} in {}$; only {}$ trades supported".format(
                    order.security, order.currency, self.currency )
            self.markets[order.security] = market( '/'.join(( order.security, order.currency )), currency=order.currency )
        self.markets[order.security].enter( order, update=update )

    def execute( self, now=None ):
        """
        Invoke .execute on each market in the exchange, and yield all the resultant trades.
        """
        for market in self.markets.values():
            for order in market.execute( now=now ):
                yield order

    def price( self, security ):
        if security in self.markets:
            return self.markets[security].price()
        return prices_t( None, None, None )
