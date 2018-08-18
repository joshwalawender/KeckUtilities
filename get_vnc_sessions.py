#!/usr/env/python

## Import General Tools
import sys
import re
import argparse
import logging
import yaml
import paramiko
import subprocess
from time import sleep
from threading import Thread
from telnetlib import Telnet
from subprocess import Popen
from astropy.table import Table, Column

from gooey import Gooey, GooeyParser


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
def launch_vncviewer(port, pw=None):
    config = get_config()
    cmd = [config['vncviewer'], f'localhost:59{port:02d}']
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
            return True
        else:
            print(result)
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
            return True
        else:
            print(result)
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

    for instrument in accounts.keys():
        if accountname.lower() in accounts[instrument]:
            return instrument


##-------------------------------------------------------------------------
## Determine VNC Server
##-------------------------------------------------------------------------
def determine_VNCserver(accountname, password):
    config = get_config()
    servers_to_try = config.get('servers_to_try')
    vncserver = None
    for s in servers_to_try:
        try:
            print(f'Trying {s}:')
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.WarningPolicy())
            client.connect(f"{s}.keck.hawaii.edu", port=22, timeout=6,
                           username=accountname, password=password)
            print('  Connected')
        except TimeoutError:
            print('  Timeout')
        except:
            print('  Failed')
        else:
            stdin, stdout, stderr = client.exec_command('kvncinfo -server')
            rawoutput = stdout.read()
            vncserver = rawoutput.decode().strip('\n')
        finally:
            client.close()
            if vncserver is not None:
                print(f"Got VNC server: {vncserver}")
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
        print('  Connected')
    except TimeoutError:
        print('  Timeout')
    except:
        print('  Failed')
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
def main():

    ##-------------------------------------------------------------------------
    ## Parse Command Line Arguments
    ##-------------------------------------------------------------------------
    ## create a parser object for understanding command-line arguments
    parser = GooeyParser(
             description="Get VNC sessions.")
    ## add flags
    parser.add_argument("-f", "--firewall",
        dest="firewall",
        default='', help="Authenticate?")
    parser.add_argument("-c", "--close",
        dest="close",
        default='', help="Close Authentication?")
    ## add arguments
    parser.add_argument("account", type=str,
        help="The user account.")
    parser.add_argument("password", type=str, widget='PasswordField',
        help="The account password.")
    args = parser.parse_args()

    ##-------------------------------------------------------------------------
    ## Create logger object
    ##-------------------------------------------------------------------------
    log = logging.getLogger('MyLogger')
    log.setLevel(logging.DEBUG)
    ## Set up console output
    LogConsoleHandler = logging.StreamHandler()
    LogConsoleHandler.setLevel(logging.DEBUG)
    LogFormat = logging.Formatter('%(asctime)23s %(levelname)8s: %(message)s')
    LogConsoleHandler.setFormatter(LogFormat)
    log.addHandler(LogConsoleHandler)


    ##-------------------------------------------------------------------------
    ## Authenticate Through Firewall (or Disconnect)
    ##-------------------------------------------------------------------------
    if args.close != '':
        close_authentication(args.close)
        return
    if args.firewall != '':
        authenticate(args.firewall)


    ##-------------------------------------------------------------------------
    ## Determine instrument
    ##-------------------------------------------------------------------------
    instrument = determine_instrument(args.account)


    ##-------------------------------------------------------------------------
    ## Determine VNC server
    ##-------------------------------------------------------------------------
    vncserver = determine_VNCserver(args.account, args.password)


    ##-------------------------------------------------------------------------
    ## Determine VNC Sessions
    ##-------------------------------------------------------------------------
    sessions = determine_VNC_sessions(args.account, args.password, vncserver)
    if len(sessions) == 0:
        print('No VNC sessions found')
        return

    ssh_threads = []
    vncviewer_threads = []
    for session in sessions:
        port = int(session['Display'][1:])
        sshcmd = f"ssh {args.account}@{vncserver}.keck.hawaii.edu -L 59{port:02d}:{vncserver}.keck.hawaii.edu:59{port:02d} -N"
        print(f"Opening xterm for {session['Desktop']}")
        ssh_threads.append(Thread(target=launch_xterm, args=(f'"{sshcmd}"', args.password, session['Desktop'])))
        ssh_threads[-1].start()

    cont = input('Hit any key when password has been entered.')

    for session in sessions:
        port = int(session['Display'][1:])
        vncviewer_threads.append(Thread(target=launch_vncviewer, args=(port,)))
        vncviewer_threads[-1].start()




    ##-------------------------------------------------------------------------
    ## Print my unix session and k1/2status
    ##-------------------------------------------------------------------------
#     if inKeck:
#         print("open vnc://xserver1:5932")
#     else:
#         displayname = "jwalawender@xserver1"
#         hostname = "xserver1.keck.hawaii.edu"
#         outs = [f"# {displayname:<9s}:",
#                 f"/usr/bin/ssh jwalawender@{hostname} -L 5932:{hostname}:5932 -N",
#                 f"open vnc://localhost:5932",
#                 f""]
#         for line in outs:
#             print(line)
# 
#     if inKeck:
#         print(f"open vnc://svncserver{telescope[instrument]:d}:5901")
#     else:
#         displayname = f"k{telescope[instrument]}-status"
#         hostname = f"svncserver{telescope[instrument]:d}.keck.hawaii.edu"
#         outs = [f"# {displayname:<9s}:",
#                 f"/usr/bin/ssh {account}@{hostname} -L 5901:{hostname}:5901 -N",
#                 f"open vnc://localhost:5901",
#                 f""]
#         for line in outs:
#             print(line)


    ##-------------------------------------------------------------------------
    ## Get Instrument Sessions
    ##-------------------------------------------------------------------------

#     hostname = f"{vncServer[args.instrument]}.keck.hawaii.edu"
#     port = 22
#     command = 'kvncstatus'
#     log.debug(f'Running {command} on {hostname} as {args.account}')
# 
#     try:
#         client = paramiko.SSHClient()
#         client.load_system_host_keys()
#         client.set_missing_host_key_policy(paramiko.WarningPolicy())
#         client.connect(hostname, port=port, username=args.account, password=args.password)
#         stdin, stdout, stderr = client.exec_command(command)
#         rawoutput = stdout.read()
#         output = rawoutput.decode()
#     finally:
#         client.close()
# 
#     if output == 'No VNC servers found.\n':
#         print(f"No VNC servers found for {args.account}")
#         sys.exit(0)
# 
#     tab = Table.read(output, format='ascii')
#     sessions = tab[tab['User'] == args.account]
# 
#     for session in sessions:
#         matchname = re.match('(\w+)-(\w+)-(\w+)', session['Desktop'])
#         displayaccount = matchname.group(2)
#         displayname = matchname.group(3)
# 
# 
#         if inKeck:
#             print(f"# {displayname:<9s}")
#             print(f"open vnc://{hostname}:59{session['Display'][1:]}")
#             if displayname[:7] == 'control':
#                 Popen(["open", f"vnc://{hostname}:59{session['Display'][1:]}"])
#         else:
#             outs = [f"# {displayname:<9s}:",
#                     f"/usr/bin/ssh {args.account}@{hostname} -L "+\
#                     f"59{session['Display'][1:]}:{hostname}:59{session['Display'][1:]} -N",
#                     f"open vnc://localhost:59{session['Display'][1:]}",
#                     f""]
#             for line in outs:
#                 print(line)

    

if __name__ == '__main__':
    main()
