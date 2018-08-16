import logging
from . import trading, near
from .reserve_lifo import reserve, reserve_issuing

def test_reserve_simple():
    logging.getLogger().setLevel( logging.INFO )
    HoloFuel_USD		= reserve( name="HoloFuel/USD", reserves={ .0007: 100 } )
    HoloFuel_USD.print_full_book()
    bid,ask,last		= HoloFuel_USD.price()
    assert last is None
    assert near( bid.price, .0007 )

    # Agent A2 sells (Retires) Holo Fuel equal to the available reserves, emptying the tranche
    a1				= trading.agent( "A1" )
    HoloFuel_USD.sell( a1, 100, .0007 )
    print( "assets:   {!r}".format( HoloFuel_USD.assets ))
    print( "reserves: {!r}".format( HoloFuel_USD.reserves ))
    print( "{!r}".format( HoloFuel_USD ))
    HoloFuel_USD.execute_all()
    print( "assets: {!r}".format( HoloFuel_USD.assets ))
    print( "{!r}".format( HoloFuel_USD ))
    bid,ask,last		= HoloFuel_USD.price()
    assert bid is None
    assert not HoloFuel_USD.reserves

    # Agent A2 buys (Issue) some Holo Fuel on the Reserve, creating new Reserves that can be used to
    # redeem Holo fuel later.
    HoloFuel_USD.buy( a1, 1000, .001 )
    HoloFuel_USD.execute_all()
    print( "assets:   {!r}".format( HoloFuel_USD.assets ))
    print( "reserves: {!r}".format( HoloFuel_USD.reserves ))
    print( "{!r}".format( HoloFuel_USD ))
    bid,ask,last		= HoloFuel_USD.price()
    assert near( bid.price, .001 )

def test_reserve_issuing():
    logging.getLogger().setLevel( logging.INFO )
    HoloFuel_USD		= reserve_issuing( name="HoloFuel/USD",
                                        supply_book_value=1.0, supply_period=60*60, supply_available=1000000 )
    print( "assets:   {!r}".format( HoloFuel_USD.assets ))
    print( "reserves: {!r}".format( HoloFuel_USD.reserves ))
    print( "{!r}".format( HoloFuel_USD ))

    '''
    stipend			= 1000
    agent_count			= 100
    need			= need_t( 1, 
    agents			= [ trading.actor( "A{}".format( n ), currency=Holofuel_USD.currency, balance=stipend
                                                   need)
                                    for n in range( agent_count ) ]
    '''
    
    
