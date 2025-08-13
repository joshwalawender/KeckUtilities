import os
import datetime
import json
import requests
import urllib3
urllib3.disable_warnings() # We're going to do verify=False, so ignore warnings


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
    url_base = 'https://vm-appserver.keck.hawaii.edu/api'
    # Submit query
    if post == False:
        r = requests.get(f"{url_base}/{api}/{query}", params=params)
    else:
        r = requests.post(f"{url_base}/{api}/{query}", json=params, verify=False)
    # Parse result
    try:
        result = json.loads(r.text)
    except Exception as e:
        print(f'Failed to parse result:')
        print(r.text)
        print(e)
        result = None
    return result


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
