#!/usr/env/python

## Import General Tools
import sys
import os
import logging

import requests
import json
from datetime import datetime as dt
from datetime import timedelta as tdelta

import numpy as np
from astropy.table import Table, Column


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
## Get Telescope Schedule
##-------------------------------------------------------------------------
def querydb(req):
    url = f"https://www.keck.hawaii.edu/software/db_api/telSchedule.php?{req}"
    r = requests.get(url)
    return json.loads(r.text)


def get_SA(date=None, tel=1):
    if date is None:
        return None
    req = f"cmd=getNightStaff&date={date}&type=sa&telnr={tel}"
    try:
        sa = querydb(req)[0]['Alias']
    except:
        sa= ''
    return sa


def get_telsched(from_date=None, ndays=None, telnr=None):
    if from_date is None:
        now = dt.now()
        from_date = now.strftime('%Y-%m-%d')
    else:
        assert dt.strptime(from_date, '%Y-%m-%d')

    req = f"cmd=getSchedule&date={from_date}"
    if telnr is not None:
        req += f"&telnr={telnr:d}"
    if ndays is not None:
        req += f"&numdays={ndays}"
    telsched = Table(data=querydb(req))
    telsched.sort(keys=['Date', 'TelNr'])
    return telsched


def add_SA_to_telsched(telsched):
    sas = [get_SA(date=x['Date'], tel=x['TelNr']) for x in telsched]
    telsched.add_column(Column(sas, name='SA'))
    return telsched


if __name__ == '__main__':
    pass
