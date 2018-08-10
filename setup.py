from setuptools import setup
import os, sys

here				= os.path.abspath( os.path.dirname( __file__ ))

__version__			= None
__version_info__		= None
exec( open( os.path.join( here, 'holofuel', 'version.py' ), 'r' ).read() )

install_requires		= open( os.path.join( here, 'requirements.txt' )).readlines()

setup(
    name			= "holofuel",
    version			= __version__,
    tests_require		= [ "pytest" ],
    install_requires		= install_requires,
    packages			= [ 
        "holofuel",
        "holofuel/model",
        "holofuel/model/trading",
        "holofuel/model/control",
    ],
    include_package_data	= True,
    author			= "Perry Kundert",
    author_email		= "perry.kundert@holo.host",
    description			= "Python modules for interacting with and modelling/testing the Holo Fuel system",
    long_description		= """\
Holo Fuel implement a currency where every unit is backed by wealth, and where
eligible holders of wealth may create credit.  The system implements a limit, K,
on the amount of credit created relative to pledged wealth, to control inflation
and deflation, automatically ensuring that the value of each unit of credit
remains roughly constant in terms of some "reference" basket of wealth. These
modules allow access to Holo Fuel from within Python programs.
""",
    license			= "GPLv3",
    keywords			= "Holo Fuel wealth-backed value-stable currency",
    url				= "https://github.com/Holo-Host/holofuel-python",
    classifiers			= [
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Environment :: Console",
        "Topic :: Communications",
    ],
)
