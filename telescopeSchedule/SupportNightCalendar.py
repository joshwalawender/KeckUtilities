#!/usr/env/python

## Import General Tools
import sys
import os
from argparse import ArgumentParser
import re
from datetime import datetime as dt
from datetime import timedelta as tdelta

import numpy as np
from astropy.table import Table, Column

from telescopeSchedule import *

##-------------------------------------------------------------------------
## ICS File Object
##-------------------------------------------------------------------------
class ICSFile(object):
    '''
    Class to represent an ICS calendar file.
    '''
    def __init__(self, filename):
        self.file = filename
        self.lines = ['BEGIN:VCALENDAR\n',
                      'PRODID:-//hacksw/handcal//NONSGML v1.0//EN\n',
                      '\n']


    def add_event(self, title, starttime, endtime, description, verbose=False):
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
                     'DESCRIPTION: {}\n'.format(description),
                     'END:VEVENT\n',
                     '\n',
                     ]
        self.lines.extend(new_lines)


    def write(self):
        self.lines.append('END:VCALENDAR\n')
        if os.path.exists(self.file): os.remove(self.file)
        with open(self.file, 'w') as FO:
            for line in self.lines:
                FO.write(line)
            


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

#     print(calc['seto'])
#     print(keck['seto'])
#     print(calc['riseo'])
#     print(keck['riseo'])

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


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():
    ##-------------------------------------------------------------------------
    ## Parse Command Line Arguments
    ##-------------------------------------------------------------------------
    ## create a parser object for understanding command-line arguments
    parser = ArgumentParser(
             description="Generates ICS file of support nights from telescope DB.")
    ## add arguments
#     parser.add_argument('-s', '--sa',
#         type=str, dest="sa", default='jwalawender',
#         help='SA name. Use enough to make a search unique for the "Alias".')
    parser.add_argument('-s', '--sa',
        type=str, dest="sa", help='SA alias.',
        choices=['jwalawender', 'arettura', 'calvarez', 'gdoppmann', 'jlyke',
                 'lrizzi', 'pgomez', 'randyc', 'syeh'])
    parser.add_argument('--sem', '--semester',
        type=str, dest="semester",
        help="Semester (e.g. '18B')")
    parser.add_argument('-b', '--begin',
        type=str, dest="begin", #widget='DateChooser',
        help="Start date in YYYY-mm-dd format.")
    parser.add_argument('-e', '--end',
        type=str, dest="end", #widget='DateChooser',
        help="End date in YYYY-mm-dd format.")
    args = parser.parse_args()

    ## Set start date
    if args.begin is not None:
        try:
            from_dto = dt.strptime(args.begin, '%Y-%m-%d')
        except:
            from_dto = dt.now()
    else:
        from_dto = dt.now()
    ## Determine ndays from args.end
    if args.end is not None:
        try:
            end_dto = dt.strptime(args.end, '%Y-%m-%d')
        except:
            pass
        else:
            delta = end_dto - from_dto
            ndays = delta.days + 1
    else:
        ndays = None
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

    print('Retrieving telescope schedule')
    from_date = from_dto.strftime('%Y-%m-%d')
    telsched = get_telsched(from_date=from_date, ndays=ndays)
    dates = sorted(set(telsched['Date']))
    ndays = len(dates)
    print(f"Retrieved schedule for {dates[0]} to {dates[-1]} ({ndays} days)")
    print(f"Retrieving SA schedule")
    telsched = add_SA_to_telsched(telsched)
    print('Done')

    ##-------------------------------------------------------------------------
    ## Create Output iCal File
    ##-------------------------------------------------------------------------
    ical_file = ICSFile('Nights.ics')
    month_night_count = {}
    month_nights = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
                    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
    dual_support_count = 0
    split_night_count = 0

    sasched = telsched[telsched['SA'] == args.sa.lower()]
    night_count = len(set(sasched['Date']))

    print('Building calendar')
    for date in sorted(set(sasched['Date'])):
        progs = sasched[sasched['Date'] == date]
        progsbytel = progs.group_by('TelNr')

        if len(progsbytel.groups) > 1:
            dual_support_count += 1

        print(f"  Creating calendar entry for {date}")
        month = date[:7]
        if month in month_night_count.keys():
            month_night_count[month] += 1
        else:
            month_night_count[month] = 1

        twilights = get_twilights(date)

        # Loop over both telNr if needed
        for idx in range(len(progsbytel.groups)):
            supporttype = 'Support'
            if len(progsbytel.groups[idx]) > 1:
                supporttype = 'Split Night'
                split_night_count += 1

            instruments = list(progsbytel.groups[idx]['Instrument'])
            if len(set(instruments)) == 1:
                title = f"{instruments[0]} {supporttype}"
            else:
                title = f"{'/'.join(instruments)} {supporttype}"
#             calstart = (twilights['seto']-tdelta(0,10*60*60)).strftime('%Y%m%dT%H%M00')
            calstart = f"{twilights['udate'].replace('-', '')}"\
                       f"T{twilights['sunset HST'].replace(':', '')}00"
            calend = f"{date.replace('-', '')}T230000"
            description = [title,
                           f"Sunset: {twilights['sunset']} UT",
                           f"12deg:  {twilights['dusk_12deg']} UT",
                           ]
            for entry in progsbytel.groups[idx]:
                obslist = entry['Observers'].split(',')
                loclist = entry['Location'].split(',')
                assert len(obslist) == len(loclist)
                observers = [f"{obs}({loclist[i]})" for i,obs in enumerate(obslist)]
                description.append('')
                description.append(f"Instrument: {entry['Instrument']} ({entry['Account']})")
                description.append(f"PI: {entry['Principal']}")
                description.append(f"Observers: {', '.join(observers)}")
                description.append(f"Start Time: {entry['StartTime']}")

            description.append('')
            description.append(f"12deg:  {twilights['dawn_12deg']} UT")
            description.append(f"Sunrise: {twilights['sunrise']} UT")

            ical_file.add_event(title, calstart, calend, description)

    ical_file.write()
    print(f"Found {night_count:d} / {ndays:d} nights ({100*night_count/ndays:.1f} %) where SA matches {args.sa:}")
    print(f"Found {split_night_count:d} split nights")

    for month in sorted(month_night_count.keys()):
        nsupport = month_night_count[month]
        nnights = month_nights[int(month[-2:])]
        print(f"  For {month}: {nsupport:2d} / {nnights:2d} nights ({100*nsupport/nnights:4.1f} %)")






#     for entry in telsched:
#         found = re.search(args.sa.lower(), entry['SA'].lower())
#         if found is not None:
#             night_count += 1
#             month = entry['Date'][:7]
#             if month in month_night_count.keys():
#                 month_night_count[month] += 1
#             else:
#                 month_night_count[month] = 1
#             supporttype = determine_type(entry, telsched, args)
#             if supporttype.find('Split Night') > 0:
#                 split_night_count += 1
#             title = '{} {} ({})'.format(entry['Instrument'], supporttype, entry['Location'])
#             twilight = parse_twilight(entry)
#             calend = '{}T{}'.format(entry['Date'].replace('-', ''), '230000')
#             description = [title,
#                            f"Sunset @ {twilight['sunsetstr']}",
#                            f"12 deg Twilight @ {twilight['dusk_12degstr']}",
#                            f"12 deg Twilight @ {twilight['dawn_12degstr']}",
#                            f"Sunrise @ {twilight['sunrisestr']}",
#                            f"PI: {entry['Principal']}",
#                            f"Observers: {entry['Observers']}",
#                            f"Location: {entry['Location']}",
#                            f"Account: {entry['InstrAcc']}",
#                            ]
#             print(f"{entry['Date']:10s} K{entry['TelNr']:d} {title:s}")
#             ical_file.add_event(title, twilight['sunset'].strftime('%Y%m%dT%H%M%S'),
#                                 calend, description)
#     ical_file.write()
#     print(f"Found {night_count:d} / {ndays:d} nights ({100*night_count/ndays:.1f} %) where SA matches {args.sa:}")
#     print(f"Found {split_night_count:d} split nights")
# 
#     for month in month_night_count:
#         nsupport = month_night_count[month]
#         nnights = month_nights[int(month[-2:])]
#         print(f"  For {month}: {nsupport:2d} / {nnights:2d} nights ({100*nsupport/nnights:4.1f} %)")


if __name__ == '__main__':
    main()


