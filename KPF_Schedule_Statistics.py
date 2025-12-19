## Import General Tools
import sys
from pathlib import Path
import datetime
from astropy.table import Table
import numpy as np
from matplotlib import pyplot as plt

from utils.observatoryAPIs import *


def kpf_use_by_partner():
    semesters = {'2023A': [0, 0, 0 , 0, 0],
                 '2023B': [0, 0, 10, 0, 0],
                 '2024A': [0, 0, 0 , 0, 0],
                 '2024B': [0, 0, 0 , 0, 0],
                 '2025A': [0, 0, 43, 0, 0],
                 '2025B': [0, 0, 43, 0, 0],
                 '2026A': [0, 0, 0 , 0, 0],
                 }
    kpf_time = {}
    all_time = {}

    for i,s in enumerate(semesters.keys()):
        semester_night_total = 0
        semester, start, end = get_semester_dates(s)
        semester_length = (end-start)
        nnights = semester_length.days
        remainder = semester_length - datetime.timedelta(days=semester_length.days)
        if remainder.total_seconds() > 24*60*60/2:
            nnights += 1
        semester_schedule = getSchedule(date=start.strftime('%Y-%m-%d'),
                                        numdays=nnights, telnr=1)
        for i,sched in enumerate(semester_schedule):
            date = sched.get('Date')
            institution = sched.get('Institution')
            frac = sched.get('FractionOfNight')
            instrument = sched.get('Instrument')
            obstype = sched.get('ObsType')
#             print(i, date, institution, instrument, frac, obstype)
            if obstype not in ['ToO', 'Twilight']:
                if institution is None or instrument is None or frac is None:
                    print(sched)
                    sys.exit(0)
    
                semester_night_total += frac
                if institution[:2] == 'UC':
                    institution = 'UC'
                if sched.get('ProjCode')[0] == 'E':
                    institution = 'Engineering'
                if institution not in all_time.keys():
                    all_time[institution] = frac
                else:
                    all_time[institution] += frac
    
                if instrument in ['KPF', 'KPF-CC']:
                    if institution not in kpf_time.keys():
                        kpf_time[institution] = frac
                    else:
                        kpf_time[institution] += frac
        if abs(semester_night_total-nnights) > 0.1:
            print(semester_night_total, nnights)
        print(f"KPF assigned time by institution from 2023A through {s}:")
        for institution in kpf_time.keys():
            frac = kpf_time[institution]/all_time[institution]
            print(f"{institution:11s}: {kpf_time[institution]:>5.2f} KPF nights represent {frac:.1%} of allocated time")

    kpf_night_sum = np.sum([kpf_time[x] for x in kpf_time.keys()])
    all_night_sum = np.sum([all_time[x] for x in all_time.keys()])
    total_frac = kpf_night_sum/all_night_sum
    print(f"Total: {kpf_night_sum:>5.2f} KPF nights represent {total_frac:.1%} of allocated time")


def kpf_nights_vs_kcwi():
    datafile = Path('KPF_Schedule_Statistics.txt')
    if datafile.exists():
        # Read the data from disk if present
        t = Table.read(datafile, format='ascii.csv')
    else:
        # Get the data from schedule database if it is not already on disk
        semesters = {'2022B': [0, 0, 0 , 0, 0],
                     '2023A': [0, 0, 0 , 0, 0],
                     '2023B': [0, 0, 10, 0, 0],
                     '2024A': [0, 0, 0 , 0, 0],
                     '2024B': [0, 0, 0 , 0, 0],
                     '2025A': [0, 0, 43, 0, 0],
                     '2025B': [0, 0, 43, 0, 0],
                     '2026A': [0, 0, 0 , 0, 0],
                     }
        found_first_science_night = False
        for i,s in enumerate(semesters.keys()):
            semester, start, end = get_semester_dates(s)
            semester_length = (end-start)
            nnights = semester_length.days
            remainder = semester_length - datetime.timedelta(days=semester_length.days)
            if remainder.total_seconds() > 24*60*60/2:
                nnights += 1
            semesters[s][3] = nnights
            print(f"Getting KPF schedule statistics for {s}: {semester_length} = {nnights} nights")
            params = {'instrument': 'KPF',
                      'startdate': start.strftime('%Y-%m-%d'),
                      'enddate': end.strftime('%Y-%m-%d')}
            KPFnights = query_observatoryAPI('schedule', 'getInstrumentDates', params)
            for j,night in enumerate(KPFnights):
                schedule = getSchedule(date=night.get('Date'), numdays=1, telnr=1)
                for sched in schedule:
                    if sched.get('Instrument') in ['KPF', 'KPF-CC']:
                        if not found_first_science_night and sched.get('Principal', '') not in ['Engineering', 'CIT Director', 'Howard']:
                            found_first_science_night = True
                            print(f'First night of KPF science:')
                            print(sched)
                            sys.exit(0)
                        instno = {'KPF': 0, 'KPF-CC': 1}[sched.get('Instrument')]
                        if sched.get('FractionOfNight', None) == None:
                            # Determine Length of Scheduled Time
                            starth, startm = sched.get('StartTime').split(':')
                            endh, endm = sched.get('EndTime').split(':')
                            duration = (int(endh)+int(endm)/60) - (int(starth)+int(startm)/60)
    #                         print(f'{sched.get("StartTime")}-{sched.get("EndTime")}={duration:.2f} hr')
                            # Determine Length of Night
                            twilights = getTwilights(night.get('Date'))
                            dawn_12degh, dawn_12degm = twilights.get('dawn_12deg').split(':')
                            dusk_12degh, dusk_12degm = twilights.get('dusk_12deg').split(':')
                            length_of_night = (int(dawn_12degh)+int(dawn_12degm)/60) - (int(dusk_12degh)+int(dusk_12degm)/60)
    #                         print(f'{twilights.get("dusk_12deg")}-{twilights.get("dawn_12deg")}={length_of_night:.2f} hr')
                            FractionOfNight = duration/length_of_night
                            print(f'{night.get("Date")} FractionOfNight calculated to be {FractionOfNight:.2f}')
                            semesters[semester][instno] += FractionOfNight
                        else:
                            semesters[semester][instno] += sched.get('FractionOfNight')

            print(f"Getting KCWI schedule statistics for {s}: {semester_length} = {nnights} nights")
            params = {'instrument': 'KCWI',
                      'startdate': start.strftime('%Y-%m-%d'),
                      'enddate': end.strftime('%Y-%m-%d')}
            KCWInights = query_observatoryAPI('schedule', 'getInstrumentDates', params)
            for night in KCWInights:
                schedule = getSchedule(date=night.get('Date'), numdays=1, telnr=2)
                for sched in schedule:
                    if sched.get('Instrument') in ['KCWI']:
                        instno = 4
                        if sched.get('FractionOfNight', None) == None:
                            # Determine Length of Scheduled Time
                            starth, startm = sched.get('StartTime').split(':')
                            endh, endm = sched.get('EndTime').split(':')
                            duration = (int(endh)+int(endm)/60) - (int(starth)+int(startm)/60)
    #                         print(f'{sched.get("StartTime")}-{sched.get("EndTime")}={duration:.2f} hr')
                            # Determine Length of Night
                            twilights = getTwilights(night.get('Date'))
                            dawn_12degh, dawn_12degm = twilights.get('dawn_12deg').split(':')
                            dusk_12degh, dusk_12degm = twilights.get('dusk_12deg').split(':')
                            length_of_night = (int(dawn_12degh)+int(dawn_12degm)/60) - (int(dusk_12degh)+int(dusk_12degm)/60)
    #                         print(f'{twilights.get("dusk_12deg")}-{twilights.get("dawn_12deg")}={length_of_night:.2f} hr')
                            FractionOfNight = duration/length_of_night
                            print(f'{night.get("Date")} FractionOfNight calculated to be {FractionOfNight:.2f}')
                            semesters[semester][instno] += FractionOfNight
                        else:
                            semesters[semester][instno] += sched.get('FractionOfNight')


        t = Table(names=('semester', 'KPF', 'KPF-CC', 'shutdown', 'semester_length', 'KCWI'),
                  dtype=('a5', 'f4', 'f4', 'i4', 'i4', 'f4'))
        for s in semesters.keys():
            row = {'semester': s,
                   'KPF': semesters[s][0],
                   'KPF-CC': semesters[s][1],
                   'shutdown': semesters[s][2],
                   'semester_length': semesters[s][3],
                   'KCWI': semesters[s][4],
                   }
            t.add_row(row)
        t.write(datafile, format='ascii.csv')

    # Analysis
    plt.figure(figsize=(10,4))

    plt.title('Assigned Time (Science+Engineering)')
    nnights = t['semester_length'] - t['shutdown']
    plt.plot(t['semester'], t['KCWI']/nnights, 'go-', alpha=1, label='KCWI')
    plt.plot(t['semester'], t['KPF']/nnights, 'cx-', alpha=0.5, label='KPF')
    plt.plot(t['semester'], t['KPF-CC']/nnights, 'yx-', alpha=1, label='KPF-CC')
    plt.plot(t['semester'], (t['KPF']+t['KPF-CC'])/nnights, 'bo-', label='All KPF')
    plt.xlabel('Semester')
    plt.ylabel('Fraction of Nights')
    plt.ylim(-0.01, 0.51)
    plt.grid()
    plt.legend(loc='best')

#     plt.show()
    plt.savefig('KPF_Schedule_Statistics.png', bbox_inches='tight', pad_inches=0.10)
    

if __name__ == '__main__':
#     kpf_nights_vs_kcwi()
    kpf_use_by_partner()