# KeckUtilities

A few utility scripts for use at Keck Observatory.

## KeckStarList.py

## SupportNightCalendar.py

Used to generate an ICS file (for use in typical calendar applications) of support nights.

To use, first download the [telescope schedule](https://www.keck.hawaii.edu/observing/schedule/schQuery.php?table=telsched) from the Keck Schedule Database Query page.  Make sure at least the "Date", "Instrument", "Observers", and "Location" options are checked (checking all the options is fine if you don't want to remember which are required).  Click the "Export to CSV" button and save the downloaded file.  The software expects the file to be called `telsched.csv` in the current directory, but you can optionally specify an alternate path and filename using the `--telsched` command line argument if you save it under another name.

Next, download the [support astronomer schedule](https://www.keck.hawaii.edu/observing/schedule/schQuery.php?table=sa) for yourself.  Make sure that the "Date" option is checked along with the option for your initials (make sure only one set of initials is checked, the software assume that the schedule is being made for onely one SA).  Click the "Export to CSV" button and save the downloaded file.  The software expects the file to be called `sasched.csv` in the current directory, but you can optionally specify an alternate path and filename using the `--sasched` command line argument if you save it under another name.

Execute the program using: `python KeckStarList.py` (adding `--telsched` and/or `--sasched` arguments if desired).  The output will be a file in the local directory called `Nights.ics` which should be able to be imported by any calendar program.

The calendar entry for each support night will run from 2pm to 11pm during the date in question and be called "[Instrument] Support" where [Instrument] is replaced with the instrument name from the schedule.  If the schedule reports you as on call or training, the calendar entry will replace "Support" with "On Call" or "Training" in the event name.  The notes portion of the calendar entry will have the PI name, observers list, and location.

The start and end times can be changed using the `--start` and `--end` command line options respectively.

### Known Bugs

The start and end times of each calendar entry are always on the same day.  Code needs to be modified to allow the end time to be specified as the next day if after midnight.

### Example ICS Entry

    BEGIN:VEVENT
    UID:20160803T215325Z-0011@kecksupportcalendar.com
    DTSTAMP:20160803T215325Z
    DTSTART;TZID=Pacific/Honolulu:20160806T140000
    DTEND;TZID=Pacific/Honolulu:20160806T230000
    SUMMARY:HIRESr Support
    DESCRIPTION: PI: Matsuno\nObservers: Matsuno, Aoki\nLocation: HQ
    END:VEVENT