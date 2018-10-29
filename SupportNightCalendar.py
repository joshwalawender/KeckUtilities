#!/usr/env/python

## Import General Tools
import sys
import os
import argparse
import requests
from datetime import datetime as dt
from datetime import timedelta as tdelta
import re
import xml.etree.ElementTree as ET

from astropy.table import Table

from gooey import Gooey, GooeyParser

class ParseError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


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
## Get Telescope Schedule
##-------------------------------------------------------------------------
def get_telsched(from_date=None, ndays=None):
    # Set from date
    if from_date is None:
        now = dt.now()
        from_date = now.strftime('%Y-%m-%d')
    else:
        assert dt.strptime(from_date, '%Y-%m-%d')
    from_dto = dt.strptime(from_date, '%Y-%m-%d')
    from_string = from_dto.strftime('%Y-%m-%d HST')
    # Set to date
    if ndays is None:
        if from_dto.month == 1:
            to_dto = dt(from_dto.year, 2, 1)
        elif from_dto.month < 7:
            to_dto = dt(from_dto.year, 8, 1)
        elif from_dto.month <= 12:
            to_dto = dt(from_dto.year+1, 2, 1)
    else:
        to_dto = from_dto + tdelta(ndays)
    to_string = to_dto.strftime('%Y-%m-%d HST')
    ndays = (to_dto - from_dto).days + 1
    print(f'Getting telescope schedule from {from_string} to {to_string} ({ndays} days)')

    address = f'http://www/observing/schedule/ws/telsched.php'\
              f'?date={from_date}&ndays={ndays:d}&field=all&verbosity=-1'
    r = requests.get(address)

    telsched_xml = ET.fromstring(r.text)
    keys = ['Date', 'InstrAcc', 'Instrument', 'Location', 'OA', 'Observers',
            'Principal', 'SA', 'TelNr', 'Twilight']
    telsched = Table(names=keys,
                     dtype=('a10', 'a30', 'a30', 'a30', 'a30', 'a100',
                            'a50', 'a30', 'i4', 'a200'))
    for i,item in enumerate(telsched_xml.iter('item')):
        entry = {}
        for el in item:
            if el.tag in keys:
                entry[el.tag] = el.text
        telsched.add_row(entry)
    return telsched


def parse_twilight(entry):
    twistring = entry['Twilight']
    datestr = entry['Date']
    twilist = twistring.strip('{').strip('}').split(',')
    twilight = {}
    for x in twilist:
        match = re.match("^(\w+)\:'([\w:\-]+)'", x)
        if match:
            if match.group(1) == 'sunset':
                str = '{} {}'.format(entry['Date'], match.group(2))
                twilight['sunset'] = dt.strptime(str, '%Y-%m-%d %H:%M:%S') +\
                                     tdelta(1, -10*60*60)
                twilight['sunsetstr'] = twilight['sunset'].strftime('%H:%M')
            if match.group(1) == 'sunrise':
                str = '{} {}'.format(entry['Date'], match.group(2))
                twilight['sunrise'] = dt.strptime(str, '%Y-%m-%d %H:%M:%S') +\
                                     tdelta(1, -10*60*60)
                twilight['sunrisestr'] = twilight['sunrise'].strftime('%H:%M')
            if match.group(1) == 'dusk_12deg':
                str = '{} {}'.format(entry['Date'], match.group(2))
                twilight['dusk_12deg'] = dt.strptime(str, '%Y-%m-%d %H:%M:%S') +\
                                     tdelta(1, -10*60*60)
                twilight['dusk_12degstr'] = twilight['dusk_12deg'].strftime('%H:%M')
            if match.group(1) == 'dawn_12deg':
                str = '{} {}'.format(entry['Date'], match.group(2))
                twilight['dawn_12deg'] = dt.strptime(str, '%Y-%m-%d %H:%M:%S') +\
                                     tdelta(1, -10*60*60)
                twilight['dawn_12degstr'] = twilight['dawn_12deg'].strftime('%H:%M')


    return twilight

##-------------------------------------------------------------------------
## Check On Call
##-------------------------------------------------------------------------
def determine_type(entry, telsched, args):
    '''
    Given an entry (a single row of a telsched table), check to see if the
    previous night on the same telescope has the same PI string.  If so, the
    night is "On Call" instead of "Support".
    '''
    date = dt.strptime(entry['Date'], '%Y-%m-%d')
    yesterday = (date-tdelta(1)).strftime('%Y-%m-%d')
    ysched = telsched[telsched['Date'] == yesterday]
    yentry = ysched[ysched['TelNr'] == entry['TelNr']]
    if len(yentry) == 0:
        supporttype = 'Support'
    elif len(yentry) == 1:
        SAmatch = re.search(args.sa.lower(), yentry['SA'][0].lower())
        PImatch = entry['Principal'] == yentry['Principal'][0]
        instmatch = entry['Instrument'] == yentry['Instrument'][0]
        if SAmatch and PImatch and instmatch:
            supporttype = 'On Call'
        else:
            supporttype = 'Support'
    else:
        print('Multiple entries for yesterday')
        supporttype = 'Support'

    split = entry['Principal'].split('/')
    if len(split) > 1:
        supporttype = f"{supporttype}, Split Night ({len(split)}x)"

    return supporttype


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
@Gooey
def main():
    ##-------------------------------------------------------------------------
    ## Parse Command Line Arguments
    ##-------------------------------------------------------------------------
    ## create a parser object for understanding command-line arguments
    parser = GooeyParser(
             description="Generates ICS file of support nights from telescope DB.")
    ## add arguments
    parser.add_argument('-s', '--sa',
        type=str, dest="sa", default='Josh',
        help="SA name. Use enough to make a search unique.")
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

    from_date = from_dto.strftime('%Y-%m-%d')
    telsched = get_telsched(from_date=from_date, ndays=ndays)
    ndays = int(len(telsched)/2)


    ##-------------------------------------------------------------------------
    ## Create Output iCal File
    ##-------------------------------------------------------------------------
    ical_file = ICSFile('Nights.ics')
    month_night_count = {}
    month_nights = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
                    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
    night_count = 0
    for entry in telsched:
        found = re.search(args.sa.lower(), entry['SA'].lower())
        if found is not None:
            night_count += 1
            month = entry['Date'][:7]
            if month in month_night_count.keys():
                month_night_count[month] += 1
            else:
                month_night_count[month] = 1
            supporttype = determine_type(entry, telsched, args)
            title = '{} {} ({})'.format(entry['Instrument'], supporttype, entry['Location'])
            twilight = parse_twilight(entry)
            calend = '{}T{}'.format(entry['Date'].replace('-', ''), '230000')
            description = [title,
                           f"Sunset @ {twilight['sunsetstr']}",
                           f"12 deg Twilight @ {twilight['dusk_12degstr']}",
                           f"12 deg Twilight @ {twilight['dawn_12degstr']}",
                           f"Sunrise @ {twilight['sunrisestr']}",
                           f"PI: {entry['Principal']}",
                           f"Observers: {entry['Observers']}",
                           f"Location: {entry['Location']}",
                           f"Account: {entry['InstrAcc']}",
                           ]
            print(f"{entry['Date']:10s} K{entry['TelNr']:d} {title:s}")
            ical_file.add_event(title, twilight['sunset'].strftime('%Y%m%dT%H%M%S'),
                                calend, description)
    ical_file.write()
    print(f"Found {night_count:d} / {ndays:d} nights ({100*night_count/ndays:.1f} %) where SA matches {args.sa:}")

    for month in month_night_count:
        nsupport = month_night_count[month]
        nnights = month_nights[int(month[-2:])]
        print(f"  For {month}: {nsupport:2d} / {nnights:2d} nights ({100*nsupport/nnights:4.1f} %)")


if __name__ == '__main__':
    main()


