#!/usr/env/python

from __future__ import division, print_function

## Import General Tools
import sys
import os
import re
import argparse
import logging

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

##-------------------------------------------------------------------------
## Parse Star List Argument
##-------------------------------------------------------------------------
def parse_arg(arg):
    ## Compile Match Objects for Optional Arguments:
    ##   pmra=s.ssss seconds-of-time/year
    ##   pmdec=a.aaa arcsec/year
    ##   dra=s.ssss arcsec/hr divided by 15 (positive implies moving east)
    ##   ddec=a.aaa arcsec/hr
    ##   vmag=m.m mag
    ##   rotmode=nnn pa, vertical, or stationary
    ##   rotdest=mmm.mm degrees
    ##   wrap=xxx shortest, south, or north (south is clockwise with az
    ##        increasing and north is counterclockwise with az decreasing)
    ##   raoffset=xx.x arcseconds (positive implies moving east)
    ##   decoffset=xx.x arcseconds (positive implies moving north)
    arguments = {'pmra': 'float',\
                 'pmdec': 'float',\
                 'dra': 'float',\
                 'ddec': 'float',\
                 'vmag': 'float',\
                 'rotmode': 'word',\
                 'rotdest': 'float',\
                 'wrap': 'word',\
                 'raoffset': 'float',\
                 'decoffset': 'float',\
                 }
    MO = re.match('(\w+)=([\w\d\-\+\.]+)', arg)
    if MO:
        keyword = MO.group(1)
        assert keyword in arguments.keys()
        if arguments[keyword] == 'float':
            result = float(MO.group(2))
        elif arguments[keyword] == 'word':
            result = str(MO.group(2))
    return keyword, result


##-------------------------------------------------------------------------
## StarList Object
##-------------------------------------------------------------------------
class StarList():
    def __init__(self, filename, verbose=True):
        self.comments = []
        self.lines = []
        self.read_from_file(filename, verbose=verbose)

    def read_from_file(self, filename, verbose=True):

        

        with open(filename, 'r') as FO:
            self.lines = FO.readlines()
            if verbose: print(self.lines)

            for line in self.lines:
                comment = ''
                if verbose: print('\n|{}|'.format(line.strip('\n')))

                ## Check for comments
                commentMO = re.match('(.*)#(.*)\n', line)
                if commentMO:
                    line = '{}\n'.format(commentMO.group(1))
                    comment = commentMO.group(2)

                isblank = re.match('^\s*\n', line)
                if not isblank:
                    objname = line[0:15].strip()
                    line_args = line[16:].split()
                    ## Format coordinate for astropy
                    coord_string = '{} {} {} {} {} {}'.format(\
                                    line_args[0], line_args[1], line_args[2],\
                                    line_args[3], line_args[4], line_args[5],\
                                    )
                    ## Format Equinox argument for astropy
                    equinox_string = line_args[6]
                    if equinox_string == 'APP':
                        equniox = Time.now()
                    else:
                        equinox = Time(float(equinox_string), format='jyear')
                    ## Parse Optional Arguments
                    for line_arg in line_args[7:]:
                        arg, value = parse_arg(line_arg)
                        print('{}: {} = {}'.format(line_arg, arg, value))
                        


                    c = SkyCoord(coord_string,\
                                 unit=(u.hourangle, u.deg),\
                                 frame='fk5',\
                                 equinox=equinox)



                    if verbose:
                        print('Object Name: "{}"'.format(objname))
                        print('Coordinates: {}'.format(c.to_string('hmsdms')))
                        print('Equinox: {}'.format(c.equinox))



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
    parser.add_argument("--input",
        type=str, dest="input",
        help="The input.")
    args = parser.parse_args()

    ##-------------------------------------------------------------------------
    ## Create logger object
    ##-------------------------------------------------------------------------
    logger = logging.getLogger('MyLogger')
    logger.setLevel(logging.DEBUG)
    ## Set up console output
    LogConsoleHandler = logging.StreamHandler()
    if args.verbose:
        LogConsoleHandler.setLevel(logging.DEBUG)
    else:
        LogConsoleHandler.setLevel(logging.INFO)
    LogFormat = logging.Formatter('%(asctime)23s %(levelname)8s: %(message)s')
    LogConsoleHandler.setFormatter(LogFormat)
    logger.addHandler(LogConsoleHandler)
    ## Set up file output
#     LogFileName = None
#     LogFileHandler = logging.FileHandler(LogFileName)
#     LogFileHandler.setLevel(logging.DEBUG)
#     LogFileHandler.setFormatter(LogFormat)
#     logger.addHandler(LogFileHandler)




if __name__ == '__main__':
    sl = StarList('sample_star_list.txt')
    
