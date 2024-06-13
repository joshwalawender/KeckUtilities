#!/usr/env/python

'''
Name: queryTelSched.py

Purpose:
    Query the telescope database and return the value of `field` for the given
    `date` and `tel`.  Try to replicate functionality of the old queryTelSched
    which was located at: ~kics/instr/bin/queryTelSched (on a summit machine).
    
    This program tries to be backward compatible with the old telescope
    schedule database and programs which called it.  Some field names have
    changed with the new database, so a translation step is included in the
    queryTelSched function below.  To add additional translations, just add to
    the translations dictionary

Example Use:
    python queryTelSched.py 2018-12-18 1 Instrument

Arguments:
    date: The date for the query in  a string with YYYY-MM-DD format.

    tel: An int (1 or 2) indicating the telescope.

    field: A string with the field to return.  For more information on the API
        and on what fields are returnable, see the web liks below.

Additional Information on the Telescope Schedule API can be found here:
https://www.keck.hawaii.edu/software/db_api/telSchedule.php

Details on the getSchedule command and what it returns can be found here:
https://www.keck.hawaii.edu/software/db_api/telSchedule.php?cmd=getSchedule

Modification history:
    2018-12-18   jwalawender  Original version (adapted from old version for
                              old database API).
'''

## Import General Tools
import argparse
import logging
import requests
import json

##-------------------------------------------------------------------------
## Parse Command Line Arguments
##-------------------------------------------------------------------------
## create a parser object for understanding command-line arguments
p = argparse.ArgumentParser(description='''
''')
## add arguments
p.add_argument('date', type=str,
               help="Date (HST) in YYYY-MM-DD format.")
p.add_argument('tel', type=int,
               help="Telescope number as int (i.e. 1 or 2).")
p.add_argument('field', type=str,
               help="Field to query (e.g. Instrument).")
## add flags
p.add_argument("-v", "--verbose", dest="verbose",
    default=False, action="store_true",
    help="Be verbose! (default = False)")
args = p.parse_args()


##-------------------------------------------------------------------------
## Create logger object
##-------------------------------------------------------------------------
log = logging.getLogger('queryTelSched')
log.setLevel(logging.DEBUG)
LogConsoleHandler = logging.StreamHandler()
if args.verbose is True:
    LogConsoleHandler.setLevel(logging.DEBUG)
else:
    LogConsoleHandler.setLevel(logging.INFO)
LogFormat = logging.Formatter('%(levelname)9s: %(message)s')
LogConsoleHandler.setFormatter(LogFormat)
log.addHandler(LogConsoleHandler)


##-------------------------------------------------------------------------
## Define some useful functions
##-------------------------------------------------------------------------
def querydb(req):
    '''A simple wrapper to form a generic API level query to the telescope
    schedule web API.  Returns a JSON object with the result of the query.
    '''
    log.debug('Querying telescope schedule')
    url = f"https://www.keck.hawaii.edu/software/db_api/telSchedule.php?{req}"
    r = requests.get(url)
    return json.loads(r.text)


def get_schedule(date, tel):
    '''Use the querydb function and getSchedule of the telescope schedule web
    API with arguments for date and telescope number.  Returns a JSON object
    with the schedule result.
    '''
    if tel not in [1,2]:
        log.error("Telescope number must be 1 or 2.")
        return
    req = f"cmd=getSchedule&date={date}&telnr={tel}"
    result = querydb(req)
    log.debug('Got result from schedule database')
    return result


def get_all_kpf_programs():
    '''
    '''
    months = ['2024-08-01', '2024-09-01', '2024-10-01', '2024-11-01',
              '2024-12-01', '2025-01-01']
    tel = 1
    all_programs = []
    kpf = []
    for month in months:
        req = f"cmd=getScheduleByMonth&date={month}&telnr={tel}"
        result = querydb(req)
        all_programs.extend(result)
        print(f'Got {len(result)} results from schedule database')
        kpf_result = [entry for entry in result if entry['Instrument'] == 'KPF']
        print(f'Got {len(kpf_result)} KPF results from schedule database')
        kpf.extend(kpf_result)
    return kpf


def show_number_of_KPF_nights_assigned(kpf):
    results = {}
    for entry in kpf:
        if entry['ProjCode'] not in results.keys():
            results[entry['ProjCode']] = []
        results[entry['ProjCode']].append(f"{entry['StartTime']}-{entry['EndTime']}")
    return results



##-------------------------------------------------------------------------
## Main Program: queryTelSched
##-------------------------------------------------------------------------
def queryTelSched(date, tel, field):
    result = get_schedule(date, tel)
    log.debug(f"Found {len(result)} programs")

    translations = {'InstrAcc': 'Account',
                   }

    output_list = []
    for i,entry in enumerate(sorted(result, key=lambda x: x['StartTime'])):
        log.debug(f"Entry {i+1}:")
        for key in entry.keys():
            log.debug(f"  {key:>15s}: {entry[key]}")
        try:
            output_list.append(entry[field])
        except KeyError:
            log.error(f'Field "{field}" not found')
            if field in translations.keys():
                log.debug(f'Trying tranlated key "{translations[field]}"')
                output_list.append(entry[translations[field]])
                log.warning(f'Please update the script calling for "{field}" '
                            f'to use "{translations[field]}" instead.')
    print('/'.join(output_list))
    return output_list


if __name__ == '__main__':
    queryTelSched(args.date, args.tel, args.field)

