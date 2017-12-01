#!/usr/env/python

## Import General Tools
import sys
import os
import re
import argparse
import logging
import paramiko
from astropy.table import Table
from socket import gethostname
from subprocess import Popen

##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():

    ##-------------------------------------------------------------------------
    ## Parse Command Line Arguments
    ##-------------------------------------------------------------------------
    ## create a parser object for understanding command-line arguments
    parser = argparse.ArgumentParser(
             description="Program description.")
    ## add flags
    parser.add_argument("-v", "--verbose",
        action="store_true", dest="verbose",
        default=False, help="Be verbose! (default = False)")
    ## add arguments
    parser.add_argument("account", type=str,
        help="The user account.")
    parser.add_argument("password", type=str,
        help="The account password.")
    args = parser.parse_args()

    ##-------------------------------------------------------------------------
    ## Create logger object
    ##-------------------------------------------------------------------------
    log = logging.getLogger('MyLogger')
    log.setLevel(logging.DEBUG)
    ## Set up console output
    LogConsoleHandler = logging.StreamHandler()
    if args.verbose:
        LogConsoleHandler.setLevel(logging.DEBUG)
    else:
        LogConsoleHandler.setLevel(logging.INFO)
    LogFormat = logging.Formatter('%(asctime)23s %(levelname)8s: %(message)s')
    LogConsoleHandler.setFormatter(LogFormat)
    log.addHandler(LogConsoleHandler)


    ##-------------------------------------------------------------------------
    ## Check where this is being run
    ##-------------------------------------------------------------------------
    if gethostname() == 'Joshs-MBP.local':
        inKeck = True
    else:
        inKeck = False


    ##-------------------------------------------------------------------------
    ## Determine account
    ##-------------------------------------------------------------------------
    account = args.account
    telescope = {'hires': 1,
                 'lris': 1,
                 'mosfire': 1,
                 'osiris' : 1,
                 'esi': 2,
                 'kcwi': 2,
                 'nirspec': 2,
                 'nirc': 2,
                 'nires': 2,
                 'deimos': 2,
                 }
    iseng = re.match('([a-z]+)eng', account.lower())
    isnumbered = re.match('([a-z]+)(\d*)', account.lower())
    if iseng:
        instrument = iseng.group(1)
        number = 'eng'
    elif isnumbered:
        instrument = isnumbered.group(1)
        number = int(isnumbered.group(2))
    else:
        print(f"Could not parse account name: '{account}'")
        sys.exit(0)
    if instrument in ['mos', 'moseng']:
        instrument = 'mosfire'

    log.debug(f'Account: {account}')
    log.debug(f'Instrument: {instrument}')
    log.debug(f'Number: {number}')


    ##-------------------------------------------------------------------------
    ## Print my unix session and k1/2status
    ##-------------------------------------------------------------------------
    if inKeck:
        print("open vnc://xserver1:5932")
    else:
        displayname = "jwalawender@xserver1"
        hostname = "xserver1.keck.hawaii.edu"
        outs = [f"# {displayname:<9s}:",
                f"/usr/bin/ssh jwalawender@{hostname} -L 5932:{hostname}:5932 -N",
                f"open vnc://localhost:5932",
                f""]
        for line in outs:
            print(line)

    if inKeck:
        print(f"open vnc://svncserver{telescope[instrument]:d}:5901")
    else:
        displayname = f"k{telescope[instrument]}-status"
        hostname = f"svncserver{telescope[instrument]:d}.keck.hawaii.edu"
        outs = [f"# {displayname:<9s}:",
                f"/usr/bin/ssh {account}@{hostname} -L 5901:{hostname}:5901 -N",
                f"open vnc://localhost:5901",
                f""]
        for line in outs:
            print(line)


    ##-------------------------------------------------------------------------
    ## Get Instrument Sessions
    ##-------------------------------------------------------------------------

    hostname = f"svncserver{telescope[instrument]}.keck.hawaii.edu"
    port = 22
    command = 'kvncstatus'
    log.debug(f'Running {command} on {hostname} as {account}')

    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy())
        client.connect(hostname, port=port, username=account, password=args.password)
        stdin, stdout, stderr = client.exec_command(command)
        rawoutput = stdout.read()
        output = rawoutput.decode()
    finally:
        client.close()

    if output == 'No VNC servers found.\n':
        print(f"No VNC servers found for {account}")
        sys.exit(0)

    tab = Table.read(output, format='ascii')
    sessions = tab[tab['User'] == account]
    for session in sessions:
        matchname = re.match('(\w+)-(\w+)-(\w+)', session['Desktop'])
        displayaccount = matchname.group(2)
        displayname = matchname.group(3)

        if inKeck:
            print(f"# {displayname:<9s}")
            print(f"open vnc://svncserver{telescope[instrument]:d}:59{session['Display'][1:]}")
            if displayname[:7] == 'control':
                Popen(["open", f"vnc://svncserver{telescope[instrument]:d}:59{session['Display'][1:]}"])
        else:
            outs = [f"# {displayname:<9s}:",
                    f"/usr/bin/ssh {account}@{hostname} -L "+\
                    f"59{session['Display'][1:]}:{hostname}:59{session['Display'][1:]} -N",
                    f"open vnc://localhost:59{session['Display'][1:]}",
                    f""]
            for line in outs:
                print(line)

    

if __name__ == '__main__':
    main()
