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
    try:
        result = json.loads(r.text)
    except json.decoder.JSONDecodeError as e:
        print('Error from database query.')
        print(url)
        print('Returned Value:')
        print(r.text)
        print('----')
        raise(e)
    return result


def get_SA(date=None, tel=1):
    if date is None:
        return None
    req = f"cmd=getNightStaff&date={date}&type=sa&telnr={tel}"
    try:
        sa = querydb(req)[0]['Alias']
    except:
        sa= ''
    return sa


def isCancelled(date=None, tel=1):
    if date is None:
        return None
    req = f"cmd=getObservingStatus&date={date}"
    result = querydb(req)
    for entry in result:
        if (entry['Date'] == date) and entry['TelNr'] == str(tel):
#             print(f'{date} K{tel}: {entry["ObservingStatus"]}')
            cancelled = (entry['ObservingStatus'] == 'cancelled')
    return cancelled


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


def get_instrument_location(instrument, date=None):
    if date is None:
        dateobj = dt.now()
        date = dateobj.strftime('%Y-%m-%d')
    req = f"cmd=getInstrumentStatus&date={date}"
    results = querydb(req)[0]
    location = results[instrument]['Location']
    return location


def get_observers_for_id(id):
    req = f'cmd=getObservers&obsid={id}'
    return querydb(req)


def get_user_info(date, inst):
    req = f'cmd=getUserInfo&instr={inst}&startdate={date}&enddate={date}'
    return querydb(req)


def get_observer_info(obsid):
    '''cmd=getObserverInfo&obsid=#
    '''
    if obsid == '':
        return {'Id': '',
                'Email': '',
                'FirstName': '',
                'LastName': '',
                'Phone': '',
                'username': ''}
    req = f"cmd=getObserverInfo&obsid={obsid}"
    return querydb(req)


if __name__ == '__main__':
    pass
