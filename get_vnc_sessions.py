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

from gooey import Gooey, GooeyParser

##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
@Gooey
def main():

    ##-------------------------------------------------------------------------
    ## Parse Command Line Arguments
    ##-------------------------------------------------------------------------
    ## create a parser object for understanding command-line arguments
    parser = GooeyParser(
             description="Get VNC sessions.")
    ## add flags
    parser.add_argument("-v", "--verbose",
        action="store_true", dest="verbose",
        default=False, help="Be verbose! (default = False)")
    ## add arguments
    parser.add_argument("instrument", type=str,# widget='DropDown',
        choices=["HIRES", "LRIS", "MOSFIRE", "OSIRIS", "DEIMOS", "ESI", "KCWI",
                 "NIRES", "NIRSPEC", "NIRC2"],
        help="The instrument.")
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
    vncServer = {"HIRES": 'svncserver1',
                 "LRIS": 'svncserver1',
                 "MOSFIRE": 'svncserver1',
                 "OSIRIS": 'svncserver1',
                 "DEIMOS": 'svncserver2',
                 "ESI": 'svncserver1',
                 "KCWI": 'vm-kcwi',
                 "NIRES": 'vm-nires',
                 "NIRSPEC": 'svncserver2',
                 "NIRC2": 'svncserver2'}
    telescope = {'HIRES': 1,
                 'LRIS': 1,
                 'MOSFIRE': 1,
                 'OSIRIS' : 1,
                 'DEIMOS': 2,
                 'ESI': 2,
                 'KCWI': 2,
                 'NIRES': 2,
                 'NIRSPEC': 2,
                 'NIRC2': 2,
                 }

    log.debug(f'Account: {args.account}')
    log.debug(f'Instrument: {args.instrument}')


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

    hostname = f"{vncServer[args.instrument]}.keck.hawaii.edu"
    port = 22
    command = 'kvncstatus'
    log.debug(f'Running {command} on {hostname} as {args.account}')

    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy())
        client.connect(hostname, port=port, username=args.account, password=args.password)
        stdin, stdout, stderr = client.exec_command(command)
        rawoutput = stdout.read()
        output = rawoutput.decode()
    finally:
        client.close()

    if output == 'No VNC servers found.\n':
        print(f"No VNC servers found for {args.account}")
        sys.exit(0)

    tab = Table.read(output, format='ascii')
    sessions = tab[tab['User'] == args.account]

    for session in sessions:
        matchname = re.match('(\w+)-(\w+)-(\w+)', session['Desktop'])
        displayaccount = matchname.group(2)
        displayname = matchname.group(3)


        if inKeck:
            print(f"# {displayname:<9s}")
            print(f"open vnc://{hostname}:59{session['Display'][1:]}")
            if displayname[:7] == 'control':
                Popen(["open", f"vnc://{hostname}:59{session['Display'][1:]}"])
        else:
            outs = [f"# {displayname:<9s}:",
                    f"/usr/bin/ssh {args.account}@{hostname} -L "+\
                    f"59{session['Display'][1:]}:{hostname}:59{session['Display'][1:]} -N",
                    f"open vnc://localhost:59{session['Display'][1:]}",
                    f""]
            for line in outs:
                print(line)

    

if __name__ == '__main__':
    main()
