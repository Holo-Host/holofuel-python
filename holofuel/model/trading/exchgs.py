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
import math

from .. import nan_first, nan_last, timer, non_value

class trade_t( collections.namedtuple( 
    'Trade', [ 
        'security', 
        'price',
        'currency',
        'time', 
        'amount', 
        'agent',
    ] )):
    __slots__			= ()
    def __str__( self ):
        return "{:<20s} {:4} {:9.4f} @ {}${}".format(
            str( self.agent ), "buy" if self.amount > 0 else "sell",
            abs( self.amount ), self.currency,
            " <market>" if non_value( self.price ) else "{:9.4f}".format( self.price ))

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

    Only allows trades to execute between agreeable agents.  When used with custom agents with
    sells_to/buys_from methods that reject or accept other agents based on some criteria, will only
    allow trades to occur between mutually compatible agents.  By default, this only prevents
    self-trading.

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
        open		= list( self.orders() )
        biggest		= max( [ abs( order.amount ) for order in open ] if open else [0] ) # python2 compatibility for python3 max( ..., default=0 )
        return '\n'.join(
            "{} {}".format( str( order ), '*' * int( width * abs( order.amount ) // biggest if biggest else 0 ))
            for order in open )

    def __str__( self ):
        """A market's string representation is its full order book."""
        return self.name + '/' + self.currency

    def __repr__( self ):
        return '<market( ' + str( self ) + ' )>'

    def orders( self, agent=None ):
        """Yield all currently open trades by this agent; buys will have a +'ve amount, sells a -'ve amount."""
        for order in itertools.chain( self.buying, self.selling ):
            if agent is None or order.agent is agent:
                yield order

    def close( self, agent, security=None ):
        """
        Remove all open trades by agent.
        """
        if security is not None:
            assert security == self.name, \
                "Security {!r} incorrect for market {!r}".format( security, self )
        self.buying  = [ order for order in self.buying  if order.agent is not agent ]
        self.selling = [ order for order in self.selling if order.agent is not agent ]

    def buy( self, agent, amount, price=None, now=None, update=None ):
        if now is None:
            now 		= timer()
        self.enter( trade_t( self.name, price, self.currency, now, amount, agent ), update=update )

    def sell( self, agent, amount, price=None, now=None, update=None ):
        if now is None:
            now 		= timer()
        self.enter( trade_t( self.name, price, self.currency, now, -amount, agent ), update=update )

    def agents_compatible( self, buyer, seller ):
        if hasattr( buyer, 'sells_to' ) and hasattr( seller, 'buys_from' ):
            return seller.sells_to( buyer ) and buyer.buys_from( seller )
        return True # Unknown agent type; we don't know how to determine compatibility

    # 
    # buy/sell_matches -- See if we're going to enter a trade that does something degenerate
    # 
    #     These methods can be overridden to check for other stuff.  If the buys_from and sells_to
    # prevent self-trading, then these should never fire.  Otherwise, they'll prevent you from
    # entering a trade that'll be satisfied by the same agent.
    # 
    def buy_matches( self, order ):
        for s in self.selling:
            if ( self.agents_compatible( buyer=order.agent, seller=s.agent )
                 and s.agent == order.agent
                 and ( non_value( s.price ) or non_value( order.price ) or s.price <= order.price )):
                return s
            if not non_value( s.price ) and not non_value( order.price ) and s.price > order.price:
                break
        return None

    def sell_matches( self, order ):
        for b in self.buying:
            if ( self.agents_compatible( seller=order.agent, buyer=b.agent )
                 and b.agent == order.agent
                 and ( non_value( b.price ) or non_value( order.price ) or b.price >= order.price )):
                return b
            if not non_value( b.price ) and not non_value( order.price ) and b.price < order.price:
                break
        return None

    def enter( self, order, update=None ):
        """Enter a trade order.  If a trade exists (either buy or sell) and update is True, we'll
        replace it (closing all existing trades).  A -'ve amount indicates a sell.

        Sorts orders by price, then time.  Market orders (buy/sell at any price) are sorted to
        appear "before" limit orders in their respective buying/selling order books.  All selling
        amounts remain -'ve!
        
        Replace any existing trades in security iff 'update'; ensure we don't inadvertently enter a
        self-trade (ie. one that will be matched by one of our existing trades)

        """
        if update:
            self.close( order.agent, security=order.security )
        if order.amount >= 0:
 	    # entering a buy order
            if not update:
                s		= self.buy_matches( order )
                if s:
                    raise RuntimeError(
                        "Attempt to enter a buy: {:s} matching an existing sell order: {:s}".format(
                        order, s ))
            self.buying.append( order )
            self.buying.sort( key=buy_book_key )
        else:
	    # entering a sell order
            if not update:
                b		= self.sell_matches( order )
                if b:
                    raise RuntimeError(
                        "Attempt to enter a sell: {:s} matching an existing buy order: {:s}".format(
                            order, b ))
            self.selling.append( order )
            self.selling.sort( key=sell_book_key )

    def price( self, security=None ):
        """Return the current market price spread; bid, ask and last orders.  Ignores market-price
        (NaN/None) bids/asks.  Remember that the sell (ask) will have -'ve amounts!  We'll accept a
        security (for compabitility w/ exchange.price( <security> ).

        """
        if security is not None:
            assert security == self.name, \
                "Security {!r} incorrect for market {!r}".format( security, self )
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

    def execute_all( self, now=None, record=True, **kwds ):
        """Execute all trade orders; If appropriate (record is True), we will also record the trade with
        each agent.

        Returns the trades executed.

        """
        trades			= []
        for trade in self.execute( now=now, **kwds ):
            if record:
                for order in trade:
                    order.agent.record( order )
            trades.append( trade )
        return trades

    def trade_possible( self, bid=-1, ask=0 ):
        return ( bid < 0 and ask >= 0						# bid/ask indices are valid
                and bid >= -len( self.buying )
                and ask <   len( self.selling )
                and ( non_value( self.selling[ask].price )			# either are market trades
                      or non_value( self.buying[bid].price )
                      or self.selling[ask].price <= self.buying[bid].price ))   # or prices are overlapping

    def execute( self, now=None, bid=-1, ask=0 ):
        """Step bid down and ask upward, 'til we exhaust the order book, or run out of willing participants.
        This is useful in cases where not all market participants can/will deal with each-other.

        Each time we execute one trade, break out and re-walk the order book, since the book may
        have been changed.

            order book:                       holdings:
            buy    # $    | sell   # $        who #   @ $
            ---- --- ---- | ---- --- ----     --- ----  ----
            A    175 1.44 | R    100 1.38     R   100 @ 1.38  100 @ 1.39  100 @ 1.40
            B(R) 200 1.43 | C    200 1.43     A   0
                                              B   0
                                              C   200 @ 1.43

        For example, if agents A and C are not eligible to deal with R, but B is, then when this
        order book is executed, A will buy 75 at 1.43 (no eligible to buy from R):

            order book:                       holdings:                                
            buy    # $    | sell   # $        who #   @ $                              
            ---- --- ---- | ---- --- ----     --- ----  ----                           
            A    75  1.44 | R    100 1.38     R   100 @ 1.38  100 @ 1.39  100 @ 1.40
            B(R) 200 1.43 | C    125 1.43     A    75 @ 1.43                                   
                                              B   0                                    
                                              C   200 @ 1.43

        Then, B will buy 100 from R at 1.38 and 100 from C at 1.43

            order book:                       holdings:                                
            buy    # $    | sell   # $        who #   @ $                              
            ---- --- ---- | ---- --- ----     --- ----  ----                           
            B(R) 200 1.43 | R    100 1.38     R   100 @ 1.38  100 @ 1.39  100 @ 1.40
                          | C    125 1.43     A    75 @ 1.43                                   
                                              B   100 @ 1.38  100 @ 1.43
                                              C   200 @ 1.43

        After each trade, the order book has changed (the user of this generator may be modifying
        the participants in the order book, in addition to the changes in the existing orders due to
        each buy/sell processed!)

        Therefore, after each order, collect the bidder/asker agents that could possibly trade, and
        evaluate any new participants against all other potential traders.  If any buyers or sellers
        are trading at "market" (no limit price), then all of the compatible counterparties are
        potentially in play!

        """
        transaction			= self.transaction
        done				= False
        while ( not done and self.trade_possible( bid=bid, ask=ask )): 	# while there are still orders potentially possible
            done			= True
            # Seek down the order book looking for the first compatible trading partners
            bidnow,asknow		= bid,ask
            while self.trade_possible( bid=bidnow, ask=asknow ) \
                  and not self.agents_compatible( buyer=self.buying[bidnow].agent, seller=self.selling[asknow].agent ):
                bidnow,asknow		= (bidnow-1,asknow) if bidnow + asknow == 0 else (bidnow,asknow+1)
            # Could be no trades possible between consenting parties...  Yield one order, then
            # re-check, because the order book may be altered between each order!  If no trades
            # executed, outer loop will cease.
            for trade in self.execute_possible( now, bid=bidnow, ask=asknow ):
                yield trade
                done			= False
                break


    def execute_possible( self, now=None, bid=-1, ask=0 ):
        """Yield all possible (buyer,seller) trading transactions, at the given bid/ask indices, and
        adjust books.  Not thread-safe.  Performs market-price orders first, sorted by age.  Then,
        limit-price orders.  Remember that all amounts in the selling book are -'ve!
        
        The caller must record the trades with each trade's agent, as appropriate.  Normally, this
        would be something like (assuming 'mkt' is a market object, and the trade.agent supplied has
        a .record method which takes a trade):
        
            for trade in mkt.execute():
                for order in trade:
                    order.agent.record( order )
                # ... do other stuff with trade

        Largely ported from fms/fms/markets/continuousorderdriven.py, with handling for market-price
        and limit-price bid/ask added.

        Market sell (ask) prices are defined by the highest available buy (bid) price, and market
        buy (bid) prices are defined by the lowest available sell (ask) price.  If none are
        available, then the last order price is used.  It doesn't make sense to use bid prices if
        there are no price limit asks in the market, as this would allow a buyer to set his own
        price in a thin market.

        A derived class may apply other means to determine the best appropriate bid/ask index to
        execute trades from (eg. the highest (latest in list) compatible buyer, and lowest (earliest
        in list) compatible seller.

        """
        if now is None:
            now			= timer()
        while self.trade_possible( bid=bid, ask=ask ):
            # Trades available, and lowest seller at or below greatest buyer (or one or both is None
            # or NaN, meaning market price).  If both buyer and seller are trading with market-price
            # orders, then the oldest order gets the advantage; market buyers pay highest available
            # seller limit, market sellers get lowest available buyer limit.  If no limit-price
            # orders exist, then no trade can be made on current prices_t(there is no market); use the
            # last order traded, if any.
            amount 		= min( self.buying[bid].amount, -self.selling[ask].amount )

            # Who gets the "spread" between bid/ask limit orders?  The earlier trade (who took the
            # greater risk).
            if self.buying[bid].time < self.selling[ask].time:
                # Buyer placed trade before seller; buyer gets better price (seller's ask limit price)
                price 		= self.selling[ask].price
                if non_value( price ):
                    # Except if it's a market-price ask; then buyer pays his own bid limit price.
                    # If both are market price, the buyer will still get the priority; the best
                    # (lowest) sell (ask) limit price.
                    price	= self.buying[bid].price
                    search	= self.selling # in ascending price order, NaN/None first
            else:
                # Seller placed trade at/after buyer; seller gets better price (buyer's bid limit price)
                price 		= self.buying[bid].price
                if non_value( price ):
                    # Except if it's a market-price bid; then seller gets his own ask price.  If
                    # both are market, then seller still gets priority; he'll get the best available
                    # buy (bid) limit price.
                    price	= self.selling[ask].price
                    search	= reversed( self.buying ) # in descending price order, NaN/None first
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

            self.transaction   += 1
            buy = self.last 	= trade_t( self.name, price, self.currency, now,  amount, self.buying[bid].agent )
            sell		= trade_t( self.name, price, self.currency, now, -amount, self.selling[ask].agent )

            if amount == self.buying[bid].amount:
                del self.buying[bid]
            else:
                self.buying[bid] = trade_t( self.buying[bid].security, self.buying[bid].price, self.buying[bid].currency,
                                           self.buying[bid].time, self.buying[bid].amount - amount,
                                           self.buying[bid].agent )
            if amount == -self.selling[ask].amount:
                del self.selling[ask]
            else:
                self.selling[ask] = trade_t( self.selling[ask].security, self.selling[ask].price, self.selling[ask].currency,
                                           self.selling[ask].time, self.selling[ask].amount + amount,
                                           self.selling[ask].agent )
            yield buy,sell


class exchange( object ):
    """Implements an exchange comprised of any number of securities markets, in the specified currency
    (deduce from "Exchange/Currency" naming convention, or default to 'USD').  New markes are
    created as required, when trades for a new security are entered.

    Much the same as a market, but most methods require a security name.  All markets must operate
    in the exchange's currency.

    """
    def __init__( self, name, currency=None, market_class=None, **kwds ):
        super( exchange, self ).__init__( **kwds )
        self.name	        = name
        self.currency		= currency or ( name.split('/',1)[1] if '/' in name else 'USD' )
        self.markets		= {}
        self.market_class	= market_class or market

    def __repr__( self ):
        return "\n".join( (repr( m ) for m in self.markets.values()))
        
    def close( self, agent, security=None ):
        """Close all open orders for the agent, in all markets (or in market matching security)."""
        for sec,mkt in self.markets.items():
            if security is not None and sec != security:
                continue
            mkt.close( agent )

    def orders( self, agent, security=None ):
        """
        Yields all open orders for the agent, in all markets (or in market matching security).
        """
        for sec,mkt in self.markets.items():
            if security is not None and sec != security:
                continue
            for ord in mkt.orders( agent ):
                yield ord

    def buy( self, security, agent, amount, price, now=None, update=True ):
        if security not in self.markets:
            self.markets[security] = self.market_class( '/'.join(( security, self.currency )), currency=self.currency )
        self.markets[security].buy( agent, amount, price, now=now, update=update )

    def sell( self, security, agent, amount, price, now=None, update=True ):
        if security not in self.markets:
            self.markets[security] = self.market_class( '/'.join(( security, self.currency )), currency=self.currency )
        self.markets[security].buy( agent, amount, price, now=now, update=update )

    def enter( self, order, update=True ):
        """Enter the trade in the appropriate market, creating one if necessary.  Use this API, if you don't
        know if you're being supplied a market or an exchange.

        """
        if order.security not in self.markets:
            # Unless such a market already exists, disallow creating markets in other currencies
            assert order.currency == self.currency, \
                "Unable to enter orders for {} in {}$; only {}$ trades supported".format(
                    order.security, order.currency, self.currency )
            self.markets[order.security] = self.market_class( '/'.join(( order.security, order.currency )), currency=order.currency )
        self.markets[order.security].enter( order, update=update )

    def execute( self, now=None, **kwds ):
        """
        Invoke .execute on each market in the exchange, and yield all the resultant trades.
        """
        for mkt in self.markets.values():
            for trade in mkt.execute( now=now, **kwds ):
                yield trade

    def price( self, security ):
        if security in self.markets:
            return self.markets[security].price()
        return prices_t( None, None, None )
