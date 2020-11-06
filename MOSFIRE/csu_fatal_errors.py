#!python3

## Import General Tools
from pathlib import Path
import re
from datetime import datetime
import subprocess
from astropy.table import Table, Column
import numpy as np

from matplotlib import pyplot as plt


##-------------------------------------------------------------------------
## read_logs_for_fatal_errors
##-------------------------------------------------------------------------
def read_logs_for_fatal_errors():
    fatal_errors = Table(names=('Date-Time', 'ROTMODE', 'ROTPOSN', 'EL', 'bad', 'year'),
                         dtype=(np.dtype('S23'), np.dtype('S20'), np.float, np.float, np.bool, np.int))

    path_eavesdrop = Path('/s/sdata1300/logs/gui/eavesdrop/')
    match_str = '(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) \[mosfire\] DEBUG edu.ucla.astro.irlab.util.Property - Setting property <CSUStatus> to new value <FATAL ERROR >.'

#     years = ['15', '16', '17', '18', '19', '20']
    years = [15, 16, 17, 18, 19, 20]
    for year in years:
        nlogs = len([x for x in path_eavesdrop.glob(f'{year:02d}*.log')])
        print(f'Reading {nlogs} logs for 20{year}')
        for log_eavesdrop in path_eavesdrop.glob(f'{year}*.log'):

            try:
                with open(log_eavesdrop) as log_file:
                    log_contents = log_file.read()
                    lines = log_contents.split('\n')
            except:
                print(f'  Failed to read {log_eavesdrop}')
                lines = []

            for line in lines:
                is_fatal_error = re.match(match_str, line)
                if is_fatal_error is not None:
                    timestamp = datetime.strptime(f'{is_fatal_error.group(1)}000',
                                                  '%Y-%m-%d %H:%M:%S,%f')
                    cmd = ['gshow', '-s', 'dcs1',
                           'ROTMODE', 'ROTPOSN', 'EL',
                           '-window', '1s', '-csv',
                           '-date', timestamp.strftime('%Y-%m-%dT%H:%M:%S')]
                    output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                    try:
                        contents = output.stdout.decode()
                        dcsdata = Table.read(contents,
                                             format='ascii.csv', comment='#')
                        badcol = [ (abs(x['ROTPOSN']) < 10) or (abs(x['ROTPOSN']-180) < 10)
                                  or (abs(x['ROTPOSN']+180) < 10)
                                  for x in dcsdata]
                        dcsdata.add_column(Column(badcol, name='bad'))
                        dcsdata.add_column(Column([year]*len(dcsdata), name='year'))
                        fatal_errors.add_row(dcsdata[0])
                    except:
                        print('Failed to parse result:')
                        print(output.stdout)

    return fatal_errors


if __name__ == '__main__':
    csuerror_table_filename = Path('csu_fatal_errors.txt')

    # Read logs and write table file
    if csuerror_table_filename.exists() is False:
        fatal_errors = read_logs_for_fatal_errors()
        fatal_errors.write(csuerror_table_filename, format='ascii.csv')

    # Make plots
    fatal_errors = Table.read(csuerror_table_filename, format='ascii.csv')
    plt.figure(figsize=(12,8))

    by_year = fatal_errors.group_by('year')
    colors = {2015: 'k', 2016: 'k', 2017: 'y', 2018: 'b', 2019: 'g', 2020: 'r'}
    for i,yeardata in enumerate(by_year.groups):
        year = int(f'20{by_year.groups.keys[i][0]}')
        plt.plot(yeardata['ROTPOSN'], yeardata['EL'], f'{colors[year]}o',
                 alpha=0.20, label=year)
    plt.title('MOSFIRE CSU Fatal Errors')
    plt.xlabel('ROTPOSN')
    plt.ylabel('EL')
    plt.yticks(np.arange(0,100,10))
    plt.xticks(np.arange(-270,225,45))
    plt.grid()
    plt.legend(loc='best')
    plt.ylim(-1,91)
    plt.savefig('csu_fatal_errors.png')
