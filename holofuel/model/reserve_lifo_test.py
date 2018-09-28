import logging
import random
import math

from . import trading, near
from .trading import actor, need_t, engine_status, engine, world, month, week, day, hour
from .reserve_lifo import reserve, reserve_issuing

def test_reserve_simple():
    logging.getLogger().setLevel( logging.INFO )
    Holofuel_USD		= reserve( name="HoloFuel/USD", reserves={0: { .0007: 100 }} )
    Holofuel_USD.print_full_book()
    bid,ask,last		= Holofuel_USD.price()
    assert last is None
    assert near( bid.price, .0007 )

    # Agent A2 sells (Retires) Holo Fuel equal to the available reserves, emptying the tranche
    a1				= trading.agent( "A1" )
    Holofuel_USD.sell( a1, 100, .0007 )
    print( "assets:   {!r}".format( Holofuel_USD.assets ))
    print( "reserves: {!r}".format( Holofuel_USD.reserves ))
    assert len( Holofuel_USD.execute_all() ) == 1
    Holofuel_USD.print_full_book()
    print( "assets:   {!r}".format( Holofuel_USD.assets ))
    print( "reserves: {!r}".format( Holofuel_USD.reserves ))
    bid,ask,last		= Holofuel_USD.price()
    print( "bid:      {!r}".format( bid ))
    assert bid is None
    assert not Holofuel_USD.reserves

    # Agent A2 buys (Issue) some Holo Fuel on the Reserve, creating new Reserves that can be used to
    # redeem Holo fuel later.
    Holofuel_USD.buy( a1, 1000, .001 )
    Holofuel_USD.execute_all()
    print( "assets:   {!r}".format( Holofuel_USD.assets ))
    print( "reserves: {!r}".format( Holofuel_USD.reserves ))
    bid,ask,last		= Holofuel_USD.price()
    assert near( bid.price, .001 )

def test_reserve_issuing():
    # Make
    supply_available		= 1000
    supply_period		= 1 * day
    supply_book_value		= 1.00
    Holofuel_USD		= reserve_issuing( name="HoloFuel/USD", supply_book_value=supply_book_value,
                                                   supply_period=supply_period, supply_available=supply_available,
                                                   LIFO=True )
    print( "assets:   {!r}".format( Holofuel_USD.assets ))
    print( "reserves: {!r}".format( Holofuel_USD.reserves ))
    print( "{!r}".format( Holofuel_USD ))

    agent_count			= 10
    holo_need			= 100.00 # / month Start a bunch of agents, each of whom will need
    holo_need_weekly		= int( holo_need * week // month )

    # Acquire a need; some time unit's worth of Holo fuel for hosting a dApp.  Assume they can go
    # into infinite debt.
    agents			= [
        trading.actor(
            identity	= "A{}".format( n ),
            currency	= Holofuel_USD.currency,
            balance	= 0.,
            minimum	= -math.inf,
            quanta	= 6*hour,
            needs	= [ need_t( 1, None, 'HoloFuel', week, holo_need_weekly ) ] )
        for n in range( agent_count )
    ]

    # Lets run a simulation for a month, letting the agents collect their needs. The
    # prices should rise over time 'til the reserve prices are met
    duration			= 4 * week
    wld				= world( duration=duration )

    class eng_sts( engine_status ):
        def status( self, now=None ): # At exit, now == None
            super( eng_sts, self ).status( now=now )
            print( "%s Orders:\n%s" % (
                "Exit" if now is None else self.world.format_now( now ),
                self.exchange.format_book() ))

    with eng_sts( world=wld, exch=Holofuel_USD, agents=agents, status_period=day ) as eng:
        eng.run()

    # Confirm that the agents acquired the correct amount; their needs were weekly, and the duration
    # some multiple of that.
    for a in agents:
        for sec,amt in a.assets.items():
            print( "{:15} Owns {:9.4f} {}".format( str( a ), amt, sec ))
        assert near( amt, holo_need_weekly * duration / week )


def test_reserve_issuing_selective():
    """Test the concept of a reserve that allows any actor to buy/sell, but only redeems (buys) Holofuel
    in exchange for reserve funds to actors which are hosts.

    """

    class host( actor ):
        pass

    class reserve_for_hosts( reserve ):
        """Our reserve's trading.agent will only allow itself to buy Holofuel from a Holo 'host'"""
        def buys_from( self, another ):
            return isinstance( another, host )

    # 3 reserve tranches
    A				= actor()
    B				= host()
    R				= reserve_for_hosts( name="HoloFuel/USD",
                                                     reserves={ 0: { .138: 100 }, 1: {.140: 100 }, 2: { .139: 100 } } )

    # Lets ensure that only a host can buy Holo Fuel for cash, and access the reserve funds
    R.sell( B, 3 ) # A market trade; will get the best priced buyer
    print( R.format_book() )
    assert len( R.buying ) == 3 
    trades			= R.execute_all()
    assert len( trades ) == 1
    assert near( trades[0][0].price, .140 )
    assert B.assets[R.name] == -3
    assert B.currency == 'USD'
    assert near( B.balance*1, 3*.140 )

    # Try again, LIFO
    R.LIFO			= True
    R.run()
    R.sell( B, 9 ) # A market trade; will get the best priced buyer
    print( R.format_book() )
    assert len( R.buying ) == 1
    assert len( R.selling ) == 1
    trades			= R.execute_all()
    assert len( trades ) == 1
    assert near( trades[0][0].price, .139 ) # Newest reserve tranche is not highest priced
    assert B.assets[R.name] == -12
    assert B.currency == 'USD'
    assert near( B.balance*1, 3*.140 + 9*.139 )
    
    # Make sure a non-host cannot access reserves
    R.sell( A, 1 )
    R.sell( B, 1 )
    print( R.format_book() )
    assert len( R.buying ) == 1
    assert len( R.selling ) == 2
    trades			= R.execute_all()
    assert len( trades ) == 1
    assert not A.assets
    assert B.assets[R.name] == -13
    
    
