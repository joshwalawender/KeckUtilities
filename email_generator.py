#!/usr/env/python

## Import General Tools
import argparse
import datetime

from utils.observatoryAPIs import *


##-------------------------------------------------------------------------
## Parse Command Line Arguments
##-------------------------------------------------------------------------
## create a parser object for understanding command-line arguments
p = argparse.ArgumentParser(description='''
''')
## add options
p.add_argument("-d", "--date", dest="date", type=str, default=None,
    help="Date of the observing night (in YYYY-mm-dd format).")
p.add_argument("--sa", dest="sa", type=str, default='jwalawender',
    help="SA name. Will grab list of observers from that's SA support run.")
args = p.parse_args()


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


def form_emails_for_date(date, telnr):
    schedule = getSchedule(date=date, numdays=1, telnr=telnr)
    print(f"# Found {len(schedule)} programs for {date} on K{telnr}:")
    for entry in schedule:
        observerIDs = entry['ObsId'].split(',')
        email_addresses = []
        observer_names = []
        for observerID in observerIDs:
            obs = getObserverInfo(observerID)[0]
            observer_names.append(f"{obs['FirstName']} {obs['LastName']}")
            email_addresses.append(obs['Email'])
        print(f'Instrument: {entry["Instrument"]}')
        print()
        print(f'Email To:')
        print(', '.join(email_addresses))
        print('; '.join(email_addresses))
        print()
        print('Subject:')
        print(f"Keck {entry['BaseInstrument']} observing on {date}")
        print()

        email = f"Aloha {', '.join(observer_names)},\n\n"
        email += f"I'll be supporting your {entry['BaseInstrument']} "
        email += f"time on Keck {entry['TelNr']} on {date}. "
        email += "Please let me know if you have any questions "
        email += "prior to your run. "
        if 'HQ' in entry['Location']:
            email += "It looks like you'll be observing from Keck "
            email += "HQ in Waimea, feel free to stop by my "
            email += "office anytime if you have questions. "
        email += "Please also let me know when you'd like to meet "
        email += "up in the afternoon to start setup and cals.\n\n"
        email += "cheers,\n"
        email += "Josh\n"
        print(email)
        print('##################################################')


def main():
    if args.date is not None:
        start_date = args.date
    nights = get_nights_for_SA(start_date=None, numdays=7, sa=args.sa)
    for date, telnr in nights:
        form_emails_for_date(date, telnr)


if __name__ == '__main__':
    main()
