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
def get_telsched(from_date=None, ndays=10):
    if from_date is None:
        now = dt.now()
        from_date = now.strftime('%y-%m-%d')
    else:
        assert dt.strptime(from_date, '%y-%m-%d')

    from_dto = dt.strptime(from_date, '%y-%m-%d')
    from_string = from_dto.strftime('%Y-%m-%d HST')
    to_dto = from_dto + tdelta(ndays)
    to_string = to_dto.strftime('%Y-%m-%d HST')
    print(f'Getting telescope schedule from {from_string} to {to_string}')

    address = f'http://www/observing/schedule/ws/telsched.php'\
              f'?date={from_date}&ndays={ndays:d}&field=all&verbosity=-1'
    r = requests.get(address)

    telsched_xml = ET.fromstring(r.text)
    keys = ['Date', 'InstrAcc', 'Instrument', 'Location', 'OA', 'Observers',
            'Principal', 'SA', 'TelNr', 'Twilight']
    telsched = Table(names=keys,
                     dtype=('a10', 'a30', 'a30', 'a30', 'a30', 'a50',
                            'a30', 'a30', 'i4', 'a200'))
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
        type = 'Support'
    elif len(yentry) == 1:
        SAmatch = re.search(args.sa.lower(), yentry['SA'][0].lower())
        PImatch = entry['Principal'] == yentry['Principal'][0]
        instmatch = entry['Instrument'] == yentry['Instrument'][0]
        if SAmatch and PImatch and instmatch:
            type = 'On Call'
        else:
            type = 'Support'
    else:
        print('Multiple entries for yesterday')
        type = 'Support'

    split = entry['Principal'].split('/')
    if len(split) > 1:
        type = f"{type}, Split Night ({len(split)}x)"

    return type


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():
    ##-------------------------------------------------------------------------
    ## Parse Command Line Arguments
    ##-------------------------------------------------------------------------
    ## create a parser object for understanding command-line arguments
    parser = argparse.ArgumentParser(
             description="Program description.")
    ## add arguments
    parser.add_argument('-s', '--sa',
        type=str, dest="sa", default='Josh',
        help="SA name. Use enough of the name to make a case insenstive string search unique.")
    parser.add_argument('-e', '--end',
        type=str, dest="end",
        help="End date in %Y-%m-%d format or S17B format.")
    args = parser.parse_args()
    ## Determine ndays from args.end
    if args.end:
        try:
            end_dto = dt.strptime(args.end, '%Y-%m-%d')
        except:
            pass
        else:
            today = dt.strptime(dt.now().strftime('%Y-%m-%d'), '%Y-%m-%d')
            delta = end_dto - today
            ndays = delta.days
    else:
        ndays = 180


    telsched = get_telsched(ndays=ndays)
    
    ##-------------------------------------------------------------------------
    ## Create Output iCal File
    ##-------------------------------------------------------------------------
    ical_file = ICSFile('Nights.ics')

    night_count = 0
    for entry in telsched:
        found = re.search(args.sa.lower(), entry['SA'].lower())
        if found:
            night_count += 1
            type = determine_type(entry, telsched, args)
            title = '{} {} ({})'.format(entry['Instrument'], type, entry['Location'])
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
    print(f"Found {night_count:d} nights where SA matches {args.sa:}")


if __name__ == '__main__':
    main()


