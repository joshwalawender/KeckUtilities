#!/usr/env/python

## Import General Tools
import sys
import os
import argparse
import logging
from datetime import datetime as dt
from datetime import timedelta as tdelta

from SupportNightCalendar import querydb, get_SA, get_telsched

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
## add options
p.add_argument("-d", "--date", dest="input", type=str,
    help="Date of the observing night (in YYYY-mm-dd format).")
p.add_argument("--sa", dest="sa", type=str,
    help="SA name.  Will grab list of observers from net SA support run.")
args = p.parse_args()


##-------------------------------------------------------------------------
## Create logger object
##-------------------------------------------------------------------------
log = logging.getLogger('MyLogger')
log.setLevel(logging.DEBUG)
## Set up console output
LogConsoleHandler = logging.StreamHandler()
LogConsoleHandler.setLevel(logging.DEBUG)
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
def main():
    today = dt.utcnow()
    dateobj = dt.utcnow()
    dates = []
    
    done = False
    while not done:
        date = dateobj.strftime('%Y-%m-%d')
        print(f"Checking: {date}")
        if args.sa == get_SA(date=date, tel=1):
            dates.append([date, 1])
        elif args.sa == get_SA(date=date, tel=2):
            dates.append([date, 2])
        else:
            if len(dates) != 0:
                done = True
            if today > today + tdelta(30,0):
                done = True
        dateobj += tdelta(1,0)

    for date in dates:
        result = get_telsched(from_date=date[0], ndays=1, telnr=date[1])[0]
        print(result)
        print(result['PiEmail'])
        print(result['Observers'])

if __name__ == '__main__':
    main()
