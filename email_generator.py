#!/usr/env/python

## Import General Tools
import argparse
from datetime import datetime as dt
from datetime import timedelta as tdelta

from telescopeSchedule.telescopeSchedule import *

##-------------------------------------------------------------------------
## Parse Command Line Arguments
##-------------------------------------------------------------------------
## create a parser object for understanding command-line arguments
p = argparse.ArgumentParser(description='''
''')
## add flags
p.add_argument("-v", "--verbose", dest="verbose",
    default=False, action="store_true",
    help="Be verbose! (default = False)")
## add options
p.add_argument("-d", "--date", dest="date", type=str, default=None,
    help="Date of the observing night (in YYYY-mm-dd format).")
p.add_argument("--sa", dest="sa", type=str, default='jwalawender',
    help="SA name.  Will grab list of observers from that's SA support run.")
args = p.parse_args()


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():
    if args.date is None:
        dateobj = dt.now()
    else:
        dateobj = dt.strptime(args.date, '%Y-%m-%d')
    misscount = 0
    maxmisses = 1
    done = False
    foundrun = False
    print('##################################################')
    while not done:
        date = dateobj.strftime('%Y-%m-%d')
        date_name = dateobj.strftime('%a %B %d')
        print(f"# Checking telescope schedule for {date_name}")

        found_sa = [(args.sa == get_SA(date=date, tel=tel)) for tel in [1,2]]
        if np.any(found_sa) and not foundrun:
            foundrun = True
        elif not np.any(found_sa) and foundrun:
            misscount += 1
        if misscount > maxmisses:
            done = True

        for tel in [1,2]:
            if found_sa[tel-1]:
                info = get_telsched(from_date=date, ndays=1, telnr=tel)
                print(f"# Found {len(info)} programs on K{tel}:\n")
                for prog in info:
                    observers_info = []
                    for obsid in prog['ObsId'].split(','):
                        observers_info.append(get_observer_info(obsid))
                    users_names = [u['FirstName'] for u in observers_info]
                    users_str = ', '.join(users_names)

                    if prog['PiEmail'] != 'hlewis@keck.hawaii.edu':
                        email_list = [prog['PiEmail']]
                    else:
                        email_list = []
                    email_list.extend( [u['Email'] for u in observers_info\
                        if u['Email'] != prog['PiEmail'] ] )
                    print('To: ' + ', '.join(email_list))

                    email = f"Keck {prog['Instrument']} observing on "
                    email += f"{date_name}\n\n"
                    
                    email += f'Aloha {users_str},\n\n'
                    email += f"I'll be supporting your {prog['Instrument']} "
                    email += f"time on Keck {prog['TelNr']} on {date_name}. "
                    email += "Please let me know if you have any questions "
                    email += "prior to your run. "
                    if prog['Location'] == 'HQ':
                        email += "It looks like you'll be observing from Keck "
                        email += "HQ in Waimea, feel free to stop by my "
                        email += "office anytime if you have questions. "
                    email += "Please also let me know when you'd like to meet "
                    email += "up in the afternoon to start setup and cals.\n\n"
                    email += "cheers,\n"
                    email += "Josh\n"
                    print('--------------------------------------------------')
                    print(email)
                    print('##################################################')


        dateobj += tdelta(1,0)




if __name__ == '__main__':
    main()
