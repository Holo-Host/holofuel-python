import logging

from . import trading

class ReserveAccount:
    """
    The reserves_account class generates a reserves_account object for a specified currency pair
    Reserves accounts are initialised with an order book that starts at ICO price unless otherwise specified, and a reserve balance of 0

    Reserve accounts have 6 function calls:
    - quote: returns the current marginal price and the order book volume at that price
    - update_supply: changes the supply factor variable that determines the order book volume available at each price band
    - issue: adds reserves to the reserve balance and subtracts corresponding orderbook volume
    - retire: subtracts reserves from the reserve balance and adds corresponding orderbook volume
    - refresh: refreshes the orderbook starting with the current price
    - print_full_book: prints the entire order book and reserve LIFO book
    """

    def __init__(self, currency_pair, supply_factor=1.0, start_price=0.0001, reserve_price=0.00005, reserve_balance=0.0, orderbook_len=5):
        """
        :currency_pair  : the currency pair that Holo Fuel is traded against at this account
        :supply_factor  : Each price tranch of the order book has a volume of supply_factor * 1,000,000 Fuel
        :start_price    : the starting lowest price offered by the reserve order book denominated in {currency_pair}
        :reserve_balance: sets the amount of {currency_pair} held in the reserve at start
        :orderbook_len  : the number of tranches to maintain in the orderbook
        """

        self.supply_factor = supply_factor # For P-D control over orderbook volumes
        self.current_price = start_price
        self.currency_pair = currency_pair
        self.orderbook_len = orderbook_len

        self.order_book_vol = deque(maxlen=self.orderbook_len)
        self.order_book_price = deque(maxlen=self.orderbook_len)
        self.reserves = deque() # Create reserve as double-ended queue and append tranches

        self.refresh()
        
        retire_price = reserve_price
        reserve_tranch = [retire_price, self.supply_factor * 1000000] # we keep vol and price together for reserves because unlike order book we can't shift one vs. the other
        self.reserves.appendleft(reserve_tranch)
        # The oldest price in the reserves will be on the right, and the newest will be on the left


    def update_supply(self, new_supply_factor=None):
        """
        This function is designed to rebuild the orderbook when changing the supply factor
        It functions mostly like the original order book builder - starting with current price and adding higher price tranches at % intervals
        A key difference is treatment of partial tranche volumes (i.e. where some volume has already been bought)
        We will move the partial tranche volume to the current price, and scale it by the change in the supply factor
        """
        old_supply_factor = self.supply_factor
        if new_supply_factor is not None:
            self.supply_factor = new_supply_factor

        current_tranch_vol = self.order_book_vol[-1]

        for ii in range(self.orderbook_len):
            issue_price = self.current_price * (1 + ii/100) # Reserve tranches need increment in % of price, otherwise at higher prices you get ludicrous volumes available before meaningful price change
            self.order_book_price.appendleft(issue_price)
            if ii == 0:
                self.order_book_vol.appendleft(self.supply_factor/old_supply_factor * current_tranch_vol)
            else:
                self.order_book_vol.appendleft(self.supply_factor * 1000000)


    def quote(self, order_type):
        """
        :order_type: 'buy' to buy fuel from reserve (issue) or 'sell' to sell and retire fuel at reserve
        """
        if order_type == 'buy':
            volume = self.order_book_vol[-1]
            price = self.order_book_price[-1]

        elif order_type == 'sell':
            volume = self.reserves[0][1]
            price = self.reserves[0][0]
        else:
            print('No order type specified. Please specify "buy" or "sell"')
            return

        return price, volume


    def issue(self, volume):
        """
        :volume: Volume of Fuel to be issued
        """
        sum_orderbook_vol = sum(self.order_book_vol)

        if volume > sum_orderbook_vol:
            print("Volume exceeds total orderbook volume")
            return

        # Update orderbook for purchases
        while volume > 0:
            quote_price, quote_vol = self.quote('buy')
            self.current_price = quote_price
            buy_vol = min(quote_vol, volume)
            remainder = quote_vol - buy_vol

            if remainder == 0:
                self.order_book_vol.pop()
                self.order_book_price.pop()
            else:
                self.order_book_vol[-1] = remainder
            
            if self.reserves[0][0] == self.current_price:
                self.reserves[0][1] += buy_vol
            else:
                self.reserves.appendleft([self.current_price, buy_vol])

            volume -= buy_vol

        # add new tranches to replace bought ones
        for ii in range(len(self.order_book_vol), self.orderbook_len):
            self.order_book_price.appendleft(self.current_price * (1 + ii/100))
            self.order_book_vol.appendleft(self.supply_factor * 1000000)


    def retire(self, volume):
        """
        :volume: Volume of Fuel to be retired
        """
        sum_reserve_vol = sum([tranche[1] for tranche in self.reserves])

        if volume > sum_reserve_vol:
            print("Volume exceeds total reserve volume")
            return

        # Update LIFO accounts
        while volume > 0:
            quote_price, quote_vol = self.quote('sell')
            self.current_price = quote_price
            sell_vol = min(quote_vol, volume)
            remainder = quote_vol - sell_vol

            if remainder == 0:
                self.reserves.popleft()
            else:
                self.reserves[0] = [self.current_price, remainder]

            # Add the retired volume to the order book
            if self.order_book_price[-1] == self.current_price:
                self.order_book_vol[-1] += sell_vol
            else:
                self.order_book_price.append(self.current_price)
                self.order_book_vol.append(sell_vol)
                
            volume -= sell_vol
    
    def refresh(self):
        self.order_book_price.clear()
        self.order_book_vol.clear()
        
        for ii in range(self.orderbook_len):
            issue_price = self.current_price * (1 + ii/100) # Reserve tranches need increment in % of price, otherwise at higher prices you get ludicrous volumes available before meaningful price change
            self.order_book_price.appendleft(issue_price)
            self.order_book_vol.appendleft(self.supply_factor * 1000000)
            # The cheapest price in the order book will be on the right, and the most expensive will be on the left

    def print_full_book(self):
        for ii in range(len(self.order_book_vol)):
            print("Issue: {} Fuel @ Price of {:.5f} {}".format(self.order_book_vol[ii], self.order_book_price[ii], self.currency_pair))

        print("===============================================")

        for ii in range(len(self.reserves)):
            print("Buy-Back: {} Fuel @ Price of {:.5f} {}".format(self.reserves[ii][1], self.reserves[ii][0], self.currency_pair))


class reserve( trading.market, trading.agent ):
    """A simple Reserve market (and agent) that just posts sell/asks, at the price it paid/bid for the
    asset.  Reserves are ordered by price, not by order bought/sold.

    While this market has an agent that provides liquidity in the form of Retiring Holo Fuel via
    access to Reserves tranches at their original price, and perhaps Issuing Holo Fuel at some
    price(s), there is nothing that prevents other agents from buying/selling to eachother on the
    market at any prices they wish; these transactions do not affect the self.reserves, nor do they
    create/destroy Holo Fuel; they simply transfer ownership at a mutually agreeable price.

    While having no net effect on the amount of Holo Fuel in the system, it does give us valuable
    price information that could be useful for automation.

    """
    def __init__( self, name, identity=None, reserves=None, **kwds ):
        assert name, "A Reserve name (eg. 'Security/Currency') must be provided"
        if not identity: # The Reserve's Market Maker agent
            identity		= '{} Reserve'.format( name ) # Eg. HoloFuel/USD Reserve
        super( reserve, self ).__init__( name=name, identity=identity, **kwds )
        self.reserves	= dict( reserves ) if reserves else {} # { <price>: <amount>, ... }
        self.run( now=self.now )

    def execute( self, now=None ):
        """After executing all trades available, rebuild the Reserve order book from the reserves."""
        for order in super( reserve, self ).execute( now=now ):
            yield order
        self.run()

    def run( self, exch=None, now=None ):
        """Evaluates Currency reserves, and places buy orders (so other agents can sell, Retiring Holo fuel
        for USD$) for each tranche at its original Holo fuel / USD$ price.

        All outstanding orders are closed to begin; only buy orders will exist for this agent at return.
        """
        assert exch is None, \
            "A reserve is both a trading.market and an agent; no market need be supplied "
        super( reserve, self ).run( exch=self, now=now )
        self.close( self )
        for price,amount in self.reserves.items():
            self.buy( self, amount=amount, price=price, now=now )

    def record( self, order, comment=None ):
        """Adjust reserves by the amount bought/sold, retiring tranches as they are exhausted."""
        super( reserve, self ).record( order=order, comment=comment )
        self.reserves.setdefault( order.price, 0 )
        self.reserves[order.price] -= order.amount
        if self.reserves[order.price] == 0:
            logging.info( "{:<20} emptied Reserve tranche @ {}${:9.4f}".format(
                str( order.agent ), order.currency, order.price ))
            self.reserves.pop( order.price )

    def print_full_book( self, width=40 ):
        """Print buy/sell order book w/ incl. depth chart."""
        print( self.format_book( width=width ))
        

class reserve_issuing( reserve ):
    """A Reserve market that computes a sequence of buy (Issue) prices.  Supply Issuance/Retirement may
    be controlled on either total volume or relative ratio, with the goal being the net Issuance or
    Retirement of credit.

    In its simplest form, it supplies a certain fixed amount of supply Issuance per time period, and
    modulates its supply_premium (vs. book value, or highest Retirement tranche value) to maintain
    that hourly average net supply Issuance rate.

    Each Currency/Holo Fuel pair must also be balanced, such that the flow in/out of Holo Fuel is
    proportional to the size of each market.  This automatically accounts for changes in the
    relative valuation of external currency pairs (eg. USDEUR).

    Over some time period, we probably wish to target some total amount of volume and some ratio of
    Issue/Retire.  We can use our agent.trades list over the last hour to compute the volume and
    buy/sell ratio.

    """
    def __init__( self, supply_available=None, supply_factor=None, supply_premium=None, supply_amount=1000000,
                  supply_period=None, supply_ratio=None, supply_book_value=None, **kwds ):
        self.supply_book_value	= 1.0     if supply_book_value	is None else supply_book_value	# Initial supply book value
        self.supply_period	= 60 * 60 if supply_period	is None else supply_period	# 1hr
        self.supply_ratio	= 1       if supply_ratio	is None else supply_ratio	# 1/1 (neutral Issue/Retire)
        self.supply_factor	= 1       if supply_factor	is None else supply_factor	# 1.0
        self.supply_premium	= 1       if supply_premium	is None else supply_premium	# supply price vs. 
        assert supply_available is not None, \
            "Must provide a supply_available per {}hr period".format( self.supply_period // ( 60 * 60 ))
        self.supply_available	= supply_available
        super( reserve_issuing, self ).__init__( **kwds )
    
    @property
    def supply_premium( self ):
        """The supply_premium may be computed, eg. by a PID loop, to equalize flows between markets."""
        return self._supply_premium
    @supply_premium.setter
    def supply_premium( self, value ):
        self._supply_premium	= value

    @property
    def supply_value( self ):
        """The supply_value may be computed, eg. from book value, trailing average, last trade price, etc."""
        return self._supply_value
    @supply_value.setter
    def supply_value( value ):
        self._supply_value	= value

        
    def run( self, exch=None, now=None ):
        """Compute the amount of Holo Fuel available to Issue (based on the time quanta), and make it
        available in a sequence of asks.  Our goal is to seek the current equilibrium price,
        starting from the most recent trades.  

        A possible embodiment just asks a sequence of prices; the last trade's price indicates the
        maximum market price. Of course, the cost is the sale/Issue of Holo Fuel at unnecessarily
        low prices. 

        So, to mimimize that loss, we'll target a flow of supply_factor * supply_amount per unit
        time, and an exponential decreasing function defining what is available at each price point.
        As we lose coherence (time since last buy), we'll spread that function out (wider range of
        prices, but larger amounts are further away from the target price).
        
        The simplest embodiment just issues everything at one price (the book value * premium), and
        tries to issue supply_amount per supply_period.  It looks at the amount sold over the
        trailing period, and adjust the amount available to the remaining amount.  Then, it enters
        sell orders (so other agents can buy, Issuing Holo fuel for USD$).

        """
        super( reserve_issuing, self ).run( exch=exch, now=now ) # closes all open orders, issues buys
        buy,sell		= self.volume( period=self.supply_period, now=now )
        supply_sold_period	= sell - buy
        supply_price		= self.supply_book_value * self.supply_premium
        if supply_sold_period < self.supply_available:
            self.sell( agent=self, amount=self.supply_available - supply_sold_period, price=supply_price )
