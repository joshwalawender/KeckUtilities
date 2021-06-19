#!/usr/env/python

## Import General Tools
import sys
from pathlib import Path
from argparse import ArgumentParser
import re
from datetime import datetime as dt
from datetime import timedelta as tdelta

import numpy as np
from astropy.table import Table, Column, Row

from telescopeSchedule.telescopeSchedule import *


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
parser.add_argument('--calend',
    type=int, dest="calend",
    default='2359',
    help="End time of calendar entry in 24 hour format (e.g. 2359)")
parser.add_argument('-f', '--file',
    type=str, dest="file",
    default='Nights.ics',
    help="Filename (including path if desired) to write to")
parser.add_argument('--telfile',
    type=str, dest="telfile",
    default='KeckSchedule.ics',
    help="Filename for Keck Schedule")
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
        assert type(starttime) in [dt, str]
        assert type(endtime) in [dt, str]
        assert type(description) in [list, str]
        now = dt.utcnow()
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
## Get Twilight Info for Date
##-------------------------------------------------------------------------
def calculate_twilights(date):
    """ Determine sunrise and sunset times """

    from astropy import units as u
    from astropy.time import Time
    from astropy.coordinates import EarthLocation
    from astroplan import Observer

    h = 4.2*u.km
    R = (1.0*u.earthRad).to(u.km)
    d = np.sqrt(h*(2*R+h))
    phi = (np.arccos((d/R).value)*u.radian).to(u.deg)
    MK = phi - 90*u.deg

    location = EarthLocation(
        lat=19+49/60+33.40757/60**2,
        lon=-(155+28/60+28.98665/60**2),
        height=4159.58,
    )
    obs = Observer(location=location, name='Keck', timezone='US/Hawaii')
    date = Time(dt.strptime(f'{date} 18:00:00', '%Y-%m-%d %H:%M:%S'))

    t = {}
    sunset = obs.sun_set_time(date, which='nearest', horizon=MK).datetime
    t['seto'] = sunset
    t['ento'] = obs.twilight_evening_nautical(Time(sunset), which='next').datetime
    t['eato'] = obs.twilight_evening_astronomical(Time(sunset), which='next').datetime
    t['mato'] = obs.twilight_morning_astronomical(Time(sunset), which='next').datetime
    t['mnto'] = obs.twilight_morning_nautical(Time(sunset), which='next').datetime
    t['riseo'] = obs.sun_rise_time(Time(sunset), which='next').datetime
    t['set'] = t['seto'].strftime('%H:%M UT')
    t['ent'] = t['ento'].strftime('%H:%M UT')
    t['eat'] = t['eato'].strftime('%H:%M UT')
    t['mat'] = t['mato'].strftime('%H:%M UT')
    t['mnt'] = t['mnto'].strftime('%H:%M UT')
    t['rise'] = t['riseo'].strftime('%H:%M UT')

    return t


def get_twilights(date):
    """ Get twilight times from Keck API """
    url = f"https://www.keck.hawaii.edu/software/db_api/metrics.php?date={date}"
    r = requests.get(url)
    result = json.loads(r.text)
    assert len(result) == 1
    t = result[0]

    # In Keck API, date is HST, but time is UT (ugh!)
    h, m = t['sunset'].split(':')
    t['sunset HST'] = f"{int(h)+14:02d}:{m}" # correct to HST
    
    t['seto'] = dt.strptime(f"{t['udate']} {t['sunset HST']}", '%Y-%m-%d %H:%M')
    t['seto'] += tdelta(0,10*60*60) # correct to UT
    t['riseo'] = dt.strptime(f"{t['udate']} {t['sunrise']}", '%Y-%m-%d %H:%M')
    t['riseo'] += tdelta(0,24*60*60) # correct to UT

    return t


def compare_twilights_on(date):
    calc = calculate_twilights(date)
    keck = get_twilights(date)
    diff = [(calc['seto'] - keck['seto']).total_seconds()/60,
            (calc['riseo'] - keck['riseo']).total_seconds()/60,
            ]
    diff.append(diff[1]-diff[0]) # add extra night duration in calc

    return diff


def compare_twilights():
    date = dt.strptime(f'2018-08-01 18:00:00', '%Y-%m-%d %H:%M:%S')
    enddate = dt.strptime(f'2019-02-01 18:00:00', '%Y-%m-%d %H:%M:%S')
    while date < enddate:
        datestr = date.strftime('%Y-%m-%d')
        diff = compare_twilights_on(datestr)
        print(f"{date}: {diff[0]:+5.1f}, {diff[1]:+5.1f}, {diff[2]:+5.1f}")
        date += tdelta(0,24*60*60)


def build_cal_info(date, entries):
    twilights = get_twilights(date)
    assert len(set(entries['SA'])) == 1
    entries.sort('StartTime')

    supporttype = 'Support' if len(entries) == 1 else "Split Night Support"

    if len(set(entries['Instrument'])) == 1:
        title = f"{entries['Instrument'][0]} {supporttype}"
        if entries['Principal'][0].strip() == 'Shutdown'\
           or entries['PiLastName'][0].strip() == 'Shutdown':
            title = 'Shutdown'
    else:
        title = f"{'/'.join(entries['Instrument'])} {supporttype}"

    description = [f"Sunset: {twilights['sunset']} UT",
                   f"12deg:  {twilights['dusk_12deg']} UT",
                   f"18deg:  {twilights['dusk_18deg']} UT",
                   f"SA: {entries['SA'][0]}",
                   ]

    for entry in entries:
        obslist = entry['Observers'].split(',')
        loclist = entry['Location'].split(',')
        assert len(obslist) == len(loclist)
        observers = [f"{obs}({loclist[i]})" for i,obs in enumerate(obslist)]
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

    return title, description


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():
    ## If semester is set, use that for start and end dates
    if args.semester is not None:
        try:
            matched = re.match('S?(\d\d)([AB])', args.semester)
            if matched is not None:
                year = int(f"20{matched.group(1)}")
                if matched.group(2) == 'A':
                    from_dto = dt(year, 2, 1)
                    end_dto = dt(year, 7, 31)
                else:
                    from_dto = dt(year, 8, 1)
                    end_dto = dt(year+1, 1, 31)
                delta = end_dto - from_dto
                ndays = delta.days + 1
        except:
            pass
    ## If semester is not set, pull from today through the current semester
    else:
        from_dto = dt.now()
        if from_dto.month > 1 and from_dto.month <= 7:
            ## We are in semester A
            end_dto = dt(from_dto.year, 7, 31)
        else:
            end_dto = dt(from_dto.year+1, 1, 31)
        delta = end_dto - from_dto
        ndays = delta.days + 1

    print('Retrieving telescope schedule')
    from_date = from_dto.strftime('%Y-%m-%d')
    telsched = get_telsched(from_date=from_date, ndays=ndays)
    dates = sorted(set(telsched['Date']))
    ndays = len(dates)
    print(f"Retrieved schedule for {dates[0]} to {dates[-1]} ({ndays} days)")
    print(f"Retrieving SA schedule")
    telsched = add_SA_to_telsched(telsched)

    month_night_count = {}
    month_nights = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
                    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
    split_night_count = 0

    ##-------------------------------------------------------------------------
    ## Create Output iCal Files
    ##-------------------------------------------------------------------------
    ical_file = ICSFile(args.file)
    afternoon_ical_file = ICSFile(args.file.replace('.ics', '_afternoon.ics'))
    tel_sched_file = ICSFile(args.telfile) if args.telfile != '' else None

    print('Building calendars')
    for date in sorted(set(telsched['Date'])):
        month = date[:7]
        this_date = telsched[telsched['Date'] == date]
        twilights = get_twilights(date)

        group_by_tel = this_date.group_by('TelNr')
        for group in group_by_tel.groups:
            TelNr = int(group['TelNr'][0])
            title, description = build_cal_info(date, group)

            # Add telescope schedule entry
            if tel_sched_file is not None:
#                 print(f'Generating telescope schedule entry for {date} on K{TelNr}')
                telcal_title = f"K{TelNr}: {title.split()[0]}"
                telcal_start = f"VALUE=DATE:{date.replace('-', '')}"
                telcal_end = f"VALUE=DATE:{date.replace('-', '')}"
                tel_sched_file.add_event(telcal_title, telcal_start, telcal_end,
                                         description, alarm=None)

            if args.sa.lower() in group['SA']:
#                 print(f'Generating SA schedule entry for {date} on K{TelNr}')
                if month in month_night_count.keys():
                    month_night_count[month] += 1
                else:
                    month_night_count[month] = 1
                if len(group) > 1:
                    split_night_count += 1

                # Add afternoon support entry
                afternoon_ical_file.add_event(f'Afternoon Support',
                                              f"{date.replace('-', '')}T150000",
                                              f"{date.replace('-', '')}T170000",
                                              description,
                                              location=zoomnrs[TelNr])
                # Add night support entry
                calstart = f"{twilights['udate'].replace('-', '')}"\
                           f"T{twilights['sunset HST'].replace(':', '')}00"
                calend = f"{date.replace('-', '')}T{args.calend:04d}00"
                ical_file.add_event(title, calstart, calend, description,
                                    location=zoomnrs[TelNr], support=True)

    ical_file.write()
    afternoon_ical_file.write()
    if tel_sched_file is not None: tel_sched_file.write()

    # Print summary to screen
    sasched = telsched[telsched['SA'] == args.sa.lower()]
    night_count = len(set(sasched['Date']))
    print(f"Found {night_count:d} / {ndays:d} nights ({100*night_count/ndays:.1f} %) where SA matches {args.sa:}")
    print(f"Found {split_night_count:d} split nights")

    for month in sorted(month_night_count.keys()):
        nsupport = month_night_count[month]
        nnights = month_nights[int(month[-2:])]
        print(f"  For {month}: {nsupport:2d} / {nnights:2d} nights ({100*nsupport/nnights:4.1f} %)")

    byinst = sasched.group_by('Instrument')
    inst_nights = Table(names=('Instrument', 'NightCount'), dtype=('a12', 'i4'))
    for group in byinst.groups:
        inst_nights.add_row({'Instrument': group['Instrument'][0],
                             'NightCount': len(group)})
    inst_nights.sort(keys=['NightCount'])
    inst_nights.reverse()
    print(inst_nights)


if __name__ == '__main__':
    main()


