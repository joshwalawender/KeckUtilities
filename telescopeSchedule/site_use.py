#!/usr/env/python

## Import General Tools
import sys
import re
from pathlib import Path
import numpy as np
from astropy.table import Table, Column, vstack
from datetime import datetime, timedelta

from telescopeSchedule import get_telsched

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

##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def get_site_table_single_query(from_date=None, ndays=5):
    if ndays > 100:
        ndays = 100
    sched = get_telsched(from_date=from_date, ndays=ndays, telnr=None)
    t = Table(names=['Date'] + site_list,
              dtype=['a10'] + [int]*len(site_list))

    for prog in sched:
        if prog['Date'] not in list(t['Date']):
#             print(f"Adding {prog['Date']}")
            row = {'Date': prog['Date']}
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


def analyze_site_table(t, binsize=29, smoothing=14):
    # Prepare table with sites grouped by partner
    g = Table(names=['Date'] + group_list,
              dtype=['a10'] + [int]*len(group_list))

    # Add Observer Count Column
    observer_count = []
    for row in t:
        c = 0
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
        gc = 0
        for group in group_list:
            if g[-1][group] > 0:
                gc += g[-1][group]
        if c != gc:
            print(c, gc)
    t.add_column(Column(data=observer_count, name='Observer Count'))
    g.add_column(Column(data=observer_count, name='Observer Count'))

    woczero = np.where(g['Observer Count'] == 0)

    print(f"Removing {len(g['Date'][woczero])} nights with no observers:")
    print(g['Date'][woczero])
    g.remove_rows(woczero)

    for group in group_list:
        frac = g[group]/g['Observer Count']
#         frac[woczero] = 0
        g.add_column(Column(data=frac, name=f'{group} fraction'))

#     for entry in g:
#         fracs = [entry[f'{group} fraction'] for group in group_list]
#         total_frac = np.sum(fracs)
#         if abs(total_frac-1) > 0.05:
#             print(total_frac)
#             print(fracs)
#             print(entry)
#             print()
#             sys.exit()

    # Bin groups data
#     b = Table(names=['Date', 'ndays'] + group_list + ['Observer Count'],
#               dtype=['a10', 'i4'] + [int]*(len(group_list)+1))
#     nbinnedrows = int(np.floor(len(g)/binsize))
#     print(f'Generating time binned data. binsize = {binsize} nights')
#     for i in np.arange(0, nbinnedrows+1, 1):
#         grows = g[i*binsize:(i+1)*binsize]
#         from_date = grows['Date'][0]
#         to_date = grows['Date'][-1]
#         ndays = (datetime.strptime(to_date, '%Y-%m-%d') - datetime.strptime(from_date, '%Y-%m-%d')).days + 1
#         brow = [from_date, ndays]
#         brow.extend([0]*(len(group_list)+1))
#         for j,group in enumerate(group_list):
#             brow[j+2] = np.sum(grows[group])
#         brow[-1] = np.sum(grows['Observer Count'])
#         b.add_row(brow)
#     for group in group_list:
#         frac = b[group]/b['Observer Count']
#         b.add_column(Column(data=frac, name=f'{group} fraction'))
#     observers_per_night = b['Observer Count']/b['ndays']
#     b.add_column(Column(data=observers_per_night,
#                         name='Observers per Night'))

    # Smooth groups data
    print(f'Generating smoothed data. smoothing scale = {smoothing} nights')
    smoothed_group_counts = {}
    smoothed_group_fractions = {}
    smoothed_observer_counts = []
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
    for group in group_list:
        g.add_column(Column(data=smoothed_group_counts[group], name=f'smoothed {group}'))
        g.add_column(Column(data=smoothed_group_fractions[group], name=f'smoothed {group} fraction'))
    return t, g#, b


# def plot_grouped_site_use(t, g, binsize=1):
#     dates = [datetime.strptime(d, '%Y-%m-%d') for d in g['Date']]
#     plt.figure(figsize=(16,8))
# 
#     # Pre- vs. Post- Pandemic Observer Counts
#     ids = [0, 750, 850, -1]
#     pre_mean_observer_count = np.mean(t[ids[0]:ids[1]]['Observer Count'])
#     pre_median_observer_count = np.median(t[ids[0]:ids[1]]['Observer Count'])
#     pre_std_observer_count = np.std(t[ids[0]:ids[1]]['Observer Count'])
#     post_mean_observer_count = np.mean(t[ids[2]:ids[3]]['Observer Count'])
#     post_median_observer_count = np.median(t[ids[2]:ids[3]]['Observer Count'])
#     post_std_observer_count = np.std(t[ids[2]:ids[3]]['Observer Count'])
#     title_str = (f"Site Use Over Time (data binned over {binsize} nights)\n"
#                  f"Pre-pandemic ({t[ids[0]]['Date']} to {t[ids[1]]['Date']}) "
#                  f"{pre_mean_observer_count:.1f} mean observers per night ({pre_median_observer_count:.1f} median) [std dev = {pre_std_observer_count:.1f}]\n"
#                  f"Post-pandemic ({t[ids[2]]['Date']} to {t[ids[3]]['Date']}) "
#                  f"{post_mean_observer_count:.1f} mean observers per night ({post_median_observer_count:.1f} median) [std dev = {post_std_observer_count:.1f}]"
#                  )
#     print(title_str)
#     plt.title(title_str)
#     previous_fracs = np.zeros(len(g))
#     for i,group in enumerate(group_list):
#         plt.fill_between(dates,
#                          previous_fracs,
#                          previous_fracs+g[f'{group} fraction'],
#                          facecolor=colors[i], alpha=alphas[i],
#                          step='post',
#                          label=group)
#         previous_fracs += g[f'{group} fraction']
#     plt.grid()
#     plt.ylim(0, 1.0)
#     plt.ylabel('Fraction of Observers')
#     plt.legend(loc='upper right')
# 
#     cax = plt.gca().twinx()
#     cax.plot_date(dates, g['Observers per Night'], 'k-',
#                   label='N Observers',
#                   drawstyle='steps-post')
#     cax.set_ylabel('Number of Observers per Night')
#     cax.set_ylim(3, 13)
# 
#     margin_frac = 0.12
#     margin_days = (max(dates) - min(dates)).days*margin_frac
#     plt.xlim(dates[0], dates[-1]+timedelta(days=margin_days))
#     plt.legend(loc='center right')
# 
#     plt.savefig('Site_Use_Over_Time.png', bbox_inches='tight')
#     plt.show()


def plot_smoothed_site_use(t, g, smoothing=1):
    dates = [datetime.strptime(d, '%Y-%m-%d') for d in g['Date']]
    plt.figure(figsize=(16,8))

    # Pre- vs. Post- Pandemic Observer Counts
    ids = [0, 750, 850, -1]
    pre_mean_observer_count = np.mean(t[ids[0]:ids[1]]['Observer Count'])
    pre_median_observer_count = np.median(t[ids[0]:ids[1]]['Observer Count'])
    pre_std_observer_count = np.std(t[ids[0]:ids[1]]['Observer Count'])
    post_mean_observer_count = np.mean(t[ids[2]:ids[3]]['Observer Count'])
    post_median_observer_count = np.median(t[ids[2]:ids[3]]['Observer Count'])
    post_std_observer_count = np.std(t[ids[2]:ids[3]]['Observer Count'])
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
             'r-', label='Pre-pandemic\nMedian', alpha=0.5)
    plt.plot(dates, [-1]*len(dates),
             'b-', label='Post-pandemic\nMedian', alpha=0.5)

    plt.grid()
    plt.ylim(0, 1.0)
    plt.ylabel('Fraction of Observers')
    plt.legend(loc='best')
#     plt.legend(loc='upper right')

    cax = plt.gca().twinx()
    cax.plot(dates, g['smoothed Observer Count'], 'k-',
                  label='N Observers',
                  drawstyle='steps-post')
    cax.plot([dates[ids[0]], dates[ids[1]]], [pre_median_observer_count]*2,
             'r-', label='Pre-pandemic Median', alpha=0.5)
    cax.plot([dates[ids[2]], dates[ids[3]]], [post_median_observer_count]*2,
             'b-', label='Post-pandemic Median', alpha=0.5)
#     cax.plot(dates[ids[0]:ids[1]], [pre_median_observer_count]*(ids[1]-ids[0]),
#              'r-', label='Pre-pandemic Median', alpha=0.5)
#     cax.plot(dates[ids[2]:ids[3]], [post_median_observer_count]*(len(t)-ids[2]-1),
#              'b-', label='Post-pandemic Median', alpha=0.5)
    cax.set_ylabel('Number of Observers per Night')
    cax.set_ylim(0, 15)

    margin_frac = 0.15
    margin_days = (max(dates) - min(dates)).days*margin_frac
    plt.xlim(dates[0], dates[-1]+timedelta(days=margin_days))
#     plt.legend(loc='center right')

    plt.savefig('Site_Use_Over_Time.png', bbox_inches='tight')
#     plt.show()



if __name__ == '__main__':
    from_date = '2018-02-01'
    ndays = (datetime.now() - datetime.strptime(from_date, '%Y-%m-%d')).days
    file = Path(f'site_use_{ndays}days_from_{from_date}.csv')
    if file.exists() is False:
        print('Querying database')
        t = get_site_table(from_date=from_date, ndays=ndays)
        t.write(file, format='ascii.csv')
    else:
        print('Reading file on disk')
        t = Table.read(file)

    binsize = 29
    smoothing = 29
    t, g = analyze_site_table(t, binsize=binsize, smoothing=smoothing)
    plot_smoothed_site_use(t, g, smoothing=smoothing)
    