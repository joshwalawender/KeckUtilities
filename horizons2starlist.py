#!/usr/env/python

## Import General Tools
import sys
import os
import argparse
import logging
from datetime import datetime as dt
from datetime import timedelta as tdelta

import callhorizons

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table

##-------------------------------------------------------------------------
## Parse Command Line Arguments
##-------------------------------------------------------------------------
## create a parser object for understanding command-line arguments
p = argparse.ArgumentParser(description='''
''')
## add flags
p.add_argument("-v", "--verbose", dest="verbose",
    default=False, action="store_true",
    help="Be verbose! (default = False)")
p.add_argument("-f", "--from", dest="fromdate",
    help="From date for the starlist table (in ISO format)")
p.add_argument("-t", "--to", dest="todate",
    help="To date for the starlist table (in ISO format)")
p.add_argument("-s", "--spacing", dest="spacing",
    default="1h",
    help="The spacing for each starlist entry (e.g. 1h or 15m)")
## add arguments
p.add_argument('name', type=str,
               help="The name of the target compatible with JPL horizons")
args = p.parse_args()

if args.fromdate is None:
    fromdate = dt.utcnow()
else:
    try:
        fromdate = dt.strptime(args.fromdate, '%Y-%m-%dT%H:%M:%S')
    except:
        print('Could not parse from date')
        raise

if args.todate is None:
    todate = dt.utcnow() + tdelta(1, 0)
else:
    try:
        todate = dt.strptime(args.todate, '%Y-%m-%dT%H:%M:%S')
    except:
        print('Could not parse to date')
        raise

##-------------------------------------------------------------------------
## Create logger object
##-------------------------------------------------------------------------
log = logging.getLogger('MyLogger')
log.setLevel(logging.DEBUG)
## Set up console output
LogConsoleHandler = logging.StreamHandler()
if args.verbose is True:
    LogConsoleHandler.setLevel(logging.DEBUG)
else:
    LogConsoleHandler.setLevel(logging.INFO)
LogFormat = logging.Formatter('%(asctime)s %(levelname)8s: %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')
LogConsoleHandler.setFormatter(LogFormat)
log.addHandler(LogConsoleHandler)
## Set up file output
# LogFileName = None
# LogFileHandler = logging.FileHandler(LogFileName)
# LogFileHandler.setLevel(logging.DEBUG)
# LogFileHandler.setFormatter(LogFormat)
# log.addHandler(LogFileHandler)


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main(name, fromdate, todate, obscode=568, spacing='1h'):
    log.debug(f'Querying horizons for: "{name}"')
    target = callhorizons.query(name)
    fromstr = fromdate.strftime('%Y-%m-%d %H:%M')
    tostr = todate.strftime('%Y-%m-%d %H:%M')
    log.debug(f'  From: "{fromstr}"')
    log.debug(f'  To:   "{tostr}"')
    log.debug(f'  Increment: "{spacing}"')
    target.set_epochrange(fromstr, tostr, spacing)
    try:
        target.get_ephemerides(obscode)
    except ValueError as e:
        log.error("Failed to get ephemerides")
        print(e.args[0])
    tab = Table(target.data)
    if len(tab) == 0:
        log.error("ephemerides have zero length")

    name = name.replace("/", "")
    name = name.replace(" ", "_")

    wasup = True
    for entry in tab:
        time = (entry['datetime'].split(' ')[1]).replace(':', '')
        starlistname = f'{name[0:9]:s}_{time:s}'
        if np.isnan(float(entry['airmass'])) == True:
            if wasup == True:
                print(f"# Target {name} is down at {time}")
                wasup = False
        else:
            line = [f'{starlistname:15s}']
            coord = SkyCoord(entry['RA'], entry['DEC'], frame='fk5', unit=(u.deg, u.deg))
            line.append(f'{coord.to_string("hmsdms", sep=" ", precision=2)}')
            line.append(f'{coord.equinox.jyear:.2f}')
            line.append(f'dra={float(entry["RA_rate"])/15*3600:.3f}')
            line.append(f'ddec={float(entry["DEC_rate"])*3600:.3f}')
            line.append(f'vmag={float(entry["V"]):.2f}')
            line.append(f'# airmass={float(entry["airmass"]):.2f}')
            print(' '.join(line))


if __name__ == '__main__':
    main(args.name, fromdate, todate, spacing=args.spacing)
