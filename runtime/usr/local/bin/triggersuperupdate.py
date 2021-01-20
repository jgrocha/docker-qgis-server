#!/usr/bin/python3

import select
import psycopg2
from psycopg2 import sql
import psycopg2.extras
import psycopg2.extensions
import os
import json
import argparse
import subprocess
import shutil
import re
import time

parser = argparse.ArgumentParser(description='Listener for project updates on database')
# Very important: databases and services share the same name.
parser.add_argument('-c', '--client', help='client short name', required=True)
parser.add_argument('-w', '--dbaseweb', help='database supporting geomasterboard webapp', required=True)
parser.add_argument('-d', '--dbase', help=' database where qgis projects was stored', required=True)
parser.add_argument("--skip", help="skip project publishing",
                    action="store_true")

args = parser.parse_args()

time.sleep(10)

# client is defined in the qgis-server-trigger-<service>.service
client = args.client
host = "http://qgis.demo"
mapproxyservice = "http://mapproxy.qgis.demo/mapproxy/service"
epsg = 'EPSG:3763'
cmdreloadmapproxy = "sudo /bin/systemctl reload apache2.service"
schema = 'users'
tbl_logger = 'logger'

if client == 'drota':
    # falta configurar o MapProxy como serviço
    host = "http://gismar.eu"
    epsg = 'EPSG:5016'
if client == 'drote':
    mapproxyservice = "http://localhost:8033/mapproxy/service"
    # cmdreloadmapproxy = "sudo /bin/systemctl restart apache2"
    cmdreloadmapproxy = "apache2 -k restart"
    # host = "http://localhost:8033"
    host = "http://localhost"
    epsg = 'EPSG:5016'
if client == 'dgt':
    mapproxyservice = "https://homologacao.geomaster.pt/mapproxy/service"
    cmdreloadmapproxy = "sudo /bin/systemctl restart apache2"
    host = "https://homologacao.geomaster.pt"
    schema = 'webapp'
    tbl_logger = 'logger'

# database where the 'users' schema is stored. Maybe a different database.
# webdb='geotuga'
webdb = args.dbaseweb

# To prevent server error: Could not open CRS database //.local/share/QGIS/QGIS3/profiles/default/qgis.db
if not os.path.isfile('/tmp/srs.db'):
    # cp /usr/share/qgis/resources/srs.db /tmp
    if os.path.isfile('/usr/share/qgis/resources/srs.db'):
        shutil.copy2('/usr/share/qgis/resources/srs.db', '/tmp')

conn = psycopg2.connect('service={0}'.format(args.dbase))
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

curs = conn.cursor()
curs.execute("LISTEN qgis;")

count = 0
print("Waiting for notifications on channel 'qgis'")
while True:
    if select.select([conn],[],[],6) == ([],[],[]):
        count = count + 1
        if count % 10 == 0:
            print("Timeout for service {0}".format(args.dbase))
    else:
        conn.poll()
        while conn.notifies:
            notify = conn.notifies.pop(0)
            print("Got NOTIFY:", notify.payload)
            print("Client:", client)
            try:
                #
                # apache reload: qgis server needs to reload the project
                #
                payload = json.loads(notify.payload)
                project_name = payload["project"]

                # qgis started to create '*'.bak projects on the database
                if not re.search('\.bak$', project_name):
                    os.system("apache2 -k restart")
                    #
                    # no need to copy custom SVG icon from shared network drive to SVG PATH
                    # important: QGIS clients must add the network folder to QGIS SVG path
                    # important: The same netwrk drive /different mount point) must be added to QGIS Server configuration
                    # 
                    # if client == 'cmbraga':
                    #     bashCommand = ["rsync", "-zarvm", "--include=*/", "--include=*.svg", "--exclude=*",
                    #                    "/mnt/share_cmb/DMUOP-DPRRU/Servico/00_QGIS/Estilos PDM/",
                    #                    "/home/qgis/QGIS/images/svg"]
                    #     subprocess.run(bashCommand)
                    #
                    # log actions on the database (to report on GeomasterBoard)
                    connlog = psycopg2.connect("service=" + args.dbaseweb)
                    connlog.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
                    # conn.autocommit = True
                    cursor = connlog.cursor(cursor_factory=psycopg2.extras.DictCursor)
                    qgisserver = "/postgresql/{}/{}/{}/cgi-bin/qgis_mapserv.fcgi".format( args.dbase, payload["schema"], payload["project"])

                    query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
                    cursor.execute( query, (parser.prog, project_name, 1, "A publicar o projeto {}...".format( project_name )))
                    if not args.skip:
                        #
                        # create, update or delete the GeomasterBoard app
                        #
                        cmdwebapp = "/usr/bin/python3 /usr/local/bin/createsuperwebapp.py -h '{}' -u '{}' -o {} -b '{}' -s '{}' -p '{}' -c '{}' -w '{}'".format( host, qgisserver, payload["operation"], payload["database"], payload["schema"], payload["project"], client, webdb )
                        print(cmdwebapp)
                        query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
                        cursor.execute( query, (parser.prog, project_name, 0, cmdwebapp))
                        os.system(cmdwebapp)
                    # MapProxy needs to be updated: 
                    #   mapproxy.yaml
                    #   seed.yaml
                    if not args.skip:
                        cmdmapproxy = "cd /etc/qgisserver/qgismapproxy; /usr/bin/python3 /usr/local/bin/createflatyaml.py -h '{}' -u '{}' -o {} -b '{}' -s '{}' -p '{}' -g '{}' -c '{}' -w '{}' -m '{}'".format( host, qgisserver, payload["operation"], payload["database"], payload["schema"], payload["project"], epsg, client, webdb, mapproxyservice )
                    else:
                        cmdmapproxy = "cd /etc/qgisserver/qgismapproxy; /usr/bin/python3 /usr/local/bin/createflatyaml.py -h '{}' -u '{}' -o {} -b '{}' -s '{}' -p '{}' -g '{}' -c '{}' -m '{}'".format( host, qgisserver, payload["operation"], payload["database"], payload["schema"], payload["project"], epsg, client, mapproxyservice )
                    print(cmdmapproxy)
                    query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
                    cursor.execute( query, (parser.prog, project_name, 0, cmdmapproxy))
                    os.system(cmdmapproxy)
                    # restart MapProxy service
                    os.system(cmdreloadmapproxy)
            except (ValueError, Exception, psycopg2.Error) as e:  # includes json.decoder.JSONDecodeError:
                print(e)
                query = sql.SQL("INSERT INTO {schema}.{table}(subject,loglevel,detail) VALUES (%s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
                cursor.execute( query, (parser.prog, 1, e))
                cursor.close()
            finally:
                if connlog is not None:
                    connlog.close()
