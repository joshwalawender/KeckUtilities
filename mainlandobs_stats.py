import pymysql
import pymysql.cursors

def main():
    # Connect to the database
    connection = pymysql.connect(host='mysqlserver',
                                 user='sched',
                                 password='sched',
                                 db='schedules',
                                 cursorclass=pymysql.cursors.DictCursor)


    semesters = {'2005B': ('2005-08-01', '2006-01-31'),
                }
    for semester in semesters.keys():
        fields = "ReqNo,FromDate,NumNights,Portion,Telescope,Instrument,AllocInst,Site,Mode,Principal,Status"
        table = "mainlandObs"
        date1, date2 = semesters[semester]
        conditions = ["FromDate between '{}' and '{}'".format(date1, date2),
                      "Site = 'USRA'"]
        condition = "where {}".format(" and ".join(conditions))
        sql = "select {} from {} {}".format(fields, table, condition)
        print(condition)
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                result = cursor.fetchall()
                print(result)
        finally:
            connection.close()


if __name__ == '__main__':
    main()

