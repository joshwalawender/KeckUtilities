import os
import datetime
import yaml
import json
import requests
import urllib3
urllib3.disable_warnings() # We're going to do verify=False, so ignore warnings

# Human readbale API info at, for example:
# https://vm-appserver.keck.hawaii.edu/api/schedule/swagger/#/

url_base = 'https://vm-appserver.keck.hawaii.edu'


def get_semester_dates(date):
    if isinstance(date, datetime.datetime):
        if date.month == 1:
            semester = f'{date.year-1}B'
            semester_start_str = f'{date.year-1}-08-01 00:00:00'
            semester_end_str = f'{date.year}-01-31 23:59:59'
        elif date.month > 1 and date.month < 8:
            semester = f'{date.year}A'
            semester_start_str = f'{date.year}-02-01 00:00:00'
            semester_end_str = f'{date.year}-07-31 23:59:59'
        else:
            semester = f'{date.year}B'
            semester_start_str = f'{date.year}-08-01 00:00:00'
            semester_end_str = f'{date.year+1}-01-31 23:59:59'
    elif isinstance(date, str):
        year = int(date[:4])
        semester = date
        if semester[-1] == 'A':
            semester_start_str = f'{year}-02-01 00:00:00'
            semester_end_str = f'{year}-07-31 23:59:59'
        elif semester[-1] == 'B':
            semester_start_str = f'{year}-08-01 00:00:00'
            semester_end_str = f'{year+1}-01-31 23:59:59'
    semester_start = datetime.datetime.strptime(semester_start_str, '%Y-%m-%d %H:%M:%S')
    semester_end = datetime.datetime.strptime(semester_end_str, '%Y-%m-%d %H:%M:%S')
    return semester, semester_start, semester_end


##-------------------------------------------------------------------------
## query_observatoryAPI
##-------------------------------------------------------------------------
def query_observatoryAPI(api, query, params, post=False):
    if api == 'proposals' and 'hash' not in params.keys():
        params['hash'] = os.getenv('APIHASH', default='')
    # Submit query
    if post == False:
        r = requests.get(f"{url_base}/api/{api}/{query}", params=params)
    else:
        r = requests.post(f"{url_base}/api/{api}/{query}", json=params, verify=False)
    # Parse result
    try:
        result = json.loads(r.text)
    except Exception as e:
        print(f'Failed to parse result:')
        print(r.text)
        print(e)
        result = None
    return result


def get_routes(api):
    url = f"{url_base}/{api}/swagger/{api}_api.yaml"
    r = requests.get(url)
    result = yaml.safe_load(r.text)
    try:
        output = [r[1:] for r in result.get('paths').keys()]
    except:
        output = result
    return output


##-------------------------------------------------------------------------
## A few specific queries
##-------------------------------------------------------------------------
def getSchedule(date=None, numdays=1, telnr=None):
    if date is None:
        now = datetime.datetime.now()
        date = now.strftime('%Y-%m-%d')
    params = {'date': date, 'numdays': str(numdays)}
    if telnr is not None:
        params['telnr'] = str(telnr)
    return query_observatoryAPI('schedule', 'getSchedule', params)


def getCancelledStatus(date):
    params = {'date': date}
    result = query_observatoryAPI('schedule', 'getObservingStatus', params)
    k1status = [x['ObservingStatus'] for x in result if x['TelNr'] == 1][0]
    k2status = [x['ObservingStatus'] for x in result if x['TelNr'] == 2][0]
    cancelled = {'K1': k1status == 'cancelled',
                 'K2': k2status == 'cancelled'}
    return cancelled


def getTwilights(date):
    result = query_observatoryAPI('metrics', '', {'date': date})
    return result[0]


def getNightStaff(date=None, numdays=1, telnr=None, role='sa'):
    if date is None:
        now = datetime.datetime.now()
        date = now.strftime('%Y-%m-%d')
    params = {'date': date, 'numdays': str(numdays), 'type': role}
    if telnr is not None:
        params['telnr'] = str(telnr)
    return query_observatoryAPI('employee', 'getNightStaff', params)


def getPI(semid):
    return query_observatoryAPI('proposals', 'getPI', {'semid': semid})


def getObserverInfo(observerID):
    return query_observatoryAPI('schedule', 'getObserverInfo', {'obsid': observerID})


def getInstrumentDates(instrument, start, end):
    return query_observatoryAPI('schedule', 'getInstrumentDates',
                               {'instrument': instrument,
                                'startdate': start,
                                'enddate': end})

##-------------------------------------------------------------------------
## Useful scripts
##-------------------------------------------------------------------------
def get_nights_for_SA(start_date=None, numdays=7, sa='jwalawender'):
    if start_date is None:
        now = datetime.datetime.now()
        date = now.strftime('%Y-%m-%d')
    if numdays is None:
        semester, semester_start, semester_end = get_semester_dates(now)
        duration = semester_end-now
        numdays = duration.days
    sas = getNightStaff(date=start_date, numdays=numdays)
    nights = [(entry['Date'], entry['TelNr']) for entry in sas if entry['Alias'] == sa]
    nights = sorted(set(nights))
    return nights




##-------------------------------------------------------------------------
## For testing
##-------------------------------------------------------------------------
if __name__ == '__main__':
    api = 'schedule'
    query = 'getSchedule'
    params = {'date': '2025-08-12',
              'numdays': '1',
              'telnr': '1',
              }
    query_observatoryAPI(api, query, params)
