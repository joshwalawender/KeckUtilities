# KeckUtilities

A few utility scripts for use at Keck Observatory.

## SupportNightCalendar.py

Used to generate an ICS file (for use in typical calendar applications) of support nights.

To use, clone this repository to your machine:
```
git clone https://github.com/joshwalawender/KeckUtilities.git
```

Then `cd` in to the resulting `KeckUtilities` directory and run:
```
python SupportNightCalendar.py --end 2018-01-31 --sa Josh
```

The program will generate a `Nights.ics` file in that directory which can then be imported by typical calendar applications.

The `--end 2018-01-31` option tells the program to look at the schedule from today until that end date (the end of S17B in this example) and generate calendar entries for that time period.

The `--sa Josh` option means that the program will search (in a case insensitive manner) for the string 'Josh' in the SA field in the database.  You only have to include enough of the SA's name to make it unique.

Each calendar entry will run from sunset until 11pm (a somewhat arbitrary end time).  The title will show what instrument, whether it is regular support or on call, and the location of the observers.  For example, for K1 on 2017-07-30 the calendar entry title is: `MOSFIRE Support (HQ)`.  The calendar entry notes will include information on the twilight times, PI, observers, location, and account.  For example, for K1 on 2017-07-30 the calendar entry notes are:

```
Sunset @ 19:10
12 deg Twilight @ 19:51
12 deg Twilight @ 05:06
Sunrise @ 05:47
PI: Nakajima
Observers: Fletcher; Ellis; Nakajima; Iwata
Location: HQ
Account: MOSFIRE(4)
```

### Example ICS Entry

    BEGIN:VEVENT
    UID:20160803T215325Z-0011@kecksupportcalendar.com
    DTSTAMP:20160803T215325Z
    DTSTART;TZID=Pacific/Honolulu:20160806T140000
    DTEND;TZID=Pacific/Honolulu:20160806T230000
    SUMMARY:HIRESr Support
    DESCRIPTION: PI: Matsuno\nObservers: Matsuno, Aoki\nLocation: HQ
    END:VEVENT
    

## KeckStarList.py

Some minor utilities for reading star lists.
