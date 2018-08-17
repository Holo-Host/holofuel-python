import logging
import random
import math

from . import trading, near
from .trading import need_t, engine, world, month, day, hour
from .reserve_lifo import reserve, reserve_issuing

def test_reserve_simple():
    logging.getLogger().setLevel( logging.INFO )
    Holofuel_USD		= reserve( name="HoloFuel/USD", reserves={ .0007: 100 } )
    Holofuel_USD.print_full_book()
    bid,ask,last		= Holofuel_USD.price()
    assert last is None
    assert near( bid.price, .0007 )

    # Agent A2 sells (Retires) Holo Fuel equal to the available reserves, emptying the tranche
    a1				= trading.agent( "A1" )
    Holofuel_USD.sell( a1, 100, .0007 )
    print( "assets:   {!r}".format( Holofuel_USD.assets ))
    print( "reserves: {!r}".format( Holofuel_USD.reserves ))
    print( "{!r}".format( Holofuel_USD ))
    Holofuel_USD.execute_all()
    print( "assets: {!r}".format( Holofuel_USD.assets ))
    print( "{!r}".format( Holofuel_USD ))
    bid,ask,last		= Holofuel_USD.price()
    assert bid is None
    assert not Holofuel_USD.reserves

    # Agent A2 buys (Issue) some Holo Fuel on the Reserve, creating new Reserves that can be used to
    # redeem Holo fuel later.
    Holofuel_USD.buy( a1, 1000, .001 )
    Holofuel_USD.execute_all()
    print( "assets:   {!r}".format( Holofuel_USD.assets ))
    print( "reserves: {!r}".format( Holofuel_USD.reserves ))
    print( "{!r}".format( Holofuel_USD ))
    bid,ask,last		= Holofuel_USD.price()
    assert near( bid.price, .001 )

def test_reserve_issuing():
    logging.getLogger().setLevel( logging.INFO )
    Holofuel_USD		= reserve_issuing( name="HoloFuel/USD",
                                        supply_book_value=1.0, supply_period=60*60, supply_available=1000000 )
    print( "assets:   {!r}".format( Holofuel_USD.assets ))
    print( "reserves: {!r}".format( Holofuel_USD.reserves ))
    print( "{!r}".format( Holofuel_USD ))

    stipend			= 1000
    agent_count			= 100
    holo_need			= 100.00 # / month Start a bunch of agents, each of whom will need
    # to acquire an hour's worth of Holo fuel for hosting a Holofuel$100.0/mo dApp.  Assume they can
    # go into infinite debt.
    agents			= [ trading.actor( "A{}".format( n ), currency=Holofuel_USD.currency, balance=0., minimum=-math.inf,
                                        needs=[ need_t( 1, trading.hour * random.random(), 'HoloFuel', hour, holo_need * hour // month ) ] )
                                    for n in range( agent_count ) ]
    
    duration		= 1 * day
    wld			= world( duration=duration )
    eng			= engine( world=wld, exch=Holofuel_USD, agents=agents )
    eng.run()
