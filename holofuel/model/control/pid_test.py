from __future__ import absolute_import, print_function, division

from . import pid
from .. import near

def test_pid_simple():
    control             = pid.controller( Kpid = ( 2.0, 1.0, 2.0 ), setpoint=1.0, process=1.0, now = 0. )
    assert near( control.loop( 1.0, 1.0, now = 1. ),   0.0000 )
    assert near( control.loop( 1.0, 1.0, now = 2. ),   0.0000 )
    assert near( control.loop( 1.0, 1.1, now = 3. ),  -0.5000 )
    assert near( control.loop( 1.0, 1.1, now = 4. ),  -0.4000 )
    assert near( control.loop( 1.0, 1.1, now = 5. ),  -0.5000 )
    assert near( control.loop( 1.0, 1.05,now = 6. ),  -0.3500 )
    assert near( control.loop( 1.0, 1.05,now = 7. ),  -0.5000 )
    assert near( control.loop( 1.0, 1.01,now = 8. ),  -0.3500 )
    assert near( control.loop( 1.0, 1.0, now = 9. ),  -0.3900 )
    assert near( control.loop( 1.0, 1.0, now =10. ),  -0.4100 )
    assert near( control.loop( 1.0, 1.0, now =11. ),  -0.4100 )
