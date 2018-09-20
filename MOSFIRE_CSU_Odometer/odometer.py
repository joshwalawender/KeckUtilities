#!/usr/env/python

## Import General Tools
import sys
import os

import re
from glob import glob


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():
    bars = [i for i in range(1,93)]
    nmoves = [0 for i in range(1,93)]
    mileage = [0 for i in range(1,93)]
    lines = {}
    for bar in bars:
        lines[bar] = []

    log_files = glob('/h/instrlogs/mosfire/*/CSU.log*')
    log_files.append('/sdata1300/syslogs/CSU.log')
    
    for log_file in log_files[0:1]:
        if log_file.find('.Z') == -1 and log_file.find('.tar') == -1:
            print(f'Reading {log_file}')
#             with open(log_file, 'r') as FO:
#                 contents = FO.readlines()
#             for line in contents:
#                 match = re.search(f'Record=<(\d\d),', line)
#                 if match is not None:
#                     bar = int(match.group(1))
#                     lines[bar].append(float(line.strip('\n').split(',')[2]))
#                     if len(lines[bar]) > 1:
#                         delta = lines[bar][-1] - lines[bar][-2]
#                         if abs(delta) > 0:
#                             nmoves[bar-1] += 1
#                             mileage[bar-1] += abs(delta)
        else:
            print(f'Skipping {log_file}')

    


if __name__ == '__main__':
    main()
