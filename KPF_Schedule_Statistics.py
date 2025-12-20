## Import General Tools
import sys
import copy
from pathlib import Path
import datetime
from astropy.table import Table
import numpy as np
from matplotlib import pyplot as plt

from utils.observatoryAPIs import *


def get_instrument_frac_from_schedule_entry(sched, instrument='KPF'):
    date = sched.get('Date')
    institution = sched.get('Institution')
    frac = sched.get('FractionOfNight')
    obstype = sched.get('ObsType')
    if obstype in ['ToO', 'Twilight']:
        instrument_time = 0
        frac = 0
    else:
        if institution is None or sched.get('Instrument') is None or frac is None:
            print(sched)
            sys.exit(0)
        if institution[:2] == 'UC':
            institution = 'UC'
        if sched.get('ProjCode')[0] == 'E':
            institution = 'Engineering'

        instrument_time = 0 if sched.get('Instrument') != instrument else frac

    result = {'institution': institution,
              'instrument': instrument_time,
              'all': 0 if sched.get('Instrument') == '' else frac,
              }

    return result


def kpf_use_by_partner():
    initial_semester_data = {'KPF': 0, 'KPF-CC': 0, 'All': 0,
                             'KCWI': 0, 'All_K2': 0}
    semesters = {'2023A': copy.deepcopy(initial_semester_data),
                 '2023B': copy.deepcopy(initial_semester_data),
                 '2024A': copy.deepcopy(initial_semester_data),
                 '2024B': copy.deepcopy(initial_semester_data),
                 '2025A': copy.deepcopy(initial_semester_data),
                 '2025B': copy.deepcopy(initial_semester_data),
                 '2026A': copy.deepcopy(initial_semester_data),
                 }
    kpf_time = {}
    all_time = {}

    for i,s in enumerate(semesters.keys()):
        sem_kpf_time = {}
        sem_kpfcc_time = {}
        sem_all_time = {}
        semester_night_total = 0
        semester, start, end = get_semester_dates(s)
        semester_length = (end-start)
        nnights = semester_length.days
        remainder = semester_length - datetime.timedelta(days=semester_length.days)
        if remainder.total_seconds() > 24*60*60/2:
            nnights += 1
        # Get KCWI Statistics
        k2_semester_schedule = getSchedule(date=start.strftime('%Y-%m-%d'),
                                           numdays=nnights, telnr=2)
        for i,sched in enumerate(k2_semester_schedule):
            result = get_instrument_frac_from_schedule_entry(sched, instrument='KCWI')
            semesters[s]['KCWI'] += result['instrument']
            semesters[s]['All_K2'] += result['all']
        # Get KPF Statistics
        semester_schedule = getSchedule(date=start.strftime('%Y-%m-%d'),
                                        numdays=nnights, telnr=1)
        for i,sched in enumerate(semester_schedule):

            # KPF Results
            result = get_instrument_frac_from_schedule_entry(sched, instrument='KPF')
            semesters[s]['KPF'] += result['instrument']
            semesters[s]['All'] += result['all']
            if result['institution'] not in semesters[s].keys():
                semesters[s][f"{result['institution']}"] = result['instrument']
                semesters[s][f"{result['institution']}_All"] = result['all']
            else:
                semesters[s][f"{result['institution']}"] += result['instrument']
                semesters[s][f"{result['institution']}_All"] += result['all']

            # KPF-CC Results
            result = get_instrument_frac_from_schedule_entry(sched, instrument='KPF-CC')
            semesters[s]['KPF-CC'] += result['instrument']
            if result['institution'] not in semesters[s].keys():
                semesters[s][f"{result['institution']}"] = result['instrument']
            else:
                semesters[s][f"{result['institution']}"] += result['instrument']

        if abs(semesters[s]['All']-nnights) > 0.1:
            print(f"{s} missing {nnights-semesters[s]['All']:.1f} nights in schedule")

        sem_frac = (semesters[s]['KPF']+semesters[s]['KPF-CC'])/semesters[s]['All']
        print(f"{s}: {semesters[s]['KPF']+semesters[s]['KPF-CC']:>5.2f} KPF nights represent {sem_frac:.1%} of allocated time")
        for institution in semesters[s].keys():
            if institution not in initial_semester_data.keys() and institution[-4:] != '_All':
                if semesters[s][institution] > 0.01:
                    frac = semesters[s][institution]/semesters[s][f"{institution}_All"]
                    print(f" {institution:12s}: {semesters[s][institution]:>5.2f} KPF nights represent {frac:.1%} of allocated time")
        print()

    # Plot KPF Use Over Time
    snames = sorted(list(semesters.keys()))
    fkpf = [semesters[s]['KPF']/semesters[s]['All'] for s in snames]
    fkpfcc = [semesters[s]['KPF-CC']/semesters[s]['All'] for s in snames]
    fallkpf = [(semesters[s]['KPF']+semesters[s]['KPF-CC'])/semesters[s]['All'] for s in snames]
    fkcwi = [semesters[s]['KCWI']/semesters[s]['All_K2'] for s in snames]
    plt.figure(figsize=(10,4))

    plt.title('Scheduled Science Time')
    width = 0.42
    xind = np.arange(0,len(snames))
    bottom = np.zeros(len(snames))
    plt.bar(xind+width/2, fkcwi,  color='g', alpha=0.9, width=width, label='KCWI')
    plt.bar(xind-width/2, fkpf,   color='b', alpha=0.9, width=width, label='KPF', bottom=0)
    plt.bar(xind-width/2, fkpfcc, color='c', alpha=0.9, width=width, label='KPF-CC', bottom=fkpf)

#     plt.plot(snames, fkcwi, 'go-', alpha=1, label='KCWI')
#     plt.plot(snames, fkpf, 'cx-', alpha=0.5, label='KPF')
#     plt.plot(snames, fkpfcc, 'yx-', alpha=1, label='KPF-CC')
#     plt.plot(snames, fallkpf, 'bo-', label='All KPF')

    plt.xticks(xind, snames)
    plt.xlabel('Semester')
    plt.ylabel('Fraction of Nights')
    plt.ylim(0, 0.47)
    plt.grid(axis='y')
    plt.legend(loc='best')

#     plt.show()
    plt.savefig('KPF_Use_By_Semester.png', bbox_inches='tight', pad_inches=0.10)

    # Summarize KPF Use by Institution
    institutional_totals = {}
    for s in snames:
        for institution in semesters[s].keys():
            if institution not in initial_semester_data.keys() and institution[-4:] != '_All':
                if institution not in institutional_totals.keys():
                    institutional_totals[f"{institution}"] = semesters[s][institution]
                    institutional_totals[f"{institution}_All"] = semesters[s][f"{institution}_All"]
                else:
                    institutional_totals[f"{institution}"] += semesters[s][institution]
                    institutional_totals[f"{institution}_All"] += semesters[s][f"{institution}_All"]

    # Sort institutions by number of nights
    institutions = [x[0] for x in sorted(institutional_totals.items(),
                    key=lambda item: item[1], reverse=True)]

    print(f"KPF assigned time by institution from 2023A through 2026A:")
    for institution in institutions:
        if institution not in initial_semester_data.keys() and institution[-4:] != '_All':
            if institutional_totals[institution] > 0.01:
                frac = institutional_totals[institution]/institutional_totals[f"{institution}_All"]
                print(f" {institution:12s}: {institutional_totals[institution]:>5.2f} KPF nights represent {frac:.1%} of allocated time")

    kpf_sum = np.sum([semesters[s]['KPF'] for s in snames])
    kpfcc_sum = np.sum([semesters[s]['KPF-CC'] for s in snames])
    all_sum = np.sum([semesters[s]['All'] for s in snames])

    total_frac = (kpf_sum+kpfcc_sum)/all_sum
    print(f"Total: {kpf_sum+kpfcc_sum:>5.2f} KPF nights represent {total_frac:.1%} of allocated time")





def old_kpf_nights_vs_kcwi():
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