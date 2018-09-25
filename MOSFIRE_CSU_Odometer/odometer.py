#!/usr/env/python

## Import General Tools
import sys
import os
from datetime import datetime as dt
import re
from glob import glob
import numpy as np

import matplotlib as mpl
mpl.use('Agg')
from matplotlib import pyplot as plt

##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():
    bars = [i for i in range(1,93)]
    nmoves = [0 for i in range(1,93)]
    mileage = [0 for i in range(1,93)]

    log_files = glob('/h/instrlogs/mosfire/*/CSU.log*')
    log_files.append('/sdata1300/syslogs/CSU.log')
    filedates = []
    
    for log_file in log_files:
        last_pos = {}
        for bar in bars:
            last_pos[bar] = 0
        try:
            print(f'Reading {log_file}')
            with open(log_file, 'r') as FO:
                contents = FO.readlines()
            print(f'  Analyzing {len(contents):,} lines')
            file_start = None
            file_end = None
            for line in contents:
                match = re.search(f'Record=<(\d\d),', line)
                if match is not None:
                    bar = int(match.group(1))
                    md = re.match('(\w+)\s+(\d+)\s+(\d+:\d+:\d+).+', line)
                    if md is not None:
                        date_string = f"{md.group(1)} {int(md.group(2)):02d} {md.group(3)}"
                        date = dt.strptime(date_string, '%b %d %H:%M:%S')
                        if file_start is None:
                            file_start = date
                            ## Look for overlap
                            for i,fds in enumerate(filedates):
                                if (file_start > fds[0]) and (file_start < fds[1]):
                                    print(f'Found Overlap with {log_files[i]}')
                        else:
                            file_end = date
                        barpos = float(line.strip('\n').split(',')[2])
                        if last_pos[bar] != 0:
                            delta = last_pos[bar] - barpos
                            if abs(delta) > 0:
                                nmoves[bar-1] += 1
                                mileage[bar-1] += abs(delta)
                        last_pos[bar] = barpos
                    else:
                        print(line)
            filedates.append([file_start, file_end])
        except UnicodeDecodeError:
            print(f'  Unable to read {log_file}')

    bars = np.array(bars)
    mileage = np.array(mileage)/1000
    nmoves = np.array(nmoves)
    slits = np.array([int((b+1)/2) for b in bars])
    left = np.array([(b%2 != 0) for b in bars])
    right = np.array([(b%2 == 0) for b in bars])

    maxmileage = 0
    for s in set(slits):
        ids = np.where(slits == s)
        slitmileage = np.sum(mileage[ids])
        maxmileage = max([maxmileage, slitmileage])

    plt.ioff()
    plt.figure(figsize=(16,10))
    plt.bar(slits[left], mileage[left],
            width=0.9, align='center', color='b')
    plt.bar(slits[right], -mileage[right], bottom=maxmileage,
            width=0.9, align='center', color='b', alpha=0.5)
    plt.xlim(0,47)
    plt.xlabel("Bar")
    plt.ylabel("Mileage (m)")
    plt.grid()
    plt.savefig('CSU_Bar_Mileage.png')


if __name__ == '__main__':
    main()
