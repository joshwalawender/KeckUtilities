#!/usr/env/python

## Import General Tools
import sys
import argparse
import re
from pathlib import Path
import numpy as np
from astropy.table import Table, Column, vstack
from datetime import datetime, timedelta

from telescopeSchedule import get_telsched, get_observer_info_from_lastname

from matplotlib import pyplot as plt

site_list = sorted(['ANU', 'CIT', 'UCB', 'UCD', 'UCLA', 'UCSD', 'UCI', 'UCR', 'Yale',
                    'USRA', 'NU', 'HQ', 'IfA', 'Stanford', 'Swinburne', 'UCSB', 'UCSC'])
site_list.append('Other')

group_list = ['HQ', 'UC', 'CIT', 'IfA+US', 'Australia', 'Other']
colors = ['r', 'b', 'y', 'k', 'k', 'g']
alphas = [0.2, 0.4, 0.4, 0.4, 0.2, 0.4]

group_members = {'UC': ['UCB', 'UCD', 'UCLA', 'UCSD', 'UCI', 'UCR', 'UCSB', 'UCSC', 'USCS'],
                 'IfA+US': ['Yale', 'USRA', 'NU', 'IfA', 'Stanford', 'Northwestern'],
                 'Australia': ['ANU', 'Swinburne', 'Swin'],
                 'CIT': ['CIT'],
                 'Other': ['Other'],
                 'HQ': ['HQ']}

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
               'engineering': 'Honolulu',
               'subaru': 'Tokyo',
               'keck': 'Honolulu',
               'northwestern': 'Chicago',
               'noirlab': 'City and County of Denver',
               'swinburne': 'Melbourne',
               'z': 'Honolulu',
               'd': 'Honolulu',
               'other': 'Honolulu',
               }

emissions_table = Table.read('emissions_by_city.csv', format='ascii.csv')

progID_emissions = {}
for progID in progID_city.keys():
    city = progID_city[progID]
    w = emissions_table['city'] == city
    progID_emissions[progID] = float(emissions_table[w]['co2_kg']/1000)


# Using https://www.carbonfootprint.com/calculator.aspx
# progID_emissions = {'yale': 2.24, # JFK-SFO-KOA
#                     'nasa': 1.51, # DEN-SFO-KOA
#                     'uc': 1.07, # SFO-KOA
#                     'caltech': 1.13, # LAX-KOA
#                     'cit': 1.13, # LAX-KOA
#                     'uh': 0.07, # HNL-KOA
#                     'engineering': 0,
#                     'subaru': 1.81, # HND-KOA
#                     'keck': 0,
#                     'northwestern': 1.91, # CHI-SFO-KOA
#                     'noirlab': 1.51, # DEN-SFO-KOA
#                     'swinburne': 2.50, # MEL-SYD-KOA
#                     'z': 0,
#                     'd': 0,
#                     'other': 0,
#                 }

##-------------------------------------------------------------------------
## Parse Command Line Arguments
##-------------------------------------------------------------------------
## create a parser object for understanding command-line arguments
p = argparse.ArgumentParser(description='''
''')
## add options
p.add_argument("-f", "--file", dest="file", type=str, default='',
    help="File to use?  Query DB if not specified.")
p.add_argument("--partner", dest="partner", type=str,
    choices=['NASA', 'UC', 'CIT'],
    help="Restrict to one partner?")
args = p.parse_args()


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def get_site_table_single_query(from_date=None, ndays=5):
    if ndays > 100:
        ndays = 100
    sched = get_telsched(from_date=from_date, ndays=ndays, telnr=None)
    t = Table(names=['Date', 'progID', 'Observers', 'PiFirstName', 'PiLastName', 'PiId'] + site_list,
              dtype=['a10', 'a10', 'a100', 'a50', 'a50', 'i4'] + [int]*len(site_list))

    for prog in sched:
        if prog['Date'] not in list(t['Date']):
            row = {'Date': prog['Date'],
                   'Observers': prog['Observers'],
                   'progID': prog['ProjCode']}
            for site in site_list:
                row[site] = 0
            t.add_row(row)
        if prog['Location'] == 'CIT. Hirsch,CIT,UCB,CIT':
            tonights_sites = 'CIT,CIT,UCB,CIT'.split(',')
        else:
            tonights_sites = prog['Location'].split(',')
        tonights_observers = prog['Observers'].split(',')
        while len(tonights_sites) != len(tonights_observers):
            if len(tonights_sites) > len(tonights_observers):
                print(f'{prog["Date"]}: N sites > N observers: removing last site')
                tonights_sites.pop()
            elif len(tonights_sites) < len(tonights_observers):
                print(f'{prog["Date"]}: N sites < N observers: adding site Other')
                tonights_sites.append('Other')
        t.add_index('Date')
        rowid = t.loc_indices[prog['Date']]
        for entry in tonights_sites:
            if entry == 'CIT. Hirsch':
                print(tonights_sites)
                print('Correcting comma')
                entry = 'CIT, Hirsch'
            if entry in site_list:
                t[rowid][entry] += 1
            elif entry == 'Swin':
                t[rowid]['Swinburne'] += 1
            elif entry == 'Northwestern':
                t[rowid]['NU'] += 1
            elif entry == 'USCS':
                t[rowid]['UCSC'] += 1
            elif entry == 'NASA':
                t[rowid]['Other'] += 1
            elif entry == '':
                pass
            else:
                print(f'Unmatched entry: "{entry}"')

    return t


def get_site_table(from_date=None, ndays=5):
    t = get_site_table_single_query(from_date=from_date, ndays=ndays)
    last_date = datetime.strptime(t['Date'][-1], '%Y-%m-%d') + timedelta(days=1)
    while len(t) < ndays:
        need_more_days = ndays - len(t)
        print(f"At {last_date.strftime('%Y-%m-%d')}, Need {need_more_days} more days")
        new_t = get_site_table_single_query(
                         from_date=last_date.strftime('%Y-%m-%d'),
                         ndays=need_more_days)
        t = vstack([t, new_t])
        last_date = datetime.strptime(t['Date'][-1], '%Y-%m-%d') + timedelta(days=1)
    return t


def estimate_emissions(t):
    travel = []
    emissions = []
    for entry in t:
        if entry['HQ'] > 0 and entry['progID'][0] not in ['E', 'K']:
            travel.append(f"{entry['HQ']}x {progID_names[entry['progID'][0]]}")
            inst = progID_names[entry['progID'][0]]
            emissions.append(entry['HQ']*progID_emissions[inst])
        else:
            travel.append('')
            emissions.append(0)
    t.add_column(Column(data=travel, name='Travel'))
    t.add_column(Column(data=emissions, name='Emissions'))

    return t


def analyze_site_table(t, smoothing=14, partner=None):
    # Prepare table with sites grouped by partner
    g = Table(names=['Date'] + group_list,
              dtype=['a10'] + [int]*len(group_list))

    partner_codes = {None: None, 'NASA': 'N', 'CIT': 'C', 'UC': 'U'}
    partner = partner_codes[partner]

    # Add Observer Count Column
    observer_count = []
    for row in t:
        c = 0
        if row['progID'][0] == partner or partner is None:
            for col in row.colnames:
                if type(row[col]) == np.int64 and row[col] > 0:
                    c += row[col]
        observer_count.append(c)
        grow = [row['Date']]
        grow.extend([0]*len(group_list))
        g.add_row(grow)
        for col in row.colnames:
            if type(row[col]) == np.int64 and row[col] > 0:
                for group in group_list:
                    if col in group_members[group]:
                        g[-1][group] += row[col]

        if row['progID'][0] == partner or partner is None:
            gc = 0
            for group in group_list:
                if g[-1][group] > 0:
                    gc += g[-1][group]
            if c != gc:
                print(c, gc)

    t.add_column(Column(data=observer_count, name='Observer Count'))
    g.add_column(Column(data=observer_count, name='Observer Count'))

    woczero = np.where(g['Observer Count'] == 0)
    dates_zero = g['Date'][woczero]
    print(f"Removing {len(g['Date'][woczero])} nights with no observers")
    g.remove_rows(woczero)

    for group in group_list:
        frac = g[group]/g['Observer Count']
        g.add_column(Column(data=frac, name=f'{group} fraction'))

    # Smooth groups data
    print(f'Generating smoothed data. smoothing scale = {smoothing} nights')
    smoothed_group_counts = {}
    smoothed_group_fractions = {}
    smoothed_observer_counts = []
    smoothed_emissions = []
    for group in group_list:
        smoothed_group_counts[group] = []
        smoothed_group_fractions[group] = []
    for i,row in enumerate(g):
        if i < smoothing:
            imin = 0
        else:
            imin = i-smoothing
        imax = i+1

        smoothed_observer_count = np.mean(g[imin:imax+1]['Observer Count'])
        if np.isnan(smoothed_observer_count):
            print(g[imin:imax+1]['Observer Count'])
        smoothed_observer_counts.append( smoothed_observer_count )

        smoothed_emissions.append( np.mean(t[imin:imax+1]['Emissions']) )

        for group in group_list:
            smoothed_group_count = np.mean(g[imin:imax+1][group])
            smoothed_group_fraction = np.mean(g[imin:imax+1][f"{group} fraction"])
            smoothed_group_counts[group].append( smoothed_group_count )
            smoothed_group_fractions[group].append( smoothed_group_fraction )
            if np.isnan(smoothed_group_count):
                print(g[imin:imax+1][group])
            if np.isnan(smoothed_group_fraction):
                print(g[imin:imax+1][f"{group} fraction"])
    g.add_column(Column(data=smoothed_observer_counts, name=f'smoothed Observer Count'))
    g.add_column(Column(data=smoothed_emissions, name=f'smoothed Emissions'))
    for group in group_list:
        g.add_column(Column(data=smoothed_group_counts[group], name=f'smoothed {group}'))
        g.add_column(Column(data=smoothed_group_fractions[group], name=f'smoothed {group} fraction'))

    for date in dates_zero:
        data_dict = {'Date': date}
        for key in g.keys():
            if key not in ['Date', 'smoothed Observer Count', 'smoothed HQ']:
                data_dict[key] = 0
        data_dict['smoothed Observer Count'] = np.nan
        data_dict['smoothed HQ'] = np.nan
        g.add_row(data_dict)
    g.sort('Date')

    return t, g#, b


def plot_smoothed_site_use(t, g, smoothing=1, partner=None):
    dates = [datetime.strptime(d, '%Y-%m-%d') for d in g['Date']]
    plt.figure(figsize=(16,8))

    # Pre- vs. Post- Pandemic Observer Counts
    ids = [0, 750, 850, -1]
    woczero01 = np.where(t[ids[0]:ids[1]]['Observer Count'] != 0)
    woczero23 = np.where(t[ids[2]:ids[3]]['Observer Count'] != 0)
    pre_mean_observer_count = np.mean(t[ids[0]:ids[1]][woczero01]['Observer Count'])
    pre_median_observer_count = np.median(t[ids[0]:ids[1]][woczero01]['Observer Count'])
    pre_std_observer_count = np.std(t[ids[0]:ids[1]][woczero01]['Observer Count'])
    post_mean_observer_count = np.mean(t[ids[2]:ids[3]][woczero23]['Observer Count'])
    post_median_observer_count = np.median(t[ids[2]:ids[3]][woczero23]['Observer Count'])
    post_std_observer_count = np.std(t[ids[2]:ids[3]][woczero23]['Observer Count'])

    HQids = [0, 750, 1220, -1]
    woczero01 = np.where(t[HQids[0]:HQids[1]]['Observer Count'] != 0)
    woczero23 = np.where(t[HQids[2]:HQids[3]]['Observer Count'] != 0)
    pre_mean_HQobserver_count = np.mean(t[HQids[0]:HQids[1]][woczero01]['HQ'])
    pre_median_HQobserver_count = np.median(t[HQids[0]:HQids[1]][woczero01]['HQ'])
    pre_std_HQobserver_count = np.std(t[HQids[0]:HQids[1]][woczero01]['HQ'])
    post_mean_HQobserver_count = np.mean(t[HQids[2]:HQids[3]][woczero23]['HQ'])
    post_median_HQobserver_count = np.median(t[HQids[2]:HQids[3]][woczero23]['HQ'])
    post_std_HQobserver_count = np.std(t[HQids[2]:HQids[3]][woczero23]['HQ'])

    HQtitle_str = (f"Site Use Over Time (data smoothed over {smoothing} nights)\n"
                   f"Pre-pandemic ({t[ids[0]]['Date']} to {t[ids[1]]['Date']}) "
                   f"{pre_mean_HQobserver_count:.1f} mean HQ observers per night ({pre_median_HQobserver_count:.1f} median) [std dev = {pre_std_HQobserver_count:.1f}]\n"
                   f"Post-pandemic ({t[ids[2]]['Date']} to {t[ids[3]]['Date']}) "
                   f"{post_mean_HQobserver_count:.1f} mean HQ observers per night ({post_median_HQobserver_count:.1f} median) [std dev = {post_std_HQobserver_count:.1f}]"
                   )
    print(HQtitle_str)

    title_str = (f"Site Use Over Time (data smoothed over {smoothing} nights)\n"
                 f"Pre-pandemic ({t[ids[0]]['Date']} to {t[ids[1]]['Date']}) "
                 f"{pre_mean_observer_count:.1f} mean observers per night ({pre_median_observer_count:.1f} median) [std dev = {pre_std_observer_count:.1f}]\n"
                 f"Post-pandemic ({t[ids[2]]['Date']} to {t[ids[3]]['Date']}) "
                 f"{post_mean_observer_count:.1f} mean observers per night ({post_median_observer_count:.1f} median) [std dev = {post_std_observer_count:.1f}]"
                 )
    print(title_str)
    plt.title(title_str)
    previous_fracs = np.zeros(len(g))
    for i,group in enumerate(group_list):
        plt.fill_between(dates,
                         previous_fracs,
                         previous_fracs+g[f'smoothed {group} fraction'],
                         facecolor=colors[i], alpha=alphas[i],
                         step='post',
                         label=group)
        previous_fracs += g[f'smoothed {group} fraction']
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
    plt.arrow(v1, 0, dx=0, dy=0.06, color='g')
    plt.annotate('v1.0', (v1, 0.07), color='g')
    v2 = datetime.strptime('2020-11-24', '%Y-%m-%d')
    plt.arrow(v2, 0, dx=0, dy=0.06, color='g')
    plt.annotate('v2.0', (v2, 0.07), color='g')


    cax = plt.gca().twinx()
    cax.plot(dates, g['smoothed Observer Count'], 'k-',
                  label='N Observers',
                  drawstyle='steps-post')
    cax.plot([dates[ids[0]], dates[ids[1]]], [pre_mean_observer_count]*2,
             'r-', label='Pre-pandemic Mean', alpha=0.5)
    cax.plot([dates[ids[2]], dates[ids[3]]], [post_mean_observer_count]*2,
             'b-', label='Post-pandemic Mean', alpha=0.5)
    cax.set_ylabel('Number of Observers per Night')
    cax.set_ylim(0, 15)

    margin_frac = 0.16
    margin_days = (max(dates) - min(dates)).days*margin_frac
    plt.xlim(dates[0], dates[-1]+timedelta(days=margin_days))
#     plt.legend(loc='center right')

    filename = f"Site_Use_Over_Time"
    if partner is not None:
        filename+= f'_{partner}'
    filename += '.png'
    plt.savefig(filename, bbox_inches='tight')
#     plt.show()

    ##
    ## Emissions Plot
    ##
    # Pre- vs. Post- Pandemic Emissions
    plt.figure(figsize=(16,8))
    ids = [0, 750, 850, 1245, 1247, -1]
    pre_mean_emissions = np.mean(t[ids[0]:ids[1]]['Emissions'])
    pre_median_emissions = np.median(t[ids[0]:ids[1]]['Emissions'])
    pre_std_emissions = np.std(t[ids[0]:ids[1]]['Emissions'])

    shutdown_mean_emissions = np.mean(t[ids[2]:ids[3]]['Emissions'])
    shutdown_median_emissions = np.median(t[ids[2]:ids[3]]['Emissions'])
    shutdown_std_emissions = np.std(t[ids[2]:ids[3]]['Emissions'])

    post_mean_emissions = np.mean(t[ids[4]:ids[5]]['Emissions'])
    post_median_emissions = np.median(t[ids[4]:ids[5]]['Emissions'])
    post_std_emissions = np.std(t[ids[4]:ids[5]]['Emissions'])

    title_str = (f"Emissions Over Time (data smoothed over {smoothing} nights)\n"
                 f"Pre-pandemic ({t[ids[0]]['Date']} to {t[ids[1]]['Date']}) "
                 f"{pre_mean_emissions:.2f} tCO2e/night ({pre_mean_emissions*365:.0f} tCO2e/year)\n"
                 f"HQ Shutdown ({t[ids[2]]['Date']} to {t[ids[3]]['Date']}) "
                 f"{shutdown_mean_emissions:.2f} tCO2e/night ({shutdown_mean_emissions*365:.0f} tCO2e/year)\n"
                 f"Post-pandemic ({t[ids[4]]['Date']} to {t[ids[5]]['Date']}) "
                 f"{post_mean_emissions:.2f} tCO2e/night ({post_mean_emissions*365:.0f} tCO2e/year)"
                 )
    print()
    print(title_str)
    plt.title(title_str)

    previous_fracs = np.zeros(len(g))
    for i,group in enumerate(group_list):
        if group == 'HQ':
            plt.fill_between(dates,
                             previous_fracs,
                             previous_fracs+g[f'smoothed {group} fraction'],
                             facecolor=colors[i], alpha=alphas[i],
                             step='post',
                             label=group)
            previous_fracs += g[f'smoothed {group} fraction']
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
    cax.plot(dates, g['smoothed Emissions'], 'k-',
                  label='Emissions',
                  drawstyle='steps-post')
    cax.plot([dates[ids[0]], dates[ids[1]]], [pre_mean_emissions]*2,
             'r-', label='Pre-pandemic Mean', alpha=0.5)
    cax.plot([dates[ids[2]], dates[ids[3]]], [shutdown_mean_emissions]*2,
             'g-', label='HQ Closed Mean', alpha=0.5)
    cax.plot([dates[ids[4]], dates[ids[5]]], [post_mean_emissions]*2,
             'b-', label='Post-pandemic Mean', alpha=0.5)
    cax.set_ylabel('Emissions (tCO2e / night)')
#     cax.set_ylim(0, 15)

    margin_frac = 0.16
    margin_days = (max(dates) - min(dates)).days*margin_frac
    plt.xlim(dates[0], dates[-1]+timedelta(days=margin_days))
#     plt.legend(loc='center right')

    filename = f"Emissions_Over_Time"
    if partner is not None:
        filename+= f'_{partner}'
    filename += '.png'
    plt.savefig(filename, bbox_inches='tight')
#     plt.show()






if __name__ == '__main__':
    from_date = '2018-02-01'
    ndays = (datetime.now() - datetime.strptime(from_date, '%Y-%m-%d')).days

    if args.file != '':
        file = Path(args.file)
    else:
        file = Path(f'site_use_{ndays}days_from_{from_date}.csv')

    if file.exists() is False:
        print('Querying database')
        t = get_site_table(from_date=from_date, ndays=ndays)
        t.write(file, format='ascii.csv')
    else:
        print('Reading file on disk')
        t = Table.read(file)

    t = estimate_emissions(t)

    smoothing = 29
    t, g = analyze_site_table(t, smoothing=smoothing, partner=args.partner)
    plot_smoothed_site_use(t, g, smoothing=smoothing, partner=args.partner)

#     wt = np.where(t['Travel'] != '')
#     print(t[wt]['Date', 'progID', 'Travel', 'Emissions'])

#     wunknown = np.where(t[wt]['Emissions'] < 0.01)
#     print(t[wt][wunknown]['Date', 'progID', 'Travel', 'Emissions'])
