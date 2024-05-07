#!/usr/env/python

## Import General Tools
import sys
import argparse
import logging
import re
from pathlib import Path
import numpy as np
from astropy.table import Table, Column, vstack
from datetime import datetime, timedelta

from telescopeSchedule import get_telsched, get_observer_info_from_lastname

from matplotlib import pyplot as plt

site_list = sorted(['ANU', 'CIT', 'UCB', 'UCD', 'UCLA', 'UCSD', 'UCI', 'UCR',
                    'Yale', 'USRA', 'NU', 'HQ', 'IfA', 'Stanford', 'Swinburne',
                    'UCSB', 'UCSC', 'IPAC'])
site_list.append('Other')

group_list = ['HQ', 'UC', 'CIT', 'IfA+US', 'Australia', 'Other']
colors = ['r', 'b', 'y', 'k', 'k', 'g']
alphas = [0.2, 0.4, 0.4, 0.4, 0.2, 0.4]

group_members = {'UC': ['UCB', 'UCD', 'UCLA', 'UCSD', 'UCI', 'UCR', 'UCSB', 'UCSC'],
                 'IfA+US': ['Yale', 'USRA', 'NU', 'IfA', 'Stanford', 'IPAC'],
                 'Australia': ['ANU', 'Swinburne'],
                }

progID_names = {'Y': 'yale',
                'N': 'nasa',
                'U': 'uc',
                'C': 'caltech',
                'H': 'uh',
                'E': 'engineering',
                'S': 'subaru',
                'K': 'keck', 
                'O': 'northwestern',
                'R': 'noirlab',
                'W': 'swinburne', 
                'Z': 'z',
                'D': 'd',
                }

progID_city = {'yale': 'New York',
               'nasa': 'City and County of Denver',
               'uc': 'San Francisco',
               'caltech': 'Los Angeles',
               'cit': 'Los Angeles',
               'uh': 'Honolulu',
               'engineering': 'Waimea',
               'subaru': 'Tokyo',
               'keck': 'Waimea',
               'northwestern': 'Chicago',
               'noirlab': 'City and County of Denver',
               'swinburne': 'Melbourne',
               'z': 'Waimea',
               'd': 'Waimea',
               'other': 'Waimea',
               }



##-------------------------------------------------------------------------
## Parse Command Line Arguments
##-------------------------------------------------------------------------
## create a parser object for understanding command-line arguments
p = argparse.ArgumentParser(description='''
''')
## add options
# p.add_argument("--partner", dest="partner", type=str,
#     choices=['NASA', 'UC', 'CIT'],
#     help="Restrict to one partner?")
args = p.parse_args()

##-------------------------------------------------------------------------
## Create logger object
##-------------------------------------------------------------------------
log = logging.getLogger('SiteUseAnalysis')
log.setLevel(logging.DEBUG)
## Set up console output
LogConsoleHandler = logging.StreamHandler()
LogConsoleHandler.setLevel(logging.DEBUG)
LogFormat = logging.Formatter('%(asctime)s %(levelname)8s: %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')
LogConsoleHandler.setFormatter(LogFormat)
log.addHandler(LogConsoleHandler)


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def get_sched_single_query(from_date=None, ndays=100):
    if ndays > 100:
        ndays = 100
    sched = get_telsched(from_date=from_date, ndays=ndays, telnr=None)
    for site in site_list:
        sched.add_column(Column(name=site, data=np.zeros(len(sched), dtype=int)))
    for i,prog in enumerate(sched):
        # Fix Bad entry
        if prog['Location'] == 'CIT. Hirsch,CIT,UCB,CIT':
            sched[i]['Location'] = 'CIT,CIT,UCB,CIT'
            prog['Location'] = 'CIT,CIT,UCB,CIT'
        # Check if number of sites matches number of observer names
        these_sites = prog['Location'].split(',')
        these_observers = prog['Observers'].split(',')
        while len(these_sites) != len(these_observers):
            if len(these_sites) > len(these_observers):
                log.warning(f'{prog["Date"]}: N sites > N observers: removing last site')
                log.warning(these_observers)
                log.warning(these_sites)
                these_sites.pop()
            elif len(these_sites) < len(these_observers):
                log.warning(f'{prog["Date"]}: N sites < N observers: adding site Other')
                these_sites.append('Other')
        # Now fill out new columns with observer counts
        for site in these_sites:
            if site in site_list:
                sched[i][site] += 1
            elif site == 'Swin':
                sched[i]['Swinburne'] += 1
            elif site == 'Northwestern':
                sched[i]['NU'] += 1
            elif site == 'USCS':
                sched[i]['UCSC'] += 1
            elif site == 'NASA':
                sched[i]['Other'] += 1
            elif site == '':
                pass
            else:
                log.warning(f"Unrecognized site '{site}'")

    return sched


def get_sched_full(from_date='2018-02-01'):
    ndays = 100
    sched = get_sched_single_query(from_date=from_date, ndays=ndays)
    last_date = datetime.strptime(sched['Date'][-1], '%Y-%m-%d')
    log.info(f"Queried through {sched['Date'][-1]}")
    while last_date < datetime.now():
        new_sched = get_sched_single_query(
                        from_date=(last_date+timedelta(days=1)).strftime('%Y-%m-%d'),
                        ndays=ndays)
        sched = vstack([sched, new_sched])
        last_date = datetime.strptime(sched['Date'][-1], '%Y-%m-%d')
        log.info(f"Queried through {sched['Date'][-1]}")
    return sched


def group_sites(sched):
    log.info('Grouping sites')
    group_data = {}
    for group in group_members.keys():
        group_data[group] = []
    for entry in sched:
        for group in group_members.keys():
            group_count = 0
            for site in group_members[group]:
                group_count += entry[site]
            group_data[group].append(group_count)
    for group in group_members.keys():
        sched.add_column(Column(data=group_data[group], name=group))
    return sched




def estimate_emissions(sched):
    log.info('Estimating Emissions')
    emissions_table = Table.read('emissions_by_city.csv', format='ascii.csv')
    progID_emissions = {}
    for progID in progID_city.keys():
        city = progID_city[progID]
        if city == 'Waimea':
            progID_emissions[progID] = 0
        else:
            w = emissions_table['city'] == city
            progID_emissions[progID] = float(emissions_table[w]['co2_kg']/1000)

    travel = []
    emissions = []
    for entry in sched:
        inst = progID_names[entry['ProjCode'][0]]
        epp = progID_emissions[inst]
        if entry['HQ'] > 0 and epp > 0.001:
            travel.append(f"{entry['HQ']} x {progID_city[inst]}")
        else:
            travel.append('')
        emissions.append(entry['HQ']*epp)
    sched.add_column(Column(data=travel, name='Travel'))
    sched.add_column(Column(data=emissions, name='Emissions'))

    return sched


def build_table_per_night(sched):
    log.info('Building table of nights')
    date = datetime.strptime(sched['Date'][0], '%Y-%m-%d')
    nights = Table(names=('Date', 'Emissions'),
              dtype=('a10', 'f4'))
    for site in site_list:
        nights.add_column(Column(name=site, data=[], dtype=int))
    for group in group_members.keys():
        nights.add_column(Column(name=group, data=[], dtype=int))
    while date < datetime.now():
        date_string = date.strftime('%Y-%m-%d')
        w = (sched['Date'] == date_string)
        row = {'Date': date_string}
        row['Emissions'] = np.sum(sched[w]['Emissions'])
        for site in site_list:
            row[site] = np.sum(sched[w][site])
        for group in group_members.keys():
            row[group] = np.sum(sched[w][group])
        nights.add_row(row)
        date += timedelta(days=1)
    return nights


def plot_site_use(nights, smoothing=1):
    log.info('Plotting site use')

    smoothing_func = np.ones(smoothing)/smoothing
    dates = []
    observer_totals = []
    emissions = []
    observer_counts = {}
    observer_fractions = {}
    for group in group_list:
        observer_counts[group] = []
        observer_fractions[group] = []
    for night in nights:
        observer_count = 0
        for group in group_list:
            observer_count += night[group]
        if observer_count == 0:
            print(f"Observer count is 0 on {night['Date']}")
        else:
            dates.append(datetime.strptime(night['Date'], '%Y-%m-%d'))
            observer_totals.append(observer_count)
            emissions.append(night['Emissions'])
            for group in group_list:
                observer_counts[group].append(night[group])
                observer_fractions[group].append(night[group]/observer_count)

    # Pre-pandemic observer count
    pre_date_strings = ['2018-02-01', '2020-02-28']
    pre_dates = [datetime.strptime(pre_date_strings[0], '%Y-%m-%d'),
                 datetime.strptime(pre_date_strings[1], '%Y-%m-%d')]
    wpre = np.where((np.array(dates) >= pre_dates[0]) & (np.array(dates) <= pre_dates[1]))
    pre_mean_observer_count = np.mean(np.array(observer_totals)[wpre])
    pre_median_observer_count = np.median(np.array(observer_totals)[wpre])
    pre_std_observer_count = np.std(np.array(observer_totals)[wpre])
    pre_mean_HQobserver_count = np.mean(np.array(observer_counts['HQ'])[wpre])
    pre_median_HQobserver_count = np.median(np.array(observer_counts['HQ'])[wpre])
    pre_std_HQobserver_count = np.std(np.array(observer_counts['HQ'])[wpre])

    # Post-pandemic observer count
    post_date_strings = ['2022-07-01', '2024-04-30']
    post_dates = [datetime.strptime(post_date_strings[0], '%Y-%m-%d'),
                  datetime.strptime(post_date_strings[1], '%Y-%m-%d')]
    wpost = np.where((np.array(dates) >= post_dates[0]) & (np.array(dates) <= post_dates[1]))
    post_mean_observer_count = np.mean(np.array(observer_totals)[wpost])
    post_median_observer_count = np.median(np.array(observer_totals)[wpost])
    post_std_observer_count = np.std(np.array(observer_totals)[wpost])
    post_mean_HQobserver_count = np.mean(np.array(observer_counts['HQ'])[wpost])
    post_median_HQobserver_count = np.median(np.array(observer_counts['HQ'])[wpost])
    post_std_HQobserver_count = np.std(np.array(observer_counts['HQ'])[wpost])

    HQtitle_str = (f"Site Use Over Time (data smoothed over {smoothing} nights)\n"
                   f"Pre-pandemic ({pre_date_strings[0]} to {pre_date_strings[1]}) "
                   f"{pre_mean_HQobserver_count:.1f} mean HQ observers per night ({pre_median_HQobserver_count:.1f} median) [std dev = {pre_std_HQobserver_count:.1f}]\n"
                   f"Post-pandemic ({post_date_strings[0]} to {post_date_strings[1]}) "
                   f"{post_mean_HQobserver_count:.1f} mean HQ observers per night ({post_median_HQobserver_count:.1f} median) [std dev = {post_std_HQobserver_count:.1f}]"
                   )
    print(HQtitle_str)
    print()

    title_str = (f"Site Use Over Time (data smoothed over {smoothing} nights)\n"
                 f"Pre-pandemic ({pre_date_strings[0]} to {pre_date_strings[1]}) "
                 f"{pre_mean_observer_count:.1f} mean observers per night ({pre_median_observer_count:.1f} median) [std dev = {pre_std_observer_count:.1f}]\n"
                 f"Post-pandemic ({post_date_strings[0]} to {post_date_strings[1]}) "
                 f"{post_mean_observer_count:.1f} mean observers per night ({post_median_observer_count:.1f} median) [std dev = {post_std_observer_count:.1f}]"
                 )
    print(title_str)

    log.info('Building figure')
    plt.figure(figsize=(16,8))
    plt.title(title_str)
    previous_fracs = np.zeros(len(dates))
    for i,group in enumerate(group_list):
        smoothed_fractions = np.convolve(observer_fractions[group], smoothing_func, mode='same')
        plt.fill_between(dates,
                         previous_fracs,
                         previous_fracs+smoothed_fractions,
                         facecolor=colors[i], alpha=alphas[i],
                         step='post',
                         label=group)
        previous_fracs += smoothed_fractions
    # Plot these just to get on legend
    plt.plot(dates, [-1]*len(dates), 'k-', label='N Observers')
    plt.plot(dates, [-1]*len(dates),
             'r-', label='Pre-pandemic\nMean', alpha=0.5)
    plt.plot(dates, [-1]*len(dates),
             'b-', label='Post-pandemic\nMean', alpha=0.5)

    plt.grid()
    plt.ylim(0, 1.0)
    plt.ylabel('Fraction of Observers')
    plt.legend(loc='best')

    # Add timeline indicators
    v1 = datetime.strptime('2020-03-10', '%Y-%m-%d')
    plt.arrow(v1, 0, dx=0, dy=0.06, color='k')
    plt.annotate('v1.0', (v1, 0.07), color='k')
    v2 = datetime.strptime('2020-11-24', '%Y-%m-%d')
    plt.arrow(v2, 0, dx=0, dy=0.06, color='k')
    plt.annotate('v2.0', (v2, 0.07), color='k')

    smoothed_observer_totals = np.convolve(observer_totals, smoothing_func, mode='same')

    cax = plt.gca().twinx()
    cax.plot(dates, smoothed_observer_totals, 'k-', label='N Observers')
    cax.plot(pre_dates, [pre_mean_observer_count]*2,
             'r-', label='Pre-pandemic Mean', alpha=0.5)
    cax.plot(post_dates, [post_mean_observer_count]*2,
             'b-', label='Post-pandemic Mean', alpha=0.5)
    cax.set_ylabel('Number of Observers per Night')
    cax.set_ylim(0, 15)

    margin_frac = 0.16
    margin_days = (max(dates) - min(dates)).days*margin_frac
    plt.xlim(dates[0], dates[-1]+timedelta(days=margin_days))

    margin_frac = 0.16
    margin_days = (max(dates) - min(dates)).days*margin_frac
    plt.xlim(dates[0], dates[-1]+timedelta(days=margin_days))

    log.info("Saving figure")
    plt.savefig('Site_Use_Over_Time.png', bbox_inches='tight')

    #---------------------
    ## Emissions Plot
    #---------------------

    # Pre-pandemic emissions averages
    pre_date_strings = ['2018-02-01', '2020-02-21']
    pre_dates = [datetime.strptime(pre_date_strings[0], '%Y-%m-%d'),
                  datetime.strptime(pre_date_strings[1], '%Y-%m-%d')]
    wpre = np.where((np.array(dates) >= pre_dates[0]) & (np.array(dates) <= pre_dates[1]))
    pre_mean_emissions = np.mean(np.array(emissions)[wpre])
    pre_median_emissions = np.median(np.array(emissions)[wpre])
    pre_std_emissions = np.std(np.array(emissions)[wpre])

    # Shutdown emissions averages
    sd_date_strings = ['2020-05-31', '2021-06-30']
    sd_dates = [datetime.strptime(sd_date_strings[0], '%Y-%m-%d'),
                  datetime.strptime(sd_date_strings[1], '%Y-%m-%d')]
    wsd = np.where((np.array(dates) >= sd_dates[0]) & (np.array(dates) <= sd_dates[1]))
    sd_mean_emissions = np.mean(np.array(emissions)[wsd])
    sd_median_emissions = np.median(np.array(emissions)[wsd])
    sd_std_emissions = np.std(np.array(emissions)[wsd])

    # Post-pandemic emissions averages
    post_date_strings = ['2022-07-01', '2024-04-30']
    post_dates = [datetime.strptime(post_date_strings[0], '%Y-%m-%d'),
                  datetime.strptime(post_date_strings[1], '%Y-%m-%d')]
    wpost = np.where((np.array(dates) >= post_dates[0]) & (np.array(dates) <= post_dates[1]))
    post_mean_emissions = np.mean(np.array(emissions)[wpost])
    post_median_emissions = np.median(np.array(emissions)[wpost])
    post_std_emissions = np.std(np.array(emissions)[wpost])

    title_str = (f"Emissions Over Time (data smoothed over {smoothing} nights)\n"
                 f"Pre-pandemic ({pre_date_strings[0]} to {pre_date_strings[1]}) "
                 f"{pre_mean_emissions:.2f} tCO2e/night ({pre_mean_emissions*365:.0f} tCO2e/year)\n"
                 f"HQ Shutdown ({sd_date_strings[0]} to {sd_date_strings[1]}) "
                 f"{sd_mean_emissions:.2f} tCO2e/night ({sd_mean_emissions*365:.0f} tCO2e/year)\n"
                 f"Post-pandemic ({post_date_strings[0]} to {post_date_strings[1]}) "
                 f"{post_mean_emissions:.2f} tCO2e/night ({post_mean_emissions*365:.0f} tCO2e/year)"
                 )
    print(title_str)

    log.info('Building emissions figure')
    plt.figure(figsize=(16,8))
    plt.title(title_str)

    smoothed_fractions = np.convolve(observer_fractions['HQ'], smoothing_func, mode='same')
    plt.fill_between(dates,
                     np.zeros(len(smoothed_fractions)),
                     smoothed_fractions,
                     facecolor=colors[0], alpha=alphas[0],
                     step='post',
                     label='HQ')

    # Plot these just to get on legend
    plt.plot(dates, [-1]*len(dates), 'k-', label='Emissions')
    plt.plot(dates, [-1]*len(dates),
             'r-', label='Pre-pandemic\nMean', alpha=0.5)
    plt.plot(dates, [-1]*len(dates),
             'g-', label='HQ Closed\nMean', alpha=0.5)
    plt.plot(dates, [-1]*len(dates),
             'b-', label='Post-pandemic\nMean', alpha=0.5)

    plt.grid()
    plt.ylim(0, 1.0)
    plt.ylabel('Fraction of Observers')
    plt.legend(loc='best')

    cax = plt.gca().twinx()
    smoothed_emissions = np.convolve(emissions, smoothing_func, mode='same')
    cax.plot(dates, smoothed_emissions, 'k-',
                  label='Emissions',
                  drawstyle='steps-post')
    cax.plot(pre_dates, [pre_mean_emissions]*2,
             'r-', label='Pre-pandemic Mean', alpha=0.5)
    cax.plot(sd_dates, [sd_mean_emissions]*2,
             'g-', label='HQ Closed Mean', alpha=0.5)
    cax.plot(post_dates, [post_mean_emissions]*2,
             'b-', label='Post-pandemic Mean', alpha=0.5)
    cax.set_ylabel('Emissions (tCO2e / night)')

    margin_frac = 0.16
    margin_days = (max(dates) - min(dates)).days*margin_frac
    plt.xlim(dates[0], dates[-1]+timedelta(days=margin_days))

    log.info("Saving figure")
    plt.savefig('Emissions_Over_Time.png', bbox_inches='tight')


def collect_NASA_site_statistics(sched):
    nasa = sched[sched['Institution'] == 'NASA']
    output_keys = ['Date', 'Semester', 'Institution', 'ProjCode', 'FractionOfNight', 'PiFirstName', 'PiLastName', 'ANU', 'CIT', 'HQ', 'IPAC', 'IfA', 'NU', 'Stanford', 'Swinburne', 'UCB', 'UCD', 'UCI', 'UCLA', 'UCR', 'UCSB', 'UCSC', 'UCSD', 'USRA', 'Yale', 'Other']
    nasa[output_keys].write('NASA_use_table.csv', format='ascii.csv', overwrite=True)

    semesters = ['2018A', '2018B', '2019A', '2019B', '2020A', '2020B', '2021A',
                 '2021B', '2022A', '2022B']

    print(f"# NASA Observer Count and Weighted Count by Semester")
    title_line = f"Site      "
    for semester in semesters:
        title_line += f" | {semester:>11s}"
    title_line += " |        Totals"
    print(title_line)
    for site in site_list:
        tot = np.sum(nasa[site])
        wtot = np.sum(nasa[site]*nasa['FractionOfNight'])
        line = f"{site:10s}"
        for semester in semesters:
            s = nasa[nasa['Semester'] == semester]
            stot = np.sum(s[site])
            swtot = np.sum(s[site]*s['FractionOfNight'])
            line += f" | {stot:4d} {swtot:6.2f}"
        line += f" | {tot:4d} {wtot:8.2f}"
        print(line)



if __name__ == '__main__':
#     from_date = '2022-08-01'
    from_date = '2018-02-01'

    file = Path(f'sched_from_{from_date}.csv')
    nights_file = Path(f'nights_from_{from_date}.csv')

    if file.exists() is False:
        log.info('Querying database')
        sched = get_sched_full(from_date=from_date)
        sched = group_sites(sched)
        sched = estimate_emissions(sched)
        sched.write(file, format='ascii.csv')
        nights = build_table_per_night(sched)
        nights.write(nights_file, format='ascii.csv')
    else:
        log.info('Reading files on disk')
        sched = Table.read(file)
        nights = Table.read(nights_file)

    plot_site_use(nights, smoothing=30)

    collect_NASA_site_statistics(sched)