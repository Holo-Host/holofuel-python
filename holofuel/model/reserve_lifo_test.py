import logging
from . import trading, near
from .reserve_lifo import reserve

def test_reserve_simple():
    logging.getLogger().setLevel( logging.INFO )
    USD_HFL			= reserve( name="USDHFL", reserves={ .0007: 100 } )
    USD_HFL.print_full_book()
    bid,ask,last		= USD_HFL.price()
    assert last is None
    assert near( ask.price, .0007 )

    # Buy (Reture) the available reserves, emptying the tranche
    a1				= trading.agent( name="A1" )
    USD_HFL.buy( a1, 100, .0007 )
    USD_HFL.execute_all()
    bid,ask,last		= USD_HFL.price()
    assert ask is None
    assert not USD_HFL.reserves

    # Sell (Issue) some Holo Fuel on the Reserve, creating new Reserves that can be bought
    USD_HFL.sell( a1, 1000, .001 )
    USD_HFL.execute_all()
    bid,ask,last		= USD_HFL.price()
    assert near( ask.price, .001 )
