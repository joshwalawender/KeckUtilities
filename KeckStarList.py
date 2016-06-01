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
from astropy.table import Table, Row

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
        ## rotmode must be pa, vertical, or stationary
        if keyword == 'rotmode':
            assert result in ['pa', 'vertical', 'stationary']
        ## wrap must be shortest, south, or north
        ##   (south is clockwise with az increasing and north is
        ##   counterclockwise with az decreasing)
        if keyword == 'wrap':
            assert result in ['shortest', 'south', 'north']

    return keyword, result


##-------------------------------------------------------------------------
## Target Object
##-------------------------------------------------------------------------
class Target(object):
    def __init__(self, name=None, coord=None, equinox=None, comment=None,\
                 pmra=None, pmdec=None, dra=None, ddec=None,\
                 vmag=None, rotmode=None, rotdest=None,\
                 wrap=None, raoffset=None, decoffset=None,\
                ):
        self.name = name
        self.comment = comment
        self.pmra = pmra
        self.pmdec = pmdec
        self.dra = dra
        self.ddec = ddec
        self.vmag = vmag
        self.rotmode = rotmode
        self.rotdest = rotdest
        self.wrap = wrap
        self.raoffset = raoffset
        self.decoffset = decoffset

        assert self.rotmode in [None, 'pa', 'vertical', 'stationary']
        assert self.wrap in [None, 'shortest', 'south', 'north']


        if equinox:
            assert type(equinox) == str
            if equinox == 'APP':
                self.equinox = Time.now()
            else:
                self.equinox = Time(float(equinox), format='jyear')
        else:
            ## Assume equinox is J2000
            self.equniox = Time(float('2000.0'), format='jyear')

        if type(coord) == str:
            self.coord = SkyCoord(coord,\
                                  unit=(u.hourangle, u.deg),\
                                  frame='fk5',\
                                  equinox=self.equinox)

        if type(coord) == SkyCoord:
            self.coord = coord


##-------------------------------------------------------------------------
## StarList Object
##-------------------------------------------------------------------------
class StarList(object):
    def __init__(self, filename, verbose=False):
        self.comments = []
        self.lines = []
        self.starlist = []
        self.data_table = Table(names=('name', 'RA', 'Dec', 'equinox', 'pmra',\
                                  'pmdec', 'dra', 'ddec', 'vmag', 'rotmode',\
                                  'rotdest', 'wrap', 'raoffset', 'decoffset',\
                                  ),\
                           dtype=('a15', 'f4', 'f4', 'f4', 'f4',\
                                  'f4', 'f4', 'f4', 'f4', 'a15',\
                                  'f4', 'a15', 'f4', 'f4',\
                                 ),\
                           masked=True,\
                           )
        self.read_from_file(filename, verbose=verbose)


    def read_from_file(self, filename, verbose=False):
        with open(filename, 'r') as FO:
            self.lines = FO.readlines()

        for line in self.lines:
            if verbose:
                print()
                print('## Line: "{}"'.format(line.strip('\n')))

            ## Check for comments
            comment = None
            iscomment = re.match('(.*)#(.*)\n', line)
            if iscomment:
                line = '{}\n'.format(iscomment.group(1))
                comment = iscomment.group(2)

            isblank = re.match('^\s*\n', line)
            if not isblank:

                objname = line[0:15].strip()
                line_args = line[16:].split()
                ## Format coordinate for astropy
                coord_string = '{} {} {} {} {} {}'.format(\
                                line_args[0], line_args[1], line_args[2],\
                                line_args[3], line_args[4], line_args[5],\
                                )

                ## Parse Optional Arguments
                all_args = {'pmra': None,\
                            'pmdec': None,\
                            'dra': None,\
                            'ddec': None,\
                            'vmag': None,\
                            'rotmode': None,\
                            'rotdest': None,\
                            'wrap': None,\
                            'raoffset': None,\
                            'decoffset': None}
                for line_arg in line_args[7:]:
                    arg, value = parse_arg(line_arg)
                    if arg in all_args.keys():
                        all_args[arg] = value

                self.starlist.append(Target(name=line[0:15].strip(),\
                                     coord=coord_string,\
                                     equinox=line_args[6],\
                                     comment=comment,\
                                     pmra=all_args['pmra'],\
                                     pmdec=all_args['pmdec'],\
                                     dra=all_args['dra'],\
                                     ddec=all_args['ddec'],\
                                     vmag=all_args['vmag'],\
                                     rotmode=all_args['rotmode'],\
                                     rotdest=all_args['rotdest'],\
                                     wrap=all_args['wrap'],\
                                     raoffset=all_args['raoffset'],\
                                     decoffset=all_args['decoffset'],\
                                    ))


    def table(self):
        for entry in self.starlist:
            eq = entry.coord.equinox
            eq.format = 'jyear'
            star = {'name': entry.name,\
                    'RA': entry.coord.ra.to(u.degree),\
                    'Dec': entry.coord.dec.to(u.degree),\
                    'equinox': str(eq.value),\
                    'pmra': entry.pmra,\
                    'pmdec': entry.pmdec,\
                    'dra': entry.dra,\
                    'ddec': entry.ddec,\
                    'vmag': entry.vmag,\
                    'rotmode': entry.rotmode,\
                    'rotdest': entry.rotdest,\
                    'wrap': entry.wrap,\
                    'raoffset': entry.raoffset,\
                    'decoffset': entry.decoffset,\
                    }
            mask = {}
            for key in star.keys():
                if star[key]:
                    mask[key] = False
                else:
                    mask[key] = True
            self.data_table.add_row(vals=star, mask=mask)

        return self.data_table


    def export_to_csv(self, filename):
        with open(filename, 'w') as FO:
            for row in self.table():
                c = SkyCoord('{} {}'.format(row['RA'], row['Dec']),\
                             unit=(u.deg, u.deg),\
                             frame='fk5',\
                             equinox=Time(float(row['equinox']), format='jyear'))
                line = '{:15s}, {:s}, {:s}, {:.1f}'.format(\
                       row['name'].decode('UTF-8'),\
                       c.ra.to_string(unit=u.hourangle, sep=':', pad=True,\
                                      precision=2, alwayssign=False, fields=3,\
                                      decimal=False),\
                       c.dec.to_string(unit=u.degree, sep=':', pad=True,\
                                       precision=1, alwayssign=True, fields=3,\
                                       decimal=False),\
                       c.equinox.value,\
                       )
                FO.write('{}\n'.format(line))



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
    print(sl.table())
    sl.export_to_csv('csv_test.txt')
