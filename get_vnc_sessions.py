#!/usr/env/python

## Import General Tools
import sys
import re
import argparse
import logging
import yaml
from getpass import getpass
import paramiko
import subprocess
from time import sleep
from threading import Thread
from telnetlib import Telnet
from subprocess import Popen
from astropy.table import Table, Column

from gooey import Gooey, GooeyParser


##-------------------------------------------------------------------------
## Create logger object
##-------------------------------------------------------------------------
log = logging.getLogger('GetVNCs')
log.setLevel(logging.DEBUG)
## Set up console output
LogConsoleHandler = logging.StreamHandler()
LogConsoleHandler.setLevel(logging.DEBUG)
LogFormat = logging.Formatter('%(asctime)23s %(levelname)8s: %(message)s')
LogConsoleHandler.setFormatter(LogFormat)
log.addHandler(LogConsoleHandler)


##-------------------------------------------------------------------------
## Get Configuration
##-------------------------------------------------------------------------
def get_config(filename='keck_vnc_config.yaml'):
    with open(filename) as FO:
        config = yaml.load(FO)

    assert 'servers_to_try' in config.keys()
    assert 'vncviewer' in config.keys()

    return config


##-------------------------------------------------------------------------
## Launch xterm
##-------------------------------------------------------------------------
def launch_xterm(command, pw, title):
    cmd = ['xterm', '-hold', '-title', title, '-e', f'"{command}"']
    xterm = subprocess.call(cmd)


##-------------------------------------------------------------------------
## Launch vncviewer
##-------------------------------------------------------------------------
def launch_vncviewer(vncserver, port, pw=None):
    config = get_config()
    cmd = [config['vncviewer'], f'{vncserver}:59{port:02d}']
    log.info(f"  {' '.join(cmd)}")
    vncviewer = subprocess.call(cmd)


##-------------------------------------------------------------------------
## Authenticate
##-------------------------------------------------------------------------
def authenticate(authpass):
    config = get_config()
    assert 'firewall_user' in config.keys()
    assert 'firewall_address' in config.keys()
    assert 'firewall_port' in config.keys()
    firewall_user = config.get('firewall_user')
    firewall_address = config.get('firewall_address')
    firewall_port = config.get('firewall_port')
    with Telnet(firewall_address, int(firewall_port)) as tn:
        tn.read_until(b"User: ", timeout=5)
        tn.write(f'{firewall_user}\n'.encode('ascii'))
        tn.read_until(b"password: ", timeout=5)
        tn.write(f'{authpass}\n'.encode('ascii'))
        tn.read_until(b"Enter your choice: ", timeout=5)
        tn.write('1\n'.encode('ascii'))
        result = tn.read_all().decode('ascii')
        if re.search('User authorized for standard services', result):
            log.info(result)
            return True
        else:
            log.error(result)
            return None


def close_authentication(authpass):
    config = get_config()
    assert 'firewall_user' in config.keys()
    assert 'firewall_address' in config.keys()
    assert 'firewall_port' in config.keys()
    firewall_user = config.get('firewall_user')
    firewall_address = config.get('firewall_address')
    firewall_port = config.get('firewall_port')
    with Telnet(firewall_address, int(firewall_port)) as tn:
        tn.read_until(b"User: ", timeout=5)
        tn.write(f'{firewall_user}\n'.encode('ascii'))
        tn.read_until(b"password: ", timeout=5)
        tn.write(f'{authpass}\n'.encode('ascii'))
        tn.read_until(b"Enter your choice: ", timeout=5)
        tn.write('2\n'.encode('ascii'))
        result = tn.read_all().decode('ascii')
        if re.search('User was signed off from all services', result):
            log.info(result)
            return True
        else:
            log.error(result)
            return None


##-------------------------------------------------------------------------
## Determine Instrument
##-------------------------------------------------------------------------
def determine_instrument(accountname):
    accounts = {'mosfire': [f'mosfire{i}' for i in range(1,10)],
                'hires': [f'hires{i}' for i in range(1,10)],
                'osiris': [f'osiris{i}' for i in range(1,10)],
                'lris': [f'lris{i}' for i in range(1,10)],
                'nires': [f'nires{i}' for i in range(1,10)],
                'deimos': [f'deimos{i}' for i in range(1,10)],
                'esi': [f'esi{i}' for i in range(1,10)],
                'nirc2': [f'nirc{i}' for i in range(1,10)],
                'nirspec': [f'nirspec{i}' for i in range(1,10)],
                'kcwi': [f'kcwi{i}' for i in range(1,10)],
               }
    accounts['mosfire'].append('moseng')
    accounts['hires'].append('hireseng')
    accounts['osiris'].append('osiriseng')
    accounts['lris'].append('lriseng')
    accounts['nires'].append('nireseng')
    accounts['deimos'].append('dmoseng')
    accounts['esi'].append('esieng')
    accounts['nirc2'].append('nirceng')
    accounts['nirspec'].append('nirspeceng')
    accounts['kcwi'].append('kcwieng')

    telescope = {'mosfire': 1,
                 'hires': 1,
                 'osiris': 1,
                 'lris': 1,
                 'nires': 2,
                 'deimos': 2,
                 'esi': 2,
                 'nirc2': 2,
                 'nirspec': 2,
                 'kcwi': 2,
                }

    for instrument in accounts.keys():
        if accountname.lower() in accounts[instrument]:
            return instrument, telescope[instrument]


##-------------------------------------------------------------------------
## Determine VNC Server
##-------------------------------------------------------------------------
def determine_VNCserver(accountname, password):
    config = get_config()
    servers_to_try = config.get('servers_to_try')
    vncserver = None
    for s in servers_to_try:
        try:
            log.info(f'Trying {s}:')
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.WarningPolicy())
            client.connect(f"{s}.keck.hawaii.edu", port=22, timeout=6,
                           username=accountname, password=password)
            log.info('  Connected')
        except TimeoutError:
            log.info('  Timeout')
        except:
            log.info('  Failed')
        else:
            stdin, stdout, stderr = client.exec_command('kvncinfo -server')
            rawoutput = stdout.read()
            vncserver = rawoutput.decode().strip('\n')
        finally:
            client.close()
            if vncserver is not None:
                log.info(f"Got VNC server: {vncserver}")
                break
    return vncserver


##-------------------------------------------------------------------------
## Determine VNC Sessions
##-------------------------------------------------------------------------
def determine_VNC_sessions(accountname, password, vncserver):
    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy())
        client.connect(f"{vncserver}.keck.hawaii.edu", port=22, timeout=6,
                       username=accountname, password=password)
        log.info('  Connected')
    except TimeoutError:
        log.info('  Timeout')
    except:
        log.info('  Failed')
    else:
        stdin, stdout, stderr = client.exec_command('kvncstatus')
        rawoutput = stdout.read()
        output = rawoutput.decode().strip('\n')
        allsessions = Table.read(output.split('\n'), format='ascii')
        sessions = allsessions[allsessions['User'] == accountname]
        names = [x['Desktop'].split('-')[2] for x in sessions]
        sessions.add_column(Column(data=names, name=('name')))
    finally:
        client.close()
        return sessions


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
# @Gooey
def main(args, config):
    ##-------------------------------------------------------------------------
    ## Authenticate Through Firewall (or Disconnect)
    ##-------------------------------------------------------------------------
    if config['authenticate'] is True:
        authenticate(args.firewall)


    ##-------------------------------------------------------------------------
    ## Determine instrument
    ##-------------------------------------------------------------------------
    instrument, tel = determine_instrument(args.account)


    ##-------------------------------------------------------------------------
    ## Determine VNC server
    ##-------------------------------------------------------------------------
    vncserver = determine_VNCserver(args.account, args.password)


    ##-------------------------------------------------------------------------
    ## Determine VNC Sessions
    ##-------------------------------------------------------------------------
    sessions = determine_VNC_sessions(args.account, args.password, vncserver)
    if len(sessions) == 0:
        log.info('No VNC sessions found')
        return

    print(sessions.pprint())

    ##-------------------------------------------------------------------------
    ## Open SSH Tunnel for Appropriate Ports
    ##-------------------------------------------------------------------------
    if config['authenticate'] is True:
        ssh_threads = []
        ports_in_use = []
        for session in sessions:
            if session['name'] in sessions_to_open:
                log.info(f"Opening SSH tunnel for {session['name']}")
                port = int(session['Display'][1:])
                ports_in_use.append(port)
                sshcmd = f"ssh {args.account}@{vncserver}.keck.hawaii.edu -L "+\
                        f"59{port:02d}:{vncserver}.keck.hawaii.edu:59{port:02d} -N"
                log.info(f"Opening xterm for {session['Desktop']}")
                ssh_threads.append(Thread(target=launch_xterm, args=(f'"{sshcmd}"',
                                   args.password, session['Desktop'])))
                ssh_threads[-1].start()
        if args.status is True:
            statusport = [p for p in range(1,10,1) if p not in ports_in_use][0]
            sshcmd = f"ssh {args.account}@svncserver{tel}.keck.hawaii.edu -L "+\
                     f"5901:svncserver{tel}.keck.hawaii.edu:59{statusport:02d} -N"
            log.info(f"Opening xterm for k{tel}status")
            ssh_threads.append(Thread(target=launch_xterm, args=(f'"{sshcmd}"',
                               args.password, f"k{tel}status")))
            ssh_threads[-1].start()
        cont = input('Hit any key when password has been entered.')

    ##-------------------------------------------------------------------------
    ## Open vncviewers
    ##-------------------------------------------------------------------------
    vnc_threads = []
    if config['authenticate'] is True:
        vncserver = 'localhost'
    for session in sessions:
        if session['name'] in sessions_to_open:
            log.info(f"Opening VNCviewer for {session['name']}")
            port = int(session['Display'][1:])
            vnc_threads.append(Thread(target=launch_vncviewer,
                                      args=(vncserver, port,)))
            vnc_threads[-1].start()
    if args.status is True:
        log.info(f"Opening VNCviewer for k{tel}status")
        vnc_threads.append(Thread(target=launch_vncviewer, args=(statusport,)))
        vnc_threads[-1].start()


##-------------------------------------------------------------------------
## __main__
##-------------------------------------------------------------------------
if __name__ == '__main__':
    ## create a parser object for understanding command-line arguments
    parser = GooeyParser(
             description="Get VNC sessions.")
    ## add flags
    parser.add_argument("--control0", dest="control0",
        default=True, action="store_true",
        help="Open control0?")
    parser.add_argument("--control1", dest="control1",
        default=True, action="store_true",
        help="Open control1?")
    parser.add_argument("--control2", dest="control2",
        default=True, action="store_true",
        help="Open control2?")
    parser.add_argument("--telstatus", dest="telstatus",
        default=False, action="store_true",
        help="Open telstatus?")
    parser.add_argument("--analysis0", dest="analysis0",
        default=False, action="store_true",
        help="Open analysis0?")
    parser.add_argument("--analysis1", dest="analysis1",
        default=False, action="store_true",
        help="Open analysis1?")
    parser.add_argument("--analysis2", dest="analysis2",
        default=False, action="store_true",
        help="Open analysis2?")
    parser.add_argument("--telanalys", dest="telanalys",
        default=False, action="store_true",
        help="Open telanalys?")
    parser.add_argument("--status", dest="status",
        default=False, action="store_true",
        help="Open status for telescope?")
    ## add arguments
    parser.add_argument("account", type=str,
        help="The user account.")
    parser.add_argument("-p", "--password", type=str, widget='PasswordField',
        default=None, help="The account password.")
    args = parser.parse_args()

    if args.password is None:
        args.password = getpass(f"Password for {args.account}: ")

    sessions_to_open = []
    if args.control0 is True:
        sessions_to_open.append('control0')
    if args.control1 is True:
        sessions_to_open.append('control1')
    if args.control2 is True:
        sessions_to_open.append('control2')
    if args.telstatus is True:
        sessions_to_open.append('telstatus')
    if args.analysis0 is True:
        sessions_to_open.append('analysis0')
    if args.analysis1 is True:
        sessions_to_open.append('analysis1')
    if args.analysis2 is True:
        sessions_to_open.append('analysis2')
    if args.telanalys is True:
        sessions_to_open.append('telanalys')
    if args.status is True:
        sessions_to_open.append('status')

    config = get_config()
    if 'firewall_address' in config.keys() and\
       'firewall_user' in config.keys() and\
       'firewall_port' in config.keys():
        config['authenticate'] = True
    else:
        config['authenticate'] = False

    try:
        main(args, config)
    except KeyboardInterrupt:
        if args.firewall != '' or args.close != '':
            close_authentication()
