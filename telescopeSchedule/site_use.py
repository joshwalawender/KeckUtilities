#!/usr/env/python

## Import General Tools
from pathlib import Path
from astropy.table import Table

from telescopeSchedule import get_telsched


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main(ndays=5):
    sched = get_telsched(from_date=None, ndays=ndays, telnr=None)

    site_list = sorted(['ANU', 'CIT', 'UCB', 'UCD', 'UCLA', 'UCSD', 'UCI', 'UCR', 'Yale',
                        'USRA', 'NU', 'HQ', 'IfA', 'Stanford', 'Swinburne', 'UCSB', 'UCSC'])
    site_list.append('Other')

    t = Table(names=['Date', 'TelNr', 'ProjCode'] + site_list,
              dtype=['a12', 'a12', 'a12'] + ['a100']*len(site_list))

    for prog in sched:
        row = {site: '' for site in site_list}
        row['Date'] = prog['Date']
        row['TelNr'] = prog['TelNr']
        row['ProjCode'] = prog['ProjCode']
        tonights_observers = prog['Observers'].split(',')
        tonights_sites = prog['Location'].split(',')
        for obs,s in zip(tonights_observers, tonights_sites):
            if s in row.keys():
                row[s] += f"{obs}, "
            else:
                row['Other'] += f"{obs}, "
        for site in site_list:
            if row[site] != '':
                nobs = len(row[site].split(',')) - 1
                row[site] = row[site].strip(', ')
                row[site] += f' ({nobs})'
        t.add_row(row)

    print(t)

if __name__ == '__main__':
    main()
