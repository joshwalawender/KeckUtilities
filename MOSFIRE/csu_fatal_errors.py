#!python3

## Import General Tools
import sys
from pathlib import Path
import re
from datetime import datetime
import subprocess
from astropy.table import Table, Column, Row
import numpy as np

from matplotlib import pyplot as plt


##-------------------------------------------------------------------------
## parse_eavesdrop_log
##-------------------------------------------------------------------------
def check_for_transition(line, status, pattern, new_state):
    matched = pattern.match(line)
    if matched is not None:
        transition_time = datetime.strptime(matched.group(1), '%Y-%m-%d %H:%M:%S,%f')
        duration = (transition_time-status[1]).total_seconds()
        dcs1 = get_dcs_keywords(status[1])
        dcs2 = get_dcs_keywords(transition_time)
        history_entry = {'status': status[0],
                         'begin': status[1],
                         'end': transition_time,
                         'duration (s)': duration,
                         'xaccels': -1,
                         'yaccels': -1,
                         'accel age (s)': -1,
                         'ROTPOSN': dcs1['ROTPOSN'],
                         'ROTPOSN end': dcs2['ROTPOSN'],
                         'bad': dcs1['bad'],
                         'nbars': 0,
                         }
        return (new_state, transition_time), history_entry
    else:
        return status, None


def parse_eavesdrop_log(logfile):
    print(f'Parsing log file: {logfile.name}')
    try:
        with open(logfile) as log_file:
            log_contents = log_file.read()
            lines = log_contents.split('\n')
    except:
        print(f'  Failed to read {logfile}')
        lines = []

    match_str = ('(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) \[mosfire\] DEBUG '
                 'edu.ucla.astro.irlab.util.Property - Setting property ')

    pxaccel = re.compile(match_str+'<CSUXAccelerometer> to new value <(\d+)>')
    pyaccel = re.compile(match_str+'<CSUYAccelerometer> to new value <(\d+)>')

    pstart_setup = re.compile(match_str+'<CSUSetupMaskName> to new value <(.+)>')
    pbartarget = re.compile(match_str+'<CSUBarTargetPosition(\d\d)> to new value <([\d\.]+)>.')
    pend_setup = re.compile(match_str+'<CSUStatus> to new value <Setup complete.>')

    pstart_move = re.compile(match_str+'<CSUStatus> to new value <Starting group move.>')
    pbarmoving = re.compile(match_str+'<CSUBarStatus(\d+)> to new value <MOVING>.')
    pend_move = re.compile(match_str+'<CSUStatus> to new value <Move completed.  Ready for next move.>')
    pfatal_error = re.compile(match_str+'<CSUStatus> to new value <FATAL ERROR >')
    ppower_down = re.compile(match_str+'<CSUStatus> to new value <Powering down CSU system>')
    pinitialize = re.compile(match_str+'<CSUStatus> to new value <Bar initialization command sent.>')
    pinitialize_complete = re.compile(match_str+'<CSUStatus> to new value <Initialization complete.>')

    status_history = list()
    xaccels = 0
    yaccels = 0
    moving_bars = []
    status = None
    for line in lines:
#         print(line)

        if status is None:
            mstart_time = re.match('(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) \[', line)
            if mstart_time is not None:
                start_time = datetime.strptime(mstart_time.group(1), '%Y-%m-%d %H:%M:%S,%f')
#                 print(f'Found start time: {start_time}')
                status = ('Idle', start_time)

        # Read Xaccel and Yaccel
        mxaccel = pxaccel.match(line)
        if mxaccel is not None:
            xaccel_time = datetime.strptime(mxaccel.group(1), '%Y-%m-%d %H:%M:%S,%f')
            xaccels = int(mxaccel.group(2))
        myaccel = pyaccel.match(line)
        if myaccel is not None:
            yaccel_time = datetime.strptime(myaccel.group(1), '%Y-%m-%d %H:%M:%S,%f')
            yaccels = int(myaccel.group(2))
#             print(f'Accelerations ({status[0]}): {xaccels} {yaccels} ({yaccel_time.strftime("%Y-%m-%d %H:%M:%S")})')

        # Check for Setup start
        status, history_entry = check_for_transition(line, status, pstart_setup, 'Setup')
        if history_entry is not None:
            history_entry['xaccels'] = xaccels
            history_entry['yaccels'] = yaccels
            history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)
            moving_bars = []

        # Check for new BarTarget
#         if status is not None:
#             if status[0] == 'Setup':
#                 matched = pbartarget.match(line)
#                 if matched is not None:
#                     moving_bars.append(matched.group(2))

        # Check for setup end
        status, history_entry = check_for_transition(line, status, pend_setup, 'Idle')
        if history_entry is not None:
            history_entry['xaccels'] = xaccels
            history_entry['yaccels'] = yaccels
            history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)

        # Check for move start
        status, history_entry = check_for_transition(line, status, pstart_move, 'Moving')
        if history_entry is not None:
            history_entry['xaccels'] = xaccels
            history_entry['yaccels'] = yaccels
            history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)
            moving_bars = []

        # Count moving bars
        if status is not None:
            if status[0] == 'Moving':
                matched = pbarmoving.match(line)
                if matched is not None:
                    moving_bars.append(matched.group(2))

        # Check for move end
        status, history_entry = check_for_transition(line, status, pend_move, 'Idle')
        if history_entry is not None:
            history_entry['nbars'] = len(moving_bars)
            moving_bars = []
            history_entry['xaccels'] = xaccels
            history_entry['yaccels'] = yaccels
            history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)

        # Check for fatal error
        status, history_entry = check_for_transition(line, status, pfatal_error, 'Error')
        if history_entry is not None:
            if history_entry['status'] == 'Moving':
                history_entry['nbars'] = len(moving_bars)
                moving_bars = []
            history_entry['xaccels'] = xaccels
            history_entry['yaccels'] = yaccels
            history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)

        # Check for power cycle
        status, history_entry = check_for_transition(line, status, ppower_down, 'PowerDown')
        if history_entry is not None:
            history_entry['xaccels'] = xaccels
            history_entry['yaccels'] = yaccels
            history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)

        # Check for initialization
        status, history_entry = check_for_transition(line, status, pinitialize, 'Initialize')
        if history_entry is not None:
            history_entry['xaccels'] = xaccels
            history_entry['yaccels'] = yaccels
            history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)

        # Check for initialization complete
        status, history_entry = check_for_transition(line, status, pinitialize_complete, 'Idle')
        if history_entry is not None:
            history_entry['xaccels'] = xaccels
            history_entry['yaccels'] = yaccels
            history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)

    return status_history


##-------------------------------------------------------------------------
## get_dcs_keywords
##-------------------------------------------------------------------------
def get_dcs_keywords(timestamp):
    cmd = ['gshow', '-s', 'dcs1',
           'ROTMODE', 'ROTPOSN', 'EL',
           '-window', '1s', '-csv',
           '-date', timestamp.strftime('%Y-%m-%dT%H:%M:%S')]
    output = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

    try:
        contents = output.stdout.decode()
        dcsdata = Table.read(contents,
                             format='ascii.csv', comment='#')
    except:
        print('Failed to parse result:')
        print(" ".join(cmd))
        print(output.stdout.decode())
        print('-'*40)

    badcol = [ (abs(x['ROTPOSN']) < 10) or (abs(x['ROTPOSN']-180) < 10)
              or (abs(x['ROTPOSN']+180) < 10)
              for x in dcsdata]
    dcsdata.add_column(Column(badcol, name='bad'))
    year = dcsdata['Date-Time'][0][:4]
    dcsdata.add_column(Column([year]*len(dcsdata), name='year'))
    dcsdata.remove_column('Date-Time')

    result = dict()
    for key in dcsdata.colnames:
        result[key] = dcsdata[0][key]
    return result


##-------------------------------------------------------------------------
## get_bar_keywords
##-------------------------------------------------------------------------
def get_csu_keywords(timestamp):
    cmd = ['gshow', '-s', 'mcsus',
           'B%STAT', 'B%TARG', 'B%POS',
           '-window', '30s', '-csv',
           '-date', timestamp.strftime('%Y-%m-%dT%H:%M:%S')]
    output = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    try:
        contents = output.stdout.decode()
        csudata = Table.read(contents,
                             format='ascii.csv', comment='#')
    except:
        print('Failed to parse result:')
        print(output.stdout)

    result = dict()
    for colname in csudata[-1].colnames:
        result[colname] = csudata[-1][colname]

    # Get SETUPNAME and MASKNAME
    cmd = ['gshow', '-s', 'mcsus',
           'SETUPNAME', 'MASKNAME',
           '-window', '30s', '-csv',
           '-date', timestamp.strftime('%Y-%m-%dT%H:%M:%S')]
    output = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    try:
        contents = output.stdout.decode()
        namedata = Table.read(contents,
                              format='ascii.csv', comment='#')
        result['setupname'] = str(namedata[0]['SETUPNAME'])
        result['maskname'] = str(namedata[0]['MASKNAME'])
    except:
        print('Failed to parse result:')
        print(" ".join(cmd))
        print(output.stdout.decode())
        sys.exit(0)
        result['setupname'] = ''
        result['maskname'] = ''
    
    return result


##-------------------------------------------------------------------------
## read_logs_for_fatal_errors
##-------------------------------------------------------------------------
def old_read_logs_for_fatal_errors():
    rotator = Table(names=('Date-Time', 'ROTMODE', 'ROTPOSN', 'EL', 'bad', 'year'),
                    dtype=(np.dtype('S23'), np.dtype('S20'), np.float, np.float, np.bool, np.int))

    names = ['Date-Time', 'setupname', 'maskname']
    dtype = [np.dtype('S23'), np.dtype('S23'), np.dtype('S23')]
    names.extend( [f'B{i:02d}STAT' for i in range(1,93)] )
    dtype.extend( [np.dtype('S10') for i in range(1,93)] )
    names.extend( [f'B{i:02d}TARG' for i in range(1,93)] )
    dtype.extend( [np.float for i in range(1,93)] )
    names.extend( [f'B{i:02d}POS' for i in range(1,93)] )
    dtype.extend( [np.float for i in range(1,93)] )
    csu = Table(names=names, dtype=dtype)

    path_eavesdrop = Path('/s/sdata1300/logs/gui/eavesdrop/')
    match_str = ('(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) \[mosfire\] DEBUG '
                 'edu.ucla.astro.irlab.util.Property - Setting property '
                 '<CSUStatus> to new value <FATAL ERROR >.')

    table = list()
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
                    print(f'  Fatal error at {timestamp.strftime("%Y-%m-%d %H:%M:%S")}')
                    csudata = get_csu_keywords(timestamp)
                    dcsdata = get_dcs_keywords(timestamp)
                    csudata.update(dcsdata)
                    table.append(csudata)

    return Table(table)


def old_main():
    table_filename = Path('fatal_errors.txt')
    # Read logs and write table file
    if table_filename.exists() is False:
        table = read_logs_for_fatal_errors()
        table.write(table_filename, format='ascii.csv')

    # Make plot of Fatal Errors and Rotator Angle
    table = Table.read(table_filename, format='ascii.csv')
    print(table)

    plt.figure(figsize=(12,8))
    by_year = table.group_by('year')
    colors = {2015: 'k', 2016: 'k', 2017: 'y', 2018: 'b', 2019: 'g', 2020: 'r'}
    for i,yeardata in enumerate(by_year.groups):
        year = int(f'{by_year.groups.keys[i][0]}')
        plt.plot(yeardata['ROTPOSN'], yeardata['EL'], f'{colors[year]}o',
                 alpha=0.20, label=f'{year} ({len(yeardata)} errors)')
    plt.axvspan(-190,-170, color='r', alpha=0.2)
    plt.axvspan(-10,10, color='r', alpha=0.2)
    plt.axvspan(170,190, color='r', alpha=0.2)
    plt.title('MOSFIRE CSU Fatal Errors')
    plt.xlabel('ROTPOSN')
    plt.ylabel('EL')
    plt.yticks(np.arange(0,100,10))
    plt.xticks(np.arange(-270,225,45))
    plt.grid()
    plt.legend(loc='best')
    plt.ylim(-1,91)
    plt.savefig('csu_fatal_errors.png')


def plot_rotator(history_table):
    plt.figure(figsize=(12,12))
#     plt.plot



if __name__ == '__main__':

    history_file = Path('history_table.txt')
    fatal_errors = list()
    status_history = list()

    if history_file.exists() is False:
        path_eavesdrop = Path('/s/sdata1300/logs/gui/eavesdrop/')
#         status = parse_eavesdrop_log(path_eavesdrop.joinpath('201129_1803_eavesdrop.log'))
#         status_history.extend( status )

#         years = [20]
        years = [15, 16, 17, 18, 19, 20]
        for year in years:
            nlogs = len([x for x in path_eavesdrop.glob(f'{year:02d}*.log')])
            print(f'Reading {nlogs} logs for 20{year}')
            for log_eavesdrop in path_eavesdrop.glob(f'{year}*.log'):
                status = parse_eavesdrop_log(log_eavesdrop)
                status_history.extend( status )

        history_table = Table(status_history)
        print(history_table)
        history_table.write(history_file, format='ascii.fixed_width', overwrite=True)

    print(f'Reading: {history_file}')
    history_table = Table.read(history_file, format='ascii.fixed_width')
    print(history_table)