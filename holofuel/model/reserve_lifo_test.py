import logging
from . import trading, near
from .reserve_lifo import reserve

def test_reserve_simple():
    logging.getLogger().setLevel( logging.INFO )
    HoloFuel_USD		= reserve( name="HoloFuel/USD", reserves={ .0007: 100 } )
    HoloFuel_USD.print_full_book()
    bid,ask,last		= HoloFuel_USD.price()
    assert last is None
    assert near( ask.price, .0007 )

    # Buy (Reture) the available reserves, emptying the tranche
    a1				= trading.agent( name="A1" )
    HoloFuel_USD.buy( a1, 100, .0007 )
    HoloFuel_USD.execute_all()
    bid,ask,last		= HoloFuel_USD.price()
    assert ask is None
    assert not HoloFuel_USD.reserves
    print( "assets: {!r}".format( HoloFuel_USD.assets ))

    # Sell (Issue) some Holo Fuel on the Reserve, creating new Reserves that can be bought
    HoloFuel_USD.sell( a1, 1000, .001 )
    HoloFuel_USD.execute_all()
    bid,ask,last		= HoloFuel_USD.price()
    assert near( ask.price, .001 )
