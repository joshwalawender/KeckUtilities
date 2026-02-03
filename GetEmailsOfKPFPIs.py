#!python

## Import General Tools
import sys
import os
import argparse
import datetime

from utils.observatoryAPIs import query_observatoryAPI, get_semester_dates, getInstrumentDates, getSchedule, getPI


##-------------------------------------------------------------------------
## Parse Command Line Arguments
##-------------------------------------------------------------------------
## create a parser object for understanding command-line arguments
p = argparse.ArgumentParser(description='''
''')
## add options
p.add_argument("semester", type=str,
    help="Semester to pull PI and Co-I emails for (e.g. 26A).")
args = p.parse_args()






if __name__ == '__main__':
    
    # Get start and end dates
    semester, start, end = get_semester_dates(args.semester)
    start = datetime.datetime.strftime(start, '%Y-%m-%d')
    end = datetime.datetime.strftime(end, '%Y-%m-%d')

    # Get Instrument Dates
    instrument_dates = getInstrumentDates('KPF', start, end)

    # Get PI Names and emails
    emails = {}
    for dateinfo in instrument_dates:
        sched = getSchedule(date=dateinfo['Date'])
        for entry in sched:
            if entry['BaseInstrument'] in ['KPF', 'KPF-CC']:
                print(entry['Date'], entry['ProjCode'], entry['Instrument'])
                if entry['ProjCode'] not in emails.keys():
                    semid = f"{semester}_{entry['ProjCode']}"
                    emails[semid] = [entry['PiEmail']]
                    COIs = query_observatoryAPI('proposals', 'getCOIs',
                                               {'semid': semid})
                    for COI in COIs['data']['COIs']:
                        emails[semid].append(COI['Email'])

    all_emails = []
    for ProjectCode in emails.keys():
        all_emails.extend(emails[ProjectCode])
    all_emails = list(set(all_emails))
    print()
    print(';'.join(all_emails))
