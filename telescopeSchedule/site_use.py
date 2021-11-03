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

group_list = ['UC', 'CIT', 'IfA+US', 'Australia', 'HQ', 'Other']
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


def analyze_site_table(t, binsize=29):
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

    for group in group_list:
        frac = g[group]/g['Observer Count']
        g.add_column(Column(data=frac, name=f'{group} fraction'))

    # Bin groups data
    b = Table(names=['Date'] + group_list + ['Observer Count'],
              dtype=['a10'] + [int]*(len(group_list)+1))
    nbinnedrows = int(np.floor(len(g)/binsize))
    for i in np.arange(0, nbinnedrows, 1):
        grows = g[i*binsize:(i+1)*binsize]
        brow = [grows[0]['Date']]
        brow.extend([0]*(len(group_list)+1))
        for j,group in enumerate(group_list):
            brow[j+1] = np.sum(grows[group])
        brow[-1] = np.sum(grows['Observer Count'])
        b.add_row(brow)
    for group in group_list:
        frac = b[group]/b['Observer Count']
        b.add_column(Column(data=frac, name=f'{group} fraction'))
    b.add_column(Column(data=[c/binsize for c in b['Observer Count']],
                        name='Observers per Night'))
    return t, g, b


def plot_grouped_site_use(t, g):
    dates = [datetime.strptime(d, '%Y-%m-%d') for d in g['Date']]
    plt.figure(figsize=(16,8))

    # Pre- vs. Post- Pandemic Observer Counts
    ids = [0, 750, 850, -1]
    print(f"Pre-pandemic time frame: {t[ids[0]]['Date']} to {t[ids[1]]['Date']}")
    pre_mean_observer_count = np.mean(t[ids[0]:ids[1]]['Observer Count'])
    pre_median_observer_count = np.median(t[ids[0]:ids[1]]['Observer Count'])
    print(f"  {pre_mean_observer_count:.1f} mean observers per night ({pre_median_observer_count:.1f} median)")
    print(f"Post-pandemic time frame: {t[ids[2]]['Date']} to {t[ids[3]]['Date']}")
    post_mean_observer_count = np.mean(t[ids[2]:ids[3]]['Observer Count'])
    post_median_observer_count = np.median(t[ids[2]:ids[3]]['Observer Count'])
    print(f"  {post_mean_observer_count:.1f} mean observers per night ({post_median_observer_count:.1f} median)")

    title_str = (f"Site Use Over Time\n"
                 f"Pre-pandemic ({t[ids[0]]['Date']} to {t[ids[1]]['Date']}) "
                 f"{pre_mean_observer_count:.1f} mean observers per night ({pre_median_observer_count:.1f} median)\n"
                 f"Post-pandemic ({t[ids[2]]['Date']} to {t[ids[3]]['Date']}) "
                 f"{post_mean_observer_count:.1f} mean observers per night ({post_median_observer_count:.1f} median)"
                 )
    plt.title(title_str)
    colors = ['b', 'y', 'k', 'k', 'r', 'g']
    alphas = [0.4, 0.4, 0.4, 0.2, 0.2, 0.4]
    previous_fracs = np.zeros(len(g))
    for i,group in enumerate(group_list):
        plt.fill_between(dates,
                         previous_fracs,
                         previous_fracs+g[f'{group} fraction'],
                         facecolor=colors[i], alpha=alphas[i],
                         step='post',
                         label=group)
        previous_fracs += g[f'{group} fraction']
    plt.grid()
    plt.ylim(0, 1.0)
    plt.ylabel('Fraction of Observers')
    plt.legend(loc='upper right')

    cax = plt.gca().twinx()
    cax.plot_date(dates, g['Observers per Night'], 'k-',
                  label='N Observers',
                  drawstyle='steps-post')
    cax.set_ylabel('Number of Observers per Night')
    cax.set_ylim(3, 13)

    margin_frac = 0.15
    margin_days = (max(dates) - min(dates)).days*margin_frac
    plt.xlim(dates[0], dates[-1]+timedelta(days=margin_days))
    plt.legend(loc='center right')

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
    t, g, b = analyze_site_table(t)
    plot_grouped_site_use(t, b)
    