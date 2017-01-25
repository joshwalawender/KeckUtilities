from __future__ import division, print_function

## Import General Tools
import sys
import os

from astropy.table import Table, Column

import matplotlib.pyplot as plt
import matplotlib as mpl
mpl.rcParams['font.size'] = 24

def main():
    history_file = 'HIRES_history.csv'
    sched = Table.read(history_file, format='ascii.csv', guess=False)
    year = [int(x[0:4]) for x in sched['Date']]
    sched.add_column(Column(year, name='year'))
    nightfrac = [1./min([2,len(x.split('/'))]) for x in sched['Instrument']]
    sched.add_column(Column(nightfrac, name='fraction'))
    
    years = []
    nights = []
    byyear = sched.group_by('year')
    for i,val in enumerate(byyear.groups):
        years.append(byyear.groups[i]['year'][0])
        nights.append(sum(byyear.groups[i]['fraction']))
    
    plt.figure(figsize=(16,9))
    plt.bar(years, nights, width=0.8)
    plt.xlabel('Year')
    plt.ylabel('Nights / Year')
    plt.xlim(1993,2018)
    plt.grid()
    plt.savefig('HIRES.png', dpi=72, bbox_inches='tight', pad_inches=0.1)
    
    
if __name__ == '__main__':
    main()
