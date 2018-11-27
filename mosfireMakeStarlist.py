#!/usr/env/python

## Import General Tools
import sys
import os
import argparse
import logging

import xml.etree.ElementTree as ET


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
p.add_argument("--user", dest="user", type=str,
    default='', help="The user.")
## add arguments
p.add_argument('allothers', nargs='*',
               help="All other arguments")
args = p.parse_args()


##-------------------------------------------------------------------------
## Create logger object
##-------------------------------------------------------------------------
log = logging.getLogger('MyLogger')
log.setLevel(logging.DEBUG)
## Set up console output
LogConsoleHandler = logging.StreamHandler()
if args.verbose is True:
    LogConsoleHandler.setLevel(logging.DEBUG)
else:
    LogConsoleHandler.setLevel(logging.INFO)
LogFormat = logging.Formatter('%(asctime)s %(levelname)8s: %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')
LogConsoleHandler.setFormatter(LogFormat)
log.addHandler(LogConsoleHandler)
## Set up file output
# LogFileName = None
# LogFileHandler = logging.FileHandler(LogFileName)
# LogFileHandler.setLevel(logging.DEBUG)
# LogFileHandler.setFormatter(LogFormat)
# log.addHandler(LogFileHandler)


##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():
    CSUmask_path = os.path.expanduser(f"~{args.user}/CSUmasks/")
    log.debug(f"Searching {CSUmask_path} for XML files")
    xml_files = []
    for root, dirs, files in os.walk(CSUmask_path):
        for file in files:
            if file.endswith(".xml"):
                 xml_files.append(os.path.join(root, file))
    log.debug(f"  Found {len(xml_files)} XML files")

    xml_files_parsed = []
    
    for xml_file in xml_files:
        xml_filepath, xml_filename = os.path.split(xml_file)
        if xml_filename in xml_files_parsed:
            log.warning(f"Skipping additional instance of {xml_filename} in {xml_filepath}")
        else:
            log.debug(f"Parsing {xml_file}")
            with open(xml_file, 'r') as FO:
                contents = FO.read()
            xml_contents = ET.fromstring(contents)

            for maskDescription_entry in xml_contents.iter('maskDescription'):
                maskDescription = dict(maskDescription_entry.items())
                try:
                    maskname = maskDescription['maskName']
                    if maskname.strip().find(' ') != -1:
                        log.warning(f"Spaces in mask name can cause problems.")
                        log.warning(f"We recommend renaming '{maskname}'")
                    if len(maskname.strip()) > 15:
                        log.warning(f"Mask name '{maskname}' is longer than 15 characters and will be truncated.")
                        log.warning(f"Check that no masks have same name after truncation")
                    RAh = str(maskDescription['centerRaH'])
                    RAm = int(maskDescription['centerRaM'])
                    RAs = float(maskDescription['centerRaS'])
                    DECd = str(maskDescription['centerDecD'])
                    DECm = int(maskDescription['centerDecM'])
                    DECs = float(maskDescription['centerDecS'])
                    PA = float(maskDescription['maskPA'])
                    starListLine = f"{maskname:<15s} {RAh:2s} {RAm:02d} {RAs:05.2f} {DECd:>3s} {DECm:02d} {DECs:5.2f} 2000.00 rotdest={PA:+.2f} rotmode=PA"
                    xml_files_parsed.append(xml_filename)
                    print(starListLine)
                except:
                    pass


if __name__ == '__main__':
    main()
