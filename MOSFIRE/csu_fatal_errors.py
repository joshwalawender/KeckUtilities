#!python3

## Import General Tools
import sys
import argparse
from pathlib import Path
import re
from datetime import datetime
import subprocess
from astropy.table import Table, Column, Row
import numpy as np
import subprocess

from matplotlib import pyplot as plt
import matplotlib.dates as mdates


##-------------------------------------------------------------------------
## Parse Command Line Arguments
##-------------------------------------------------------------------------
## create a parser object for understanding command-line arguments
p = argparse.ArgumentParser(description='''
''')
## add flags
p.add_argument("-n", "--nodcs", dest="nodcs",
    default=False, action="store_true",
    help="Do not query dcs keyword history for rotator position values")
args = p.parse_args()


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

#     cmd = ['grep', 'CSU', f'{logfile}']
#     output = subprocess.run(cmd, stdout=subprocess.PIPE)
#     lines = output.stdout.decode().split('\n')
#     print(f'Parsing {len(lines)} CSU lines in log file: {logfile.name}')

    lines = []
    try:
        with open(logfile) as log_file:
            log_contents = log_file.read()
            lines = log_contents.split('\n')
    except:
        print(f'  Failed to read {logfile}')

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
    setup_bars = []
    status = (None, None)
    xaccels = None
    yaccels = None
    for line in lines:

        if status[0] is None:
#             print(f'No Status: {line}')
            mstart_time = re.match('(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) \[', line)
            if mstart_time is not None:
                start_time = datetime.strptime(mstart_time.group(1), '%Y-%m-%d %H:%M:%S,%f')
#                 print(f'Found start time: {start_time}')
                status = ('Idle', start_time)
            continue

        if re.search('<CSU', line) is None:
#             print(f'Skipping: {line}')
            continue

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
        if status[0] != 'Error':
            status, history_entry = check_for_transition(line, status, pstart_setup, 'Setup')
            if history_entry is not None:
                if xaccels is not None and yaccels is not None:
                    history_entry['xaccels'] = xaccels
                    history_entry['yaccels'] = yaccels
                    history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
                status_history.append(history_entry)
                moving_bars = []

        # Check for new BarTarget
        if status[0] is not None:
            if status[0] == 'Setup':
                matched = pbartarget.match(line)
                if matched is not None:
                    setup_bars.append(matched.group(2))

        # Check for setup end
        if status[0] != 'Error':
            status, history_entry = check_for_transition(line, status, pend_setup, 'Idle')
            if history_entry is not None:
                history_entry['nbars'] = len(setup_bars)
                setup_bars = []
                if xaccels is not None and yaccels is not None:
                    history_entry['xaccels'] = xaccels
                    history_entry['yaccels'] = yaccels
                    history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
                status_history.append(history_entry)

        # Check for move start
        if status[0] != 'Error':
            status, history_entry = check_for_transition(line, status, pstart_move, 'Moving')
            if history_entry is not None:
                if xaccels is not None and yaccels is not None:
                    history_entry['xaccels'] = xaccels
                    history_entry['yaccels'] = yaccels
                    history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
                status_history.append(history_entry)
                moving_bars = []

        # Count moving bars
        if status[0] is not None:
            if status[0] == 'Moving':
                matched = pbarmoving.match(line)
                if matched is not None:
                    moving_bars.append(matched.group(2))

        # Check for move end
        if status[0] != 'Error':
            status, history_entry = check_for_transition(line, status, pend_move, 'Idle')
            if history_entry is not None:
                history_entry['nbars'] = len(moving_bars)
                moving_bars = []
                if xaccels is not None and yaccels is not None:
                    history_entry['xaccels'] = xaccels
                    history_entry['yaccels'] = yaccels
                    history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
                status_history.append(history_entry)

        # Check for fatal error
        status, history_entry = check_for_transition(line, status, pfatal_error, 'Error')
        if history_entry is not None:
            # Check what previous state was
            if len(status_history) > 1:
                if status_history[-1]['duration (s)'] >= 120:
                    print(f'  {history_entry["begin"]}: Fatal Error after: {status_history[-1]["status"]} ({status_history[-1]["duration (s)"]} s)')
                else:
                    print(f'  {history_entry["begin"]}: Fatal Error quickly after: {status_history[-1]["status"]} ({status_history[-1]["duration (s)"]} s)')
                    if len(status_history) > 2:
                        print(f'                      after: {status_history[-2]["status"]} ({status_history[-2]["duration (s)"]} s)')
            else:
                print(f'  {history_entry["begin"]}: Fatal Error')

            if history_entry['status'] == 'Moving':
                history_entry['nbars'] = len(moving_bars)
                moving_bars = []
            if xaccels is not None and yaccels is not None:
                history_entry['xaccels'] = xaccels
                history_entry['yaccels'] = yaccels
                history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)

        # Check for power cycle
        status, history_entry = check_for_transition(line, status, ppower_down, 'PowerDown')
        if history_entry is not None:
            if xaccels is not None and yaccels is not None:
                history_entry['xaccels'] = xaccels
                history_entry['yaccels'] = yaccels
                history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)

        # Check for initialization
        status, history_entry = check_for_transition(line, status, pinitialize, 'Initialize')
        if history_entry is not None:
            if xaccels is not None and yaccels is not None:
                history_entry['xaccels'] = xaccels
                history_entry['yaccels'] = yaccels
                history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)

        # Check for initialization complete
        status, history_entry = check_for_transition(line, status, pinitialize_complete, 'Idle')
        if history_entry is not None:
            if xaccels is not None and yaccels is not None:
                history_entry['xaccels'] = xaccels
                history_entry['yaccels'] = yaccels
                history_entry['accel age (s)'] = (status[1] - min([xaccel_time, xaccel_time])).total_seconds()
            status_history.append(history_entry)

    return status_history


##-------------------------------------------------------------------------
## get_dcs_keywords
##-------------------------------------------------------------------------
def get_dcs_keywords(timestamp):
    if args.nodcs is True:
        return {'ROTPOSN': 0, 'bad': False}

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
## Plot: acceleration values histogram
##-------------------------------------------------------------------------
def plot_accel(history_table):
    print('Plotting acceleration histograms')
    moves = history_table[history_table['status'] == 'Moving']
    successful_moves = moves[moves['MoveFailed'] == 'False']
    failed_moves = moves[moves['MoveFailed'] == 'True']

    plt.figure(figsize=(12,12))

    bins = np.arange(0,10000,100)
    ax = plt.subplot(2,1,1)
    plt.title('Acceleration Values')
    n, bins, _ = ax.hist(successful_moves['xaccels'], bins=bins, color='g', alpha=0.4,
                         label=f'Successful Moves ({len(successful_moves)})')
    ax.hist(failed_moves['xaccels'], bins=bins, color='r', alpha=0.1,
            label=f'Failed Moves ({len(failed_moves)})')
    ax.set_ylim(0, max(n)*1.1)
    ax.set_ylabel('N Successful Moves')
    plt.legend(loc='best')
    failed_ax = ax.twinx()
    fn, fbins, _ = failed_ax.hist(failed_moves['xaccels'], bins=bins, color='r', alpha=0.4,
                                  label=f'Failed Moves ({len(failed_moves)})')
    failed_ax.set_ylim(0, max(n)*1.1/50)
    failed_ax.set_ylabel('N Failed Moves')
    plt.xlabel('xaccel')
    plt.xlim(1000,9000)
    plt.grid()

    ax = plt.subplot(2,1,2)
    n, bins, _ = plt.hist(successful_moves['yaccels'], bins=bins, color='g', alpha=0.4,
                          label=f'Successful Moves ({len(successful_moves)})')
    plt.hist(failed_moves['yaccels'], bins=bins, color='r', alpha=0.1,
             label=f'Failed Moves ({len(failed_moves)})')
    plt.legend(loc='best')
    ax.set_ylim(0, max(n)*1.1)
    ax.set_ylabel('N Successful Moves')

    failed_ax = ax.twinx()
    plt.hist(failed_moves['yaccels'], bins=bins, color='r', alpha=0.4,
             label=f'Failed Moves ({len(failed_moves)})')
    failed_ax.set_ylim(0, max(n)*1.1/50)
    failed_ax.set_ylabel('N Failed Moves')

    plt.xlabel('yaccel')
    plt.xlim(1000,9000)
    plt.grid()

    plot_file = Path('acceleration_values.png')
    plt.savefig(plot_file, bbox_inches='tight', pad_inches=0.10)
#     plt.show()


##-------------------------------------------------------------------------
## Plot: nbars in move
##-------------------------------------------------------------------------
def plot_nbars(history_table):
    print('Plotting nbars in move')
    moves = history_table[history_table['status'] == 'Moving']

    successful_moves = moves[moves['MoveFailed'] == 'False']
    failed_moves = moves[moves['MoveFailed'] == 'True']
    time_successful_moves = [datetime.strptime(x[:19], '%Y-%m-%d %H:%M:%S')\
                             for x in successful_moves['begin']]
    time_failed_moves = [datetime.strptime(x[:19], '%Y-%m-%d %H:%M:%S')\
                         for x in failed_moves['begin']]

    plt.figure(figsize=(12,12))

    ax = plt.subplot(2,1,1)
    plt.title('Number of Bars Moving')
    bins = np.arange(0,92,1)
    n, bins, _ = plt.hist(successful_moves['nbars'], bins=bins, color='g', alpha=0.4,
                          label=f'Successful Moves ({len(successful_moves)})')
    plt.hist(failed_moves['nbars'], bins=bins, color='r', alpha=0.1,
             label=f'Failed Moves ({len(failed_moves)})')
    plt.legend(loc='best')
    ax.set_ylim(0, max(n)*1.1)
    ax.set_ylabel('N Successful Moves')

    failed_ax = ax.twinx()
    plt.hist(failed_moves['nbars'], bins=bins, color='r', alpha=0.4,
             label=f'Failed Moves ({len(failed_moves)})')
    failed_ax.set_ylim(0, max(n)*1.1/50)
    failed_ax.set_ylabel('N Failed Moves')

    plt.xlabel('Number of Bars')
    plt.xlim(0,93)
    plt.grid()

    plt.subplot(2,1,2)
    plt.title('Behavior over Time')
    plt.plot(time_successful_moves, successful_moves['nbars'], 'go',
             alpha=0.2, mew=0, label=f'Successful Moves ({len(successful_moves)})')
    plt.plot(time_failed_moves, failed_moves['nbars'], 'rv',
             alpha=0.4, ms=10, label=f'Failed Moves ({len(failed_moves)})')
    plt.xlabel('Time')
    plt.ylabel('Number of Bars')
    plt.ylim(-1,93)
    plt.grid()
    plt.legend(loc='best')

    plot_file = Path('number_of_bars_moving.png')
    plt.savefig(plot_file, bbox_inches='tight', pad_inches=0.10)
#     plt.show()


##-------------------------------------------------------------------------
## Plot: rotator position in move vs. time (color code failures)
##-------------------------------------------------------------------------
def plot_rotposn(history_table):
    print('Plotting rotator position in move')
    moves = history_table[history_table['status'] == 'Moving']
    successful_moves = moves[moves['MoveFailed'] == 'False']
    failed_moves = moves[moves['MoveFailed'] == 'True']
    time_successful_moves = [datetime.strptime(x[:19], '%Y-%m-%d %H:%M:%S')\
                             for x in successful_moves['begin']]
    time_failed_moves = [datetime.strptime(x[:19], '%Y-%m-%d %H:%M:%S')\
                         for x in failed_moves['begin']]
    t0 = time_successful_moves[0]
    t1 = time_successful_moves[-1]

    plt.figure(figsize=(12,12))

    ax = plt.subplot(2,1,1)
    plt.title('Rotator Angle')
    bins = np.arange(-450,360,10)
    n, bins, _ = plt.hist(successful_moves['ROTPOSN'], bins=bins, color='g', alpha=0.4,
                          label=f'Successful Moves ({len(successful_moves)})')
    plt.hist(failed_moves['ROTPOSN'], bins=bins, color='r', alpha=0.1,
             label=f'Failed Moves ({len(failed_moves)})')
    plt.legend(loc='best')
    ax.set_ylim(0, max(n)*1.1)
    ax.set_ylabel('N Successful Moves')

    failed_ax = ax.twinx()
    plt.hist(failed_moves['ROTPOSN'], bins=bins, color='r', alpha=0.4,
             label=f'Failed Moves ({len(failed_moves)})')
    failed_ax.set_ylim(0, max(n)*1.1/50)
    failed_ax.set_ylabel('N Failed Moves')

    plt.axvspan(170, 190, color='r', alpha=0.1)
    plt.axvspan(-10, 10, color='r', alpha=0.1)
    plt.axvspan(-190, -170, color='r', alpha=0.1)
    plt.axvspan(-370, -350, color='r', alpha=0.1)

    plt.xlabel('ROTPPOSN')
    plt.xticks(np.arange(-390,390,30))
    plt.ylabel('N Moves')
    plt.grid()

    plt.subplot(2,1,2)
    plt.plot(time_successful_moves, successful_moves['ROTPOSN'], 'go',
             alpha=0.2, mew=0, label=f'Successful Moves ({len(successful_moves)})')
    plt.plot(time_failed_moves, failed_moves['ROTPOSN'], 'rv',
             alpha=0.4, ms=10, label=f'Failed Moves ({len(failed_moves)})')
    plt.axhspan(170, 190, xmin=0, xmax=1, color='r', alpha=0.2)
    plt.axhspan(-10, 10, xmin=0, xmax=1, color='r', alpha=0.2)
    plt.axhspan(-190, -170, xmin=0, xmax=1, color='r', alpha=0.2)
    plt.axhspan(-370, -350, xmin=0, xmax=1, color='r', alpha=0.2)
    plt.xlabel('Time')
    plt.ylabel('ROTPOSN')
    plt.yticks(np.arange(-450,390,90))
    plt.grid()
    plt.legend(loc='best')

    plot_file = Path('rotator_position.png')
    plt.savefig(plot_file, bbox_inches='tight', pad_inches=0.10)
#     plt.show()


##-------------------------------------------------------------------------
## Plot: failure rate vs. time
##-------------------------------------------------------------------------
def plot_fail_rate(history_table):
    print('Plotting failure rate vs. time')
    moves = history_table[history_table['status'] == 'Moving']
    successful_moves = moves[moves['MoveFailed'] == 'False']
    failed_moves = moves[moves['MoveFailed'] == 'True']
    time_successful_moves = [datetime.strptime(x[:19], '%Y-%m-%d %H:%M:%S')\
                             for x in successful_moves['begin']]
    time_failed_moves = [datetime.strptime(x[:19], '%Y-%m-%d %H:%M:%S')\
                         for x in failed_moves['begin']]
    t0 = time_successful_moves[0]
    t1 = time_successful_moves[-1]

    plt.figure(figsize=(12,12))
    ax = plt.subplot(2,1,1)
    n, bins, _ = plt.hist(mdates.date2num(time_successful_moves),
                          bins=50, color='g', alpha=0.4,
                          label=f'Successful Moves ({len(successful_moves)})')
    nf, bins, _ = plt.hist(mdates.date2num(time_failed_moves),
                           bins=bins, color='r', alpha=0.1,
                           label=f'Failed Moves ({len(failed_moves)})')
    plt.legend(loc='best')
    ax.set_ylim(0, max(n)*1.1)
    ax.set_ylabel('N Successful Moves')
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xlabel('Time')
    plt.grid()

    failed_ax = ax.twinx()
    plt.hist(mdates.date2num(time_failed_moves),
             bins=bins, color='r', alpha=0.4,
             label=f'Failed Moves ({len(failed_moves)})')
    failed_ax.set_ylim(0, max(n)*1.1/50)
    failed_ax.set_ylabel('N Failed Moves')

    ax = plt.subplot(2,1,2)
    failrate = [nf[i]/n[i]*100 if n[i] > 0 else 0 for i,s in enumerate(n)]
    plt.plot(bins[1:], failrate, 'r-', drawstyle='steps-mid')
    plt.plot(bins[1:], [0]*len(bins[1:]), 'k-', drawstyle='steps-mid', alpha=0.5)
    ax.set_ylabel('Move Failure Rate (%)')
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xlabel('Time')
    plt.grid()

    plot_file = Path('failure_rate.png')
    plt.savefig(plot_file, bbox_inches='tight', pad_inches=0.10)



##-------------------------------------------------------------------------
## __main__
##-------------------------------------------------------------------------
if __name__ == '__main__':

    history_file = Path('history_table.txt')
    fatal_errors = list()
    status_history = list()

    if history_file.exists() is False:
#         status = parse_eavesdrop_log(Path('190614_1919_eavesdrop.log'))
#         status_history.extend( status )

        path_eavesdrop = Path('/s/sdata1300/logs/gui/eavesdrop/')
#         status = parse_eavesdrop_log(path_eavesdrop.joinpath('190614_1919_eavesdrop.log'))
#         status_history.extend( status )

        years = [15, 16, 17, 18, 19, 20]
        for year in years:
            logfiles = [x for x in path_eavesdrop.glob(f'{year:02d}*.log')]
            nlogs = len(logfiles)
            print(f'Reading {nlogs} logs for 20{year}')
            for log_eavesdrop in logfiles:
                status = parse_eavesdrop_log(log_eavesdrop)
                status_history.extend( status )

        history_table = Table(status_history)
        move_failed = np.zeros(len(history_table), dtype=bool)
        for i,event in enumerate(history_table):
            if event['status'] == 'Error':
                last_status = history_table[i-1]['status']
                if last_status == 'Moving':
                    move_failed[i-1] = True
        history_table.add_column(Column(move_failed, name='MoveFailed'))
        history_table.write(history_file, format='ascii.fixed_width', overwrite=True)
    else:
        print(f'Reading: {history_file}')
        history_table = Table.read(history_file, format='ascii.fixed_width')
        plot_nbars(history_table)
        plot_rotposn(history_table)
        plot_accel(history_table)
        plot_fail_rate(history_table)