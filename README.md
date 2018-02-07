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
python SupportNightCalendar.py
```

If your system is a conda build or if it complains: "This program needs access to the screen" then you can either run in command line mode using the `--ignore-gooey` option or you can run it using:

`pythonw SupportNightCalendar.py`

which you can install via `conda install python.app` if you have conda.

The program will generate a `Nights.ics` file in that directory which can then be imported by typical calendar applications.  Each calendar entry will run from sunset until 11pm (a somewhat arbitrary end time).  The title will show what instrument, whether it is regular support or on call, and the location of the observers.  For example, for K1 on 2017-07-30 the calendar entry title is: `MOSFIRE Support (HQ)`.  The calendar entry notes will include information on the twilight times, PI, observers, location, and account.  For example, for K1 on 2017-07-30 the calendar entry notes are:

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

### Options

`--sa Josh`: Means that the program will search (in a case insensitive manner) for the string 'Josh' in the SA field in the database.  You only have to include enough of the SA's name to make it unique.

`--semester 18A` or `--sem 18A`: Tells the program to look at the specified semester.  This overrides the `--start` and `--end` options below.

`--begin 2018-01-01`: Tells the program to look at the schedule from the date indicated until the end of that semester (ending on  the next instance of Jan 31 or July 31).  Defaults to today.

`--end 2018-01-31`: Tells the program to look at the schedule until that end date (the end of S17B in this example) and generate calendar entries for that time period.

### Example ICS Entry

```
BEGIN:VEVENT
UID:20160803T215325Z-0011@kecksupportcalendar.com
DTSTAMP:20160803T215325Z
DTSTART;TZID=Pacific/Honolulu:20160806T140000
DTEND;TZID=Pacific/Honolulu:20160806T230000
SUMMARY:HIRESr Support
DESCRIPTION: PI: Matsuno\nObservers: Matsuno, Aoki\nLocation: HQ
END:VEVENT
```

## horizons2starlist.py

A python script to query an object name and return a Keck formatted starlist for a range of dates with the appropriate tracking rate corrections.

This script requires the (callhorizons)[https://github.com/mommermi/callhorizons] package which can be obtained from GitHub at that link or installed via `pip install callhorizons`.

Once `callhorizons` is installed, you can get starlist entries for an objecy (e.g. for "C/2016 R2") by invoking:

`python horizons2starlist.py "C/2016 R2"`

This will get the coordinates for the next 24 hours (if the target is up) spaced every hour.  An example of the output looks like:

```
# Target C2016_R2 is down at 1906
C2016_R2_0006   04 02 02.54 +21 43 03.72 2000.00 dra=-1.107 ddec=42.332 vmag=13.51 # airmass=6.40
C2016_R2_0106   04 02 01.33 +21 43 46.02 2000.00 dra=-1.121 ddec=42.309 vmag=13.51 # airmass=2.65
C2016_R2_0206   04 02 00.12 +21 44 28.28 2000.00 dra=-1.133 ddec=42.264 vmag=13.51 # airmass=1.71
C2016_R2_0306   04 01 58.88 +21 45 10.48 2000.00 dra=-1.144 ddec=42.197 vmag=13.51 # airmass=1.31
C2016_R2_0406   04 01 57.65 +21 45 52.60 2000.00 dra=-1.150 ddec=42.113 vmag=13.51 # airmass=1.12
C2016_R2_0506   04 01 56.40 +21 46 34.64 2000.00 dra=-1.153 ddec=42.017 vmag=13.51 # airmass=1.02
C2016_R2_0606   04 01 55.15 +21 47 16.58 2000.00 dra=-1.152 ddec=41.916 vmag=13.51 # airmass=1.00
C2016_R2_0706   04 01 53.91 +21 47 58.42 2000.00 dra=-1.146 ddec=41.815 vmag=13.51 # airmass=1.04
C2016_R2_0806   04 01 52.68 +21 48 40.14 2000.00 dra=-1.136 ddec=41.721 vmag=13.51 # airmass=1.15
C2016_R2_0906   04 01 51.45 +21 49 21.79 2000.00 dra=-1.122 ddec=41.640 vmag=13.51 # airmass=1.38
C2016_R2_1006   04 01 50.25 +21 50 03.37 2000.00 dra=-1.106 ddec=41.578 vmag=13.51 # airmass=1.86
C2016_R2_1106   04 01 49.06 +21 50 44.88 2000.00 dra=-1.087 ddec=41.537 vmag=13.51 # airmass=3.06
C2016_R2_1206   04 01 47.90 +21 51 26.39 2000.00 dra=-1.067 ddec=41.520 vmag=13.51 # airmass=9.33
```

The first line is a comment that the target is down at the first query.  Subsequent lines are Keck starlist entries where the last four digits (after the `_`) are the UT time for that coordinate.  So at 0006UT the target is at `04 02 02.54 +21 43 03.72` and has the listed non-sidereal tracking rates.  Subsequent entries are each one hour later than the last entry.

You can specify the begin and end times for the query (the default is for the next 24 hours) and the spacing of the entries (default is one hour).  For details, see the help:

```
python horizons2starlist.py --help
usage: horizons2starlist.py [-h] [-v] [-f FROMDATE] [-t TODATE] [-s SPACING]
                            name

positional arguments:
  name                  The name of the target compatible with JPL horizons

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Be verbose! (default = False)
  -f FROMDATE, --from FROMDATE
                        From date for the starlist table (in ISO format)
  -t TODATE, --to TODATE
                        To date for the starlist table (in ISO format)
  -s SPACING, --spacing SPACING
                        The spacing for each starlist entry (e.g. 1h or 15m)
```


## KeckStarList.py

Some minor utilities for reading star lists.
