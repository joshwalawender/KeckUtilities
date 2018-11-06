#!/usr/env/python

import argparse
import numpy as np
from astropy import units as u

##-------------------------------------------------------------------------
## Parse Command Line Arguments
##-------------------------------------------------------------------------
## create a parser object for understanding command-line arguments
p = argparse.ArgumentParser(description=
'''Convert an elevation above the horizon to an airmass using the Pickering
(2002) formula:
1 / sin(h + 244/(165 + 47*h^1.1))
and estimate the extinction.
''')
## add arguments
p.add_argument('elevation', type=float,
               help="Elevation (in degrees) above the horizon")
## add options
p.add_argument("--extinction", dest="extinction", type=float,
    default=0.13, help="Extinction in magnitudes per airmass.")
args = p.parse_args()


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():
    h = args.elevation * u.degree # elevation of target above horizon
    magnitudes_per_airmass = args.extinction * u.mag

    # Pickering 2002 Airmass
    value = h.value + 244/(165.0 + 47.0*h.value**1.1)
    airmass = 1.0 / np.sin(value*u.degree)
    print(f'for EL = {h:.1f}')
    print(f'airmass = {airmass:.2f}')

    extinction = airmass * magnitudes_per_airmass
    print(f'extinction = {extinction:.2f}')


if __name__ == '__main__':
    main()
