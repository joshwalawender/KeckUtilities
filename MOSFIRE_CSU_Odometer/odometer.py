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
    
    for log_file in sorted(log_files):
        year = None
        folder = os.path.split(os.path.split(log_file)[0])[1]
        try:
            if folder[0:2] == '20':
                year = int(folder[0:4])
            else:
                year = int(f'20{folder[0:2]}')
            assert year > 2000 and year < 2100

        except ValueError:
            year = dt.utcnow().year

        last_pos = {}
        for bar in bars:
            last_pos[bar] = 0
        try:
            print(f'Reading {log_file} (file is for year {year})')
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
                        date_string = f"{year} {md.group(1)} {int(md.group(2)):02d} {md.group(3)}"
                        date = dt.strptime(date_string, '%Y %b %d %H:%M:%S')
                        if file_start is None:
                            file_start = date
                            ## Look for overlap
                            for i,fds in enumerate(filedates):
                                if (file_start >= fds[0]) and (file_start <= fds[1]):
                                    print(f'WARNING:  Found Overlap with {log_files[i]}')
                                    print(file_start)
                                    print(filedates[i])
                                    sys.exit(0)
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
            assert file_start is not None
            assert file_end is not None
            filedates.append([file_start, file_end])
            print(f'  File covers: {file_start} to {file_end}')
        except UnicodeDecodeError:
            print(f'  Unable to read {log_file}')

    bars = np.array(bars)
    mileage = np.array(mileage)/1000
    nmoves = np.array(nmoves)
    slits = np.array([int((b+1)/2) for b in bars])
    left = np.array([(b%2 != 0) for b in bars])
    right = np.array([(b%2 == 0) for b in bars])

    maxmileage = 0
    maxmoves = 0
    for s in set(slits):
        ids = np.where(slits == s)
        slitmileage = np.sum(mileage[ids])
        maxmileage = max([maxmileage, slitmileage])
        slitmoves = np.sum(nmoves[ids])
        maxmoves = max([maxmoves, slitmoves])

    plt.ioff()

    plt.figure(figsize=(16,10))
    plt.title('Bar Mileage')
    plt.bar(slits[left], mileage[left],
            width=0.9, align='center', color='b')
    plt.bar(slits[right], -mileage[right], bottom=maxmileage,
            width=0.9, align='center', color='g')
    plt.xlim(0,47)
    plt.xlabel("Slit Number")
    plt.ylabel("Mileage (m)")
    plt.grid()
    plt.savefig('CSU_Bar_Mileage.png')

    plt.figure(figsize=(16,10))
    plt.title('Number of Bar Moves')
    plt.bar(slits[left], nmoves[left],
            width=0.9, align='center', color='b')
    plt.bar(slits[right], -nmoves[right], bottom=maxmoves,
            width=0.9, align='center', color='g')
    plt.xlim(0,47)
    plt.xlabel("Slit Number")
    plt.ylabel("N Moves")
    plt.grid()
    plt.savefig('CSU_Bar_Moves.png')


if __name__ == '__main__':
    main()
