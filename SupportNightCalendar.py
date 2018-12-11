#!/usr/env/python

## Import General Tools
import sys
import os
from gooey import Gooey, GooeyParser
import requests
import json
import re
from datetime import datetime as dt
from datetime import timedelta as tdelta
from astropy.table import Table, Column


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
def querydb(req):
    url = f"https://www.keck.hawaii.edu/software/db_api/telSchedule.php?{req}"
    r = requests.get(url)
    return json.loads(r.text)


def get_SA(date=None, tel=1):
    if date is None:
        return None
    req = f"cmd=getNightStaff&date={date}&type=sa&telnr={tel}"
    try:
        sa = querydb(req)[0]['Alias']
    except:
        sa= ''
    return sa


def get_telsched(from_date=None, ndays=None):
    if from_date is None:
        now = dt.now()
        from_date = now.strftime('%Y-%m-%d')
    else:
        assert dt.strptime(from_date, '%Y-%m-%d')

    req = f"cmd=getSchedule&date={from_date}"
    if ndays is not None:
        req += f"&numdays={ndays}"
    telsched = Table(data=querydb(req))
    telsched = add_SA_to_telsched(telsched)
    return telsched


def add_SA_to_telsched(telsched):
    sas = [get_SA(date=x['Date'], tel=x['TelNr']) for x in telsched]
    telsched.add_column(Column(sas, name='SA'))
    return telsched


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
#     parser.add_argument('-s', '--sa',
#         type=str, dest="sa", default='jwalawender',
#         help='SA name. Use enough to make a search unique for the "Alias".')
    parser.add_argument('-s', '--sa',
        type=str, dest="sa", help='SA alias.', widget='Dropdown',
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

    from_date = from_dto.strftime('%Y-%m-%d')
    telsched = get_telsched(from_date=from_date, ndays=ndays)
    dates = sorted(set(telsched['Date']))
    ndays = len(dates)
    print(f"Retrieved schedule for {dates[0]} to {dates[-1]} ({ndays} days)")

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

    for date in set(sasched['Date']):
        progs = sasched[sasched['Date'] == date]
        progsbytel = progs.group_by('TelNr')

        if len(progsbytel.groups) > 1:
            dual_support_count += 1

        month = date[:7]
        if month in month_night_count.keys():
            month_night_count[month] += 1
        else:
            month_night_count[month] = 1

        # Loop over both telNr if needed
        for idx in range(len(progsbytel.groups)):
            supporttype = 'Support'
            if len(progsbytel.groups[idx]) > 1:
                supporttype = 'Split Night'
                split_night_count += 1

            instruments = list(progsbytel.groups[idx]['Instrument'])
            loc = '?'
            title = f"{'/'.join(instruments)} {supporttype} ({loc})"
            calstart = f"{date.replace('-', '')}T170000"
            calend = f"{date.replace('-', '')}T230000"
            description = [title]
            for entry in progsbytel.groups[idx]:
                description.append('')
                description.append(f"Start Time: {entry['StartTime']}")
                description.append(f"PI: {entry['Principal']}")
                description.append(f"Observers: {entry['Observers']}")
#                 description.append(f"Location: {entry['Location']}")
                description.append(f"Account: {entry['Account']}")

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


