#!/usr/env/python

## Import General Tools
from pathlib import Path
from argparse import ArgumentParser
import re
import datetime
import numpy as np

from utils.observatoryAPIs import *


zoomnrs = {1: 'https://keckobservatory.zoom.us/j/8088813714?pwd=eGM3aDhlMHdKd1F0LzY4N2kzSjhJdz09',
           2: 'https://keckobservatory.zoom.us/j/8088813729?pwd=WFJWTGk5cm4xeVlQdXdhWUZsZVdnQT09'}


##-------------------------------------------------------------------------
## Parse Command Line Arguments
##-------------------------------------------------------------------------
## create a parser object for understanding command-line arguments
parser = ArgumentParser(
         description="Generates ICS file of support nights from telescope DB.")
## add arguments
parser.add_argument('-s', '--sa',
    type=str, dest="sa", help='SA alias.',
    default='jwalawender')
parser.add_argument('--sem', '--semester',
    type=str, dest="semester",
    help="Semester (e.g. '18B')")
parser.add_argument('--start',
    type=str, dest="start", default='',
    help="Start date (e.g. 2021-08-01)")
parser.add_argument('--end',
    type=str, dest="end", default='',
    help="End date (e.g. 2021-09-01)")
parser.add_argument('--calend',
    type=int, dest="calend",
    default='2359',
    help="End time of calendar entry in 24 hour format (e.g. 2359)")
args = parser.parse_args()


##-------------------------------------------------------------------------
## ICS File Object
##-------------------------------------------------------------------------
class ICSFile(object):
    '''
    Class to represent an ICS calendar file.
    '''
    def __init__(self, filename):
        self.file = Path(filename)
        self.lines = ['BEGIN:VCALENDAR\n',
                      'PRODID:-//hacksw/handcal//NONSGML v1.0//EN\n',
                      '\n']


    def add_event(self, title, starttime, endtime, description,
                  location='', alarm=15, support=False,
                  verbose=False):
        assert type(title) is str
        assert type(starttime) in [datetime.datetime, str]
        assert type(endtime) in [datetime.datetime, str]
        assert type(description) in [list, str]
        now = datetime.datetime.utcnow()
        try:
            starttime = starttime.strftime('%Y%m%dT%H%M%S')
        except:
            pass
        try:
            endtime = endtime.strftime('%Y%m%dT%H%M%S')
        except:
            pass
        if verbose:
            print('{} {}'.format(starttime[0:8], title))
        if type(description) is list:
            description = '\\n'.join(description)
        new_lines = ['BEGIN:VEVENT\n',
                     'UID:{}@mycalendar.com\n'.format(now.strftime('%Y%m%dT%H%M%S.%fZ')),
                     'DTSTAMP:{}\n'.format(now.strftime('%Y%m%dT%H%M%SZ')),
                     'DTSTART;TZID=Pacific/Honolulu:{}\n'.format(starttime),
                     'DTEND;TZID=Pacific/Honolulu:{}\n'.format(endtime),
                     'SUMMARY:{}\n'.format(title),
                     'LOCATION:{}\n'.format(location),
                     'DESCRIPTION: {}\n'.format(description),
                     ]
        if alarm is not None:
            new_lines.extend( ['BEGIN:VALARM\n',
                               f'TRIGGER:-PT{int(alarm):d}M\n',
                               'ACTION:DISPLAY\n',
                               'DESCRIPTION:Reminder\n',
                               'END:VALARM\n',
                               ] )
        if support is True:
            new_lines.append(f'CATEGORIES:Support\n')
        new_lines.extend( ['END:VEVENT\n', '\n' ] )

        self.lines.extend(new_lines)


    def write(self):
        self.lines.append('END:VCALENDAR\n')
        if self.file.expanduser().exists():
            os.remove(self.file.expanduser())
        self.file.write_text(''.join(self.lines))


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():
    # Get start and end times for scheduled query
    if args.semester is not None:
        try:
            matched = re.match('S?(\d\d)([AB])', args.semester)
            if matched is not None:
                year = int(f"20{matched.group(1)}")
                if matched.group(2) == 'A':
                    from_dto = datetime.datetime(year, 2, 1)
                    end_dto = datetime.datetime(year, 7, 31)
                else:
                    from_dto = datetime.datetime(year, 8, 1)
                    end_dto = datetime.datetime(year+1, 1, 31)
        except Exception as e:
            print(f'Could not parse {args.semester}')
            print(e)
            return
    elif args.start != '' and args.end != '':
        from_dto = datetime.datetime.strptime(args.start, '%Y-%m-%d')
        end_dto = datetime.datetime.strptime(args.end, '%Y-%m-%d')
    else:
        # Assume rest of this semester
        from_dto = datetime.datetime.now()
        semester, semstart, end_dto = get_semester_dates(from_dto)
    delta = end_dto - from_dto
    ndays = delta.days + 1

    # Get support nights for this SA
    nights = get_nights_for_SA(start_date=None, numdays=ndays, sa=args.sa)

    ## Create Output iCal Files
    ical_file = ICSFile('SupportNights.ics')
    afternoon_ical_file = ICSFile('SupportAfternoons.ics')

    night_count_by_month = {}
    instrument_list = {}
    split_night_count = 0
    ##-------------------------------------------------------------------------
    ## Iterate over nights and create calendar entries
    ##-------------------------------------------------------------------------
    for date, telnr in nights:
        cancelled = getCancelledStatus(date)
        if cancelled[f'K{telnr}'] != True:
            schedule = getSchedule(date=date, numdays=1, telnr=telnr)
            print(f"Found {len(schedule)} programs on {date} on K{telnr}")
            twilights = getTwilights(date)
            # In Keck API time is UT
            h, m = twilights['sunset'].split(':')
            twilights['sunset HST'] = f"{int(h)+14:02d}:{m}" # correct to HST

            # Add to support statistics
            month = date[:7]
            if month not in night_count_by_month.keys():
                night_count_by_month[month] = 0
            night_count_by_month[month] += 1
            if len(schedule) > 1:
                split_night_count += 1

            # Build Title for calendar entry
            supporttype = 'Support' if len(schedule) == 1 else "Split Night Support"
            instruments = [entry['Instrument'] for entry in schedule]
            if len(set(instruments)) == 1:
                caltitle = f"{instruments[0]} {supporttype}"
            else:
                caltitle = f"{'/'.join(instruments)} {supporttype}"
#             print(caltitle)
            # Build description text for calendar entry
            description = [f"Sunset: {twilights['sunset']} UT",
                           f"12deg:  {twilights['dusk_12deg']} UT",
                           f"18deg:  {twilights['dusk_18deg']} UT",
                           f"SA: {args.sa}",
                           ]
            for entry in schedule:
                if entry['Instrument'] not in instrument_list.keys():
                    # Whole Nights, Partial Nights
                    instrument_list[entry['Instrument']] = [0, 0]
                if entry["FractionOfNight"] == 1:
                    instrument_list[entry['Instrument']][0] += 1
                else:
                    instrument_list[entry['Instrument']][1] += 1

                obslist = entry['Observers'].split(',')
                loclist = entry['Location'].split(',')
                try:
                    observers = [f"{obs}({loclist[i]})" for i,obs in enumerate(obslist)]
                except:
                    observers = f"{obslist} / {loclist}"
                description.append('')
                description.append(f"Account: {entry['Account']}")
                description.append(f"PI: {entry['Principal']}")
                description.append(f"Observers: {', '.join(observers)}")
                description.append(f"Start Time: {entry['StartTime']}")
            description.append('')
            description.append(f"18deg:  {twilights['dawn_18deg']} UT")
            description.append(f"12deg:  {twilights['dawn_12deg']} UT")
            description.append(f"Sunrise: {twilights['sunrise']} UT")
            description.append('----')
            description.append('Generated by SupportNightCalendar.py')

            # Add afternoon support entry
            inst_is_KPF = ['KPF' in iname for iname in instruments]
            if np.all(inst_is_KPF) == False:
                afternoon_ical_file.add_event(f'Afternoon Support',
                                              f"{date.replace('-', '')}T150000",
                                              f"{date.replace('-', '')}T170000",
                                              description,
                                              location=zoomnrs[telnr])
            # Add night support entry
            calstart = f"{twilights['udate'].replace('-', '')}"\
                       f"T{twilights['sunset HST'].replace(':', '')}00"
            calend = f"{date.replace('-', '')}T{args.calend:04d}00"
            ical_file.add_event(caltitle, calstart, calend, description,
                                location=zoomnrs[telnr], support=True)

    ical_file.write()
    afternoon_ical_file.write()

    # Print summary to screen
    night_count = len(nights)
    print()
    print(f"Found {night_count:d} / {ndays:d} nights ({100*night_count/ndays:.1f} %) where SA matches {args.sa:}")
    print(f"Found {split_night_count:d} split nights")

    print("Monthly distribution:")
    nights_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    for key in night_count_by_month.keys():
        nsupport = night_count_by_month[key]
        monthint = int(key[5:])
        nnights = nights_per_month[monthint-1]
        frac = 100*nsupport/nnights
        if nsupport > 0:
            print(f"  For {key}: {nsupport:2d} / {nnights:2d} nights ({frac:4.1f} %)")

    print("Instrument distribution:")
    for instrument in sorted(instrument_list.keys()):
        Nwhole = instrument_list[instrument][0]
        Npartial = instrument_list[instrument][1]
        print(f"  {instrument:10s}: {Nwhole+Npartial:2d} nights ({Nwhole} whole nights, {Npartial} partial nights)")


if __name__ == '__main__':
    main()


