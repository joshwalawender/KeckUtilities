import sys
import os

from datetime import datetime as dt

import pymysql
import pymysql.cursors

import numpy as np
from astropy.table import Table, Column, vstack

import matplotlib as mpl
mpl.rcParams['font.size'] = 24
import matplotlib.pyplot as plt

def main():

    semesters = {2005.5: ('2005-08-01', '2006-01-31'),
                 2006.0: ('2006-02-01', '2006-07-31'),
                 2006.5: ('2006-08-01', '2007-01-31'),
                 2007.0: ('2007-02-01', '2007-07-31'),
                 2007.5: ('2007-08-01', '2008-01-31'),
                 2008.0: ('2008-02-01', '2008-07-31'),
                 2008.5: ('2008-08-01', '2009-01-31'),
                 2009.0: ('2009-02-01', '2009-07-31'),
                 2009.5: ('2009-08-01', '2010-01-31'),
                 2010.0: ('2010-02-01', '2010-07-31'),
                 2010.5: ('2010-08-01', '2011-01-31'),
                 2011.0: ('2011-02-01', '2011-07-31'),
                 2011.5: ('2011-08-01', '2012-01-31'),
                 2012.0: ('2012-02-01', '2012-07-31'),
                 2012.5: ('2012-08-01', '2013-01-31'),
                 2013.0: ('2013-02-01', '2013-07-31'),
                 2013.5: ('2013-08-01', '2014-01-31'),
                 2014.0: ('2014-02-01', '2014-07-31'),
                 2014.5: ('2014-08-01', '2015-01-31'),
                 2015.0: ('2015-02-01', '2015-07-31'),
                 2015.5: ('2015-08-01', '2016-01-31'),
                 2016.0: ('2016-02-01', '2016-07-31'),
                 2016.5: ('2016-08-01', '2017-01-31'),
                 2017.0: ('2017-02-01', '2017-07-31'),
                }

    table_file = 'MainlandObserving.csv'
    if not os.path.exists(table_file):
        print('Querying SQL Database')

        # Connect to the database
        connection = pymysql.connect(host='mysqlserver',
                                     user='sched',
                                     password='sched',
                                     db='schedules',
                                     cursorclass=pymysql.cursors.DictCursor)

        names = ['Status', 'Telescope', 'ReqNo', 'AllocInst', 'Site', 'Instrument', 'Portion', 'FromDate', 'Mode', 'NumNights', 'Principal']
        dtypes = ['a20', 'a8', 'i8', 'a20', 'a20', 'a20', 'a20', 'a20', 'a20', 'i4', 'a40']

        try:
            tab = None
            for semester in sorted(semesters.keys()):
                fields = "ReqNo,FromDate,NumNights,Portion,Telescope,Instrument,AllocInst,Site,Mode,Principal,Status"
                table = "mainlandObs"
                date1, date2 = semesters[semester]
                conditions = ["FromDate between '{}' and '{}'".format(date1, date2),
                              "status = 'approved'"]
                condition = "where {}".format(" and ".join(conditions))
                sql = "select {} from {} {}".format(fields, table, condition)
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    result = cursor.fetchall()
                    print('{}: found {:d} mainland requests'.format(semester, len(result)))
                
                    if len(result) > 0:
                        new = Table(result, names=names, dtype=dtypes)
                        sem = Column([semester]*len(new), name='Semester', dtype='f4')
                        new.add_column(sem)
                        if not tab:
                            tab = new
                        else:
                            tab = vstack([tab, new])
                

        finally:
            connection.close()

        tab.write(table_file)

    else:
        print('Reading Local File')
        tab = Table.read(table_file)



#     tab.keep_columns(['Status', 'Telescope', 'FromDate', 'Mode', 'NumNights', 'Portion', 'Semester'])
#     print(tab.keys())

    ## Weight
    count = {'Full Night': 1., 'Full': 1., 'First Half': 0.5, 'Second Half': 0.5,
             'Other': 0.0, 'K1': 1., 'K2': 1., 'K1+K2': 2.}
    weight = [ count[x['Telescope']] * count[x['Portion']] * float(x['NumNights']) for x in tab ]
    tab.add_column(Column(weight, name='Weight'))


    colormap = plt.cm.gist_ncar


    ## ------------------------------------------------------------------------
    ## Number of Sites Over Time
    ## ------------------------------------------------------------------------
    tab.sort('FromDate')
    sitestab = Table(names=('Site', 'Eavesdrop', 'Mainland Only'), dtype=('a20', 'a10', 'a10'))

    for i,entry in enumerate(tab):
        sites = entry['Site'].split(' ')
        for site in sites:
            if site not in sitestab['Site'].data.astype(str) and site != 'Other':
                if entry['Mode'] == 'Mainland Only':
                    sitestab.add_row((site, '-', entry['FromDate']))
                elif entry['Mode'] == 'Eavesdrop':
                    sitestab.add_row((site, entry['FromDate'], '-'))
            elif entry['Mode'] in ['Eavesdrop', 'Mainland Only']:
                if sitestab[np.where(sitestab['Site'].data.astype(str) == site)][entry['Mode']] == b'-':
                    sitestab[entry['Mode']][np.where(sitestab['Site'].data.astype(str) == site)] = entry['FromDate']

    print(sitestab)

#     mo = [dt.strptime(x, '%Y-%m-%d') for x in sitestab['Mainland Only'].data.astype(str)]
#     e = [dt.strptime(x, '%Y-%m-%d') for x in sitestab['Eavesdrop'].data.astype(str)]
#     sitestab.add_column(Column(data=mo, name='MO'))
#     sitestab.add_column(Column(data=e, name='E'))
#     neavesdrop = []
#     nmainaldnonly = []
#     for semester in sorted(semesters.keys()):
#         print(
#         neavesdrop.append()
#         nmainlandonly.append()
#     sys.exit(0)

    ## ------------------------------------------------------------------------
    ## Mainland Only and Eavesdrop Use by Semester
    ## ------------------------------------------------------------------------
    stab = Table(names=('Semester', 'Eavesdrop Nights', 'Mainland Only Nights'),
                 dtype=('f4', 'f4', 'f4'))
    bysemester = tab.group_by('Semester')
    mode = {}
    for i,val in enumerate(bysemester.groups):
        thissemester = bysemester.groups[i]
        mainlandonly = thissemester[thissemester['Mode'] == 'Mainland Only']
        mainlandonly_sum = sum(mainlandonly['Weight'])
        eavesdrop = thissemester[thissemester['Mode'] == 'Eavesdrop']
        eavesdrop_sum = sum(eavesdrop['Weight'])
        stab.add_row((thissemester[0]['Semester'], eavesdrop_sum, mainlandonly_sum))


    plt.figure(figsize=(16,9), dpi=72)
    ax1 = plt.gca()
    plt.bar(stab['Semester'], stab['Mainland Only Nights'], width=0.4,
            label='Mainland Only')
    plt.bar(stab['Semester'], stab['Mainland Only Nights']+stab['Eavesdrop Nights'],
            width=0.4, alpha=0.4, label='Eavesdrop')
    plt.ylim(0,300)
    plt.xlim(2006, 2017)
    plt.xlabel('Semester')
    plt.ylabel('Nights')
    plt.grid()
    plt.legend(loc='best')
    
    ax2 = ax1.twinx()
    plt.ylabel('Fraction of Total Nights')
    plt.ylim(0,300./365.*2./2.)
    plt.savefig('use_by_semester.png', dpi=72, bbox_inches='tight', pad_inches=0.1)


    ## ------------------------------------------------------------------------
    ## Use by Site
    ## ------------------------------------------------------------------------
    sitecounts = {}
    for i,entry in enumerate(tab):
        sites = entry['Site'].split(' ')
        weight = entry['Weight']
        for site in sites:
            if site not in sitecounts.keys():
                sitecounts[site] = weight
            else:
                sitecounts[site] += weight

    sitelist = sorted(sitecounts.keys())
    countlist = [sitecounts[site] for site in sitelist]
    labels = ['{}: {:.0f}%'.format(site, sitecounts[site]/sum(countlist)*100.)
              for site in sitelist]
    colors = colormap(np.arange(len(countlist))/len(countlist))

    plt.figure(figsize=(12,9), dpi=72)
    ax = plt.gca()
    ax.set_aspect('equal')
    patches, plt_labels = plt.pie(countlist, labels=labels, colors=colors, startangle=90)
    plt_labels[3].get_position()
    plt_labels[3].get_rotation()
    plt_labels[3]._y += 0.02
    plt_labels[3]._x += 0.02
    plt_labels[4].get_position()
    plt_labels[4].get_rotation()
    plt_labels[4]._y -= 0.04
    plt_labels[4]._x += 0.10
    plt_labels[5].get_position()
    plt_labels[5].get_rotation()
    plt_labels[5]._y -= 0.09
    plt_labels[5]._x += 0.09
    plt_labels[13].get_position()
    plt_labels[13].get_rotation()
    plt_labels[13]._y -= 0.03
    plt.title('Use by Site')
    plt.savefig('use_by_site.png', dpi=72, bbox_inches='tight', pad_inches=0.1)


    ## ------------------------------------------------------------------------
    ## Use by Instrument
    ## ------------------------------------------------------------------------
    instruments = {'NIRSPAO': 0., 'NIRSPEC': 0., 'DEIMOS': 0., 'ESI': 0., 'NIRC2': 0.,
                   'LRIS': 0., 'MOSFIRE': 0., 'HIRES': 0., 'OSIRIS': 0.,
                   'Other': 0.}
    
    for i,entry in enumerate(tab):
        instlist = entry['Instrument'].split(',')
        weight = entry['Weight']
        for inst in instlist:
            if inst in instruments.keys():
                instruments[inst] += weight
            else:
                instruments['Other'] += weight

    instlist = ['NIRSPAO', 'NIRSPEC', 'DEIMOS', 'ESI', 'NIRC2',
                'LRIS', 'MOSFIRE', 'HIRES', 'OSIRIS', 'Other']
    countlist = [instruments[inst] for inst in instlist]
    labels = ['{}: {:.0f}%'.format(inst, instruments[inst]/sum(countlist)*100.)
              for inst in instlist]
    colors = colormap(np.arange(len(countlist))/len(countlist))

    plt.figure(figsize=(12,9), dpi=72)
    ax = plt.gca()
    ax.set_aspect('equal')
    patches, plt_labels = plt.pie(countlist, labels=labels, colors=colors)
    plt_labels[3].get_position()
    plt_labels[3].get_rotation()
    plt_labels[3]._x += 0.11
    plt_labels[9].get_position()
    plt_labels[9].get_rotation()
    plt_labels[9]._y -= 0.03
    plt.title('Use by Instrument')
    plt.savefig('use_by_instrument.png', dpi=72, bbox_inches='tight', pad_inches=0.1)



if __name__ == '__main__':
    main()

