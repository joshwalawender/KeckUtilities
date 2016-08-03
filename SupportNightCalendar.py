#!/usr/env/python

from __future__ import division, print_function

## Import General Tools
import sys
import os
import argparse
from datetime import datetime as dt

from astropy.table import Table

class ParseError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


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
    parser.add_argument('--sasched',
        type=str, dest="sasched",  default='sasched.csv',
        help="The csv file of the SA's duty nights.")
    parser.add_argument('-t', '--telsched',
        type=str, dest="telsched", default='telsched.csv',
        help="The csv file of the telescope schedule.")
    parser.add_argument('-s', '--start',
        type=str, dest="start", default='140000',
        help="Start time for calendar entry in HHMMSS or HHMM 24 hour format.")
    parser.add_argument('-e', '--end',
        type=str, dest="end", default='230000', 
        help="End time for calendar entry in HHMMSS or HHMM 24 hour format.")
    args = parser.parse_args()

    if len(args.start) == 4:
        start = args.start + '00'
    elif len(args.start) == 6:
        start = args.start
    else:
        raise ParseError('Could not parse start time: "{}"'.format(args.start))

    if len(args.end) == 4:
        end = args.end + '00'
    elif len(args.end) == 6:
        end = args.end
    else:
        raise ParseError('Could not parse end time: "{}"'.format(args.end))


    ##-------------------------------------------------------------------------
    ## Read in Telescope Schedule and SA Support Schedule
    ##-------------------------------------------------------------------------
    telsched = Table.read(args.telsched, format='ascii.csv', guess=False)
    assert '#' in telsched.keys()
    assert 'Date' in telsched.keys()
    assert 'Instrument' in telsched.keys()
    assert 'Principal' in telsched.keys()
    assert 'Observers' in telsched.keys()
    assert 'Location' in telsched.keys()
    sasched = Table.read(args.sasched, format='ascii.csv', guess=False)
    keys = sasched.keys()
    assert '#' in keys
    assert 'Date' in keys
    assert len(keys) == 3
    saname = keys.pop(-1)

    sasched = sasched[~sasched[saname].mask]
    type = {'K1': 'Support',
            'K1T': 'Training',
            'K1oc': 'On Call',
            'K2': 'Support',
            'K2T': 'Training',
            'K2oc': 'On Call',
            }

    ##-------------------------------------------------------------------------
    ## Create Output iCal File
    ##-------------------------------------------------------------------------
    ical_file = 'Nights.ics'
    if os.path.exists(ical_file): os.remove(ical_file)
    now = dt.utcnow()
    uid = now.strftime('%Y%m%dT%H%M%SZ')
    with open(ical_file, 'w') as FO:
        FO.write('BEGIN:VCALENDAR\n'.format())
        FO.write('PRODID:-//hacksw/handcal//NONSGML v1.0//EN\n'.format())
        for night in sasched:
            date = night['Date']
            tel = int(night[saname][1:2])
            entry = telsched[(telsched['Date'] == date) & (telsched['TelNr'] == tel)]
            assert len(entry) == 1
            
            FO.write('BEGIN:VEVENT\n')
            FO.write('UID:{}-{:04d}@kecksupportcalendar.com\n'.format(uid, entry['#'][0]))
            FO.write('DTSTAMP:{}\n'.format(uid))
            FO.write('DTSTART;TZID=Pacific/Honolulu:{}T140000\n'.format(
                     entry['Date'][0].replace('-', '')))
            FO.write('DTEND;TZID=Pacific/Honolulu:{}T230000\n'.format(
                     entry['Date'][0].replace('-', '')))
            FO.write('SUMMARY:{} {}\n'.format(entry['Instrument'][0], type[night[saname]]))
            FO.write('DESCRIPTION: PI: {}\\nObservers: {}\\nLocation: {}\n'.format(
                     entry['Principal'][0], entry['Observers'][0], entry['Location'][0]))
            FO.write('END:VEVENT\n')
        FO.write('END:VCALENDAR\n')


if __name__ == '__main__':
    main()
