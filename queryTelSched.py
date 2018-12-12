#!/usr/env/python

'''

'''

## Import General Tools
import sys
import os
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


def querydb(req):
'''A simple wrapper to form a generic API level query to the telescope schedule
web API.  Returns a JSON object with the result of the query.
'''
    log.debug('Querying telescope schedule')
    url = f"https://www.keck.hawaii.edu/software/db_api/telSchedule.php?{req}"
    r = requests.get(url)
    return json.loads(r.text)


def get_schedule(date, tel):
'''Use the getSchedule command with the telescope schedule web API with
arguments for date and telescope number.  Returns a JSON object with the
schedule result.
'''
    if tel not in [1,2]:
        log.error("Telescope number must be 1 or 2.")
        return
    req = f"cmd=getSchedule&date={date}&telnr={tel}"
    result = querydb(req)
    log.debug('Got result from schedule database')
    return result


##-------------------------------------------------------------------------
## Main Program: queryTelSched
##-------------------------------------------------------------------------
def queryTelSched(date, tel, field):
'''Try to replicate basic functionality of the old queryTelSched located at
~kics/instr/bin/queryTelSched (on a summit machine).
'''
    result = get_schedule(date, tel)
    log.debug(f"Found {len(result)} programs")

    translations = {'InstrAcc': 'Instrument',
                   }

    output_list = []
    for entry in result:
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


if __name__ == '__main__':
    queryTelSched(args.date, args.tel, args.field)

