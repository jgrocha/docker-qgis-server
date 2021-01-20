from owslib.wmts import WebMapTileService
from unidecode import unidecode
from yaml import SafeDumper
from datetime import datetime
from collections import OrderedDict
from shutil import copyfile
from copy import deepcopy

import psycopg2
from psycopg2 import sql
import psycopg2.extras

import argparse
import yaml
import re
import os

import requests


SafeDumper.add_representer(
    type(None),
    lambda dumper, value: dumper.represent_scalar(
        u'tag:yaml.org,2002:null', '')
)


def urlify(s):
    # Remove all non-word characters (everything except numbers and letters)
    s = re.sub(r'[^\w\s]', '', s)

    # Replace all runs of whitespace with underscore
    s = re.sub(r'\s+', '_', s)

    # print(s)
    return s


def id_trim(s):
    s = re.sub(r'[_]', '', s)

    return s


def configure_services(obj, service):
    obj['services'] = {
        'demo': None,
        'tms': {
            'use_grid_names': True,
            # origin for /tiles service
            'origin': 'nw'
        },
        'kml': {
            'use_grid_names': True
        },
        'wmts': None,
        'wms': {
            'srs': ['EPSG:900913', 'EPSG:3857', 'EPSG:4326', 'EPSG:3763', 'EPSG:5016'],
            # image_formats: ['image/png']
            'md': {
                'title': 'MapProxy WMS Proxy',
                'abstract': 'MapProxy configuration by Geomaster.'
            }
        }
    }


def search_parent(layer, parent_name, obj, identifier, source_sufix):
    res = False

    for k in obj:
        if 'name' in k and k['name'] == parent_name:
            if 'layers' not in k:
                k['layers'] = []
            k['layers'].append({
                'name': layer.name,
                'title': layer.title,
                'sources': [identifier+'_'+unidecode(urlify(layer.name))+source_sufix],
                'md': {
                    'abstract': 'Layer from project:' + identifier,
                    'identifier': [{
                        'name': layer_name
                    }]
                }
            })
            res = True
            break
        elif 'layers' in k:
            res = search_parent(layer, parent_name,
                                k['layers'], identifier, source_sufix)
            if res == True:
                break
        if res == True:
            break

    return res


def delete_project(obj, identifier):
    remove_in_caches = []
    # remove_in_layers = []
    remove_in_layers = get_layers_by_project(yml_conf, [identifier])

    aux_dict = deepcopy(obj)

    if 'sources' in aux_dict:
        for source in aux_dict['sources']:
            if source == identifier:
                del obj['sources'][source]
                remove_in_caches.append(source)

    if 'caches' in aux_dict:
        for cache in aux_dict['caches']:
            for cache_key in remove_in_caches:
                cache_source = aux_dict['caches'][cache]['sources'][0]
                if cache_source.split(':')[0] == cache_key:
                    del obj['caches'][cache]
                    # now layer is: 
                    # name: geotuga_costanova_Ruins
                    # cache source is:
                    # sources: [ geotuga_costanova:Ruins ]
                    remove_in_layers.append( identifier + '_' + cache_source.split(':')[1] )

    if 'layers' in aux_dict:
        index = 0
        del_indexes = []
        for layer in aux_dict['layers']:
            for layer_key in remove_in_layers:
                if layer['name'] == layer_key:
                    del_indexes.append(index)

            index += 1

        for i in list(reversed(del_indexes)):
            del obj['layers'][i]


def configure_layers(obj, service, identifier, source_sufix, operation, auto):
    if not 'layers' in obj:
        obj['layers'] = []
    else:
        lys = get_layers_by_project(yml_conf, [identifier])
        obj['layers'] = [x for x in obj['layers'] if x not in lys]

    for (layer_name, layer_meta) in service.contents.items():
        print('layer_name')
        print(layer_name)
        if layer_meta.parent is None or layer_meta.parent.name is None:
            if auto:
                name = '_'.join([identifier, layer_meta.name])
            else:
                name = layer_meta.name
            title = layer_meta.title if layer_meta.title else layer_meta.name
            obj['layers'].append({
                # para projetos diferentes com o mesmo layer, temos que distinguir os layers...
                # se uma camada é comum, deve passar para WMTS (e não vetorial)
                'name': name,
                'title': title,
                'sources': [identifier+'_'+unidecode(urlify(layer_meta.name))+source_sufix],
                'md': {
                    'abstract': 'Layer from project:' + identifier,
                    'identifier': [{
                        'name': layer_name
                    }]
                }
            })
        else:
            search_parent(layer_meta, layer_meta.parent.name,
                          obj['layers'], identifier, source_sufix)


def get_cache(obj, layers, source_id, grid_id):
    for layer in layers:
        if 'sources' in layer:
            for s in layer['sources']:
                if obj['caches'] is None:
                    obj['caches'] = {}
                if s not in obj['caches'] or s.startswith(source_id):
                    obj['caches'][s] = {
                        'meta_size': [4, 4],
                        'meta_buffer': 20,
                        # 20+4x256+20
                        # width=1064&height=1064
                        'use_direct_from_level': 14,
                        'concurrent_tile_creators': 2,
                        'link_single_color_images': True,
                        'grids': [grid_id],
                        'sources': [source_id+':'+layer['md']['identifier'][0]['name']]
                    }
        if 'layers' in layer:
            get_cache(obj, layer['layers'], source_id, grid_id)


def configure_caches(obj, service, source_id, grid_id, operation):
    if not 'caches' in obj:
        obj['caches'] = None
    if 'layers' in obj:
        get_cache(obj, obj['layers'], source_id, grid_id)


def configure_sources(obj, service, source_id, host_name, map, operation):
    if not 'sources' in obj:
        obj['sources'] = {}
    obj['sources'][source_id] = {
        'type': 'wms',
        'wms_opts': {
            'featureinfo': True,
            'legendgraphic': True
        },
        'req': {
            'url': host_name,
            'transparent': True
        }
    }
    if map:
        obj['sources'][source_id]['req']['map'] = map


def configure_grids(obj, service, grids, grid_id):
    if not 'grids' in obj:
        obj['grids'] = {}
    if grid_id in grids:
        obj['grids'][grid_id] = grids[grid_id]
    else:
        assert False, 'Invalid grid id'


def configure_globals(obj, service):
    obj['globals'] = None


def project_in_srcs(prjcts, srcs):
    t = [x for x in prjcts if len(
        list(filter(lambda y: y.startswith(x+':'), srcs))) > 0]

    return len(t) > 0


def search_layer(lys, cachs):
    tst = []
    for lyr in lys:
        tst = [c for c in cachs if 'sources' in lyr and len(
            list(filter(lambda y: y == c[0], lyr['sources']))) > 0]

    return len(tst) > 0


def layer_in_caches(layer, cachs):
    found = False
    if 'sources' in layer:
        found = search_layer([layer], cachs)
    if not found and 'layers' in layer:
        found = search_layer(layer['layers'], cachs)

    return found


def get_layers_by_project(cnf, prjcts):
    cachs = []
    lyrs = []
    if 'caches' in cnf:
        cachs = [x for x in cnf['caches'].items() if 'sources' in x[1]
                 and project_in_srcs(prjcts, x[1]['sources'])]
        if len(cachs) > 0 and 'layers' in cnf:
            lyrs = [x for x in cnf['layers'] if layer_in_caches(x, cachs)]

    return lyrs


def get_source_id(service_name, project_name):
    res = ''
    if service_name is not None:
        res += id_trim(urlify(service_name)) + '_'
    res += id_trim(urlify(project_name))

    return res


def update_geomasterboard_app( mapproxyservice, layers, dbaseweb, client, project_name, identifier, grid ):
    # Get GeomasterBoard app id
    conn = None
    id_of_new_webapp = None
    tilematrix = None
    if grid:
        if grid == 'EPSG:3763':
            tilematrix = """{"matrixSet":"EPSG:3763","tileGrid":{"origin":[-127200,278552],"resolutions":[1200, 600, 300, 150, 75, 37.5, 18.75, 9.375, 4.6875, 2.34375, 1.171875, 0.5859375, 0.29296875, 0.146484375, 0.0732421875],"matrixIds":["00","01","02","03","04","05","06","07","08","09","10","11","12","13","14"],"minZoom":0,"maxZoom":14}}"""
        if grid == 'EPSG:5016':
            # tilematrix = """{"matrixSet":"EPSG:5016","tileGrid":{"origin":[270000, 3650000],"resolutions":[312.5, 156.25, 78.125, 39.0625, 19.53125, 9.765625, 4.8828125, 2.44140625, 1.220703125, 0.6103515625, 0.30517578125, 0.152587890625, 0.0762939453125, 0.03814697265625, 0.019073486328125],"matrixIds":["00","01","02","03","04","05","06","07","08","09","10","11","12","13","14"],"minZoom":0,"maxZoom":14}}"""
            tilematrix = """{"matrixSet":"EPSG:5016","tileGrid":{"origin":[270000, 3570000],"resolutions":[500, 250, 125, 62.5, 31.25, 15.625, 7.8125, 3.90625, 1.953125, 0.9765625, 0.48828125, 0.244140625, 0.1220703125, 0.06103515625, 0.030517578125],"matrixIds":["00","01","02","03","04","05","06","07","08","09","10","11","12","13","14"],"minZoom":0,"maxZoom":14}}"""

    try:
        conn = psycopg2.connect("service=" + dbaseweb)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # query = sql.SQL('select * from {schema}.{table} where client = %s and lower({column}) = lower(%s)').format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu), column=sql.Identifier("routeId") )
        # cursor.execute( query, (client, project_name))
        query = sql.SQL('select * from {schema}.{table} where lower({route}) = lower(%s)').format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu), route=sql.Identifier(tbl_menu_routeId) )
        cursor.execute( query, (project_name, ))        
        row = cursor.fetchone()
        if row is None:
            print('webapp does not exist. Skip.')
        else:
            print('webapp {0} exist.'.format(project_name))
            id_of_new_webapp = row['id']
            for lyr in layers:
                wmts_layer_name = lyr["name"]
                wms_layer_name = re.compile('^'+ identifier + '_').sub('', wmts_layer_name)
                print("Layer {} {}.".format( lyr["name"], lyr["title"] )) # 'name': 'geotuga_costanova_short_house_numbers', 'title': 'short_house_numbers'
                if args.client == 'dgt':
                    insert_sql = """INSERT INTO {schema}.{table} (ord,title,layer,layer_group,url,service,srid,"style",qtip,baselayer,single_tile,active,visible,attribution,notes,create_date,modify_date,user_id,menu_id,opacity,legend_url,gfi,gfi_columns,groupid,gfi_headers,cross_origin,"type")
                        select ord+1,title,%s,layer_group,%s,%s,srid,"style",qtip,baselayer,single_tile,%s,visible,attribution,%s,create_date,modify_date,user_id,menu_id,opacity,legend_url,gfi,gfi_columns,groupid,gfi_headers,cross_origin,"type"
                        from {schema}.{table} where layer = %s and menu_id = %s and service = 'WMS' RETURNING id"""
                else:
                    insert_sql = """INSERT INTO {schema}.{table} (ord,title,layer,layergroup,url,service,srid,"style",qtip,baselayer,singletile,active,visible,attribution,notes,create_date,modify_date,userid,viewid,opacity,legendurl,getfeatureinfo,gficolumns,groupid,gfiheadercolumns,crossorigin,wfsquery,wfsinsert,wfsupdate,wfsdelete,"type")
                        select ord+1,title,%s,layergroup,%s,%s,srid,"style",qtip,baselayer,singletile,%s,visible,attribution,%s,create_date,modify_date,userid,viewid,opacity,legendurl,getfeatureinfo,gficolumns,groupid,gfiheadercolumns,crossorigin,wfsquery,wfsinsert,wfsupdate,wfsdelete,"type"
                        from {schema}.{table} where layer = %s and viewid = %s and service = 'WMS' RETURNING id"""

                query = sql.SQL(insert_sql).format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_layer) )
                cursor.execute( query, ( wmts_layer_name, mapproxyservice, 'GWC', True, tilematrix, wms_layer_name, id_of_new_webapp ) )
                log_query = cursor.query
                print(log_query)
                lrow = cursor.fetchone()
                query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
                cursor.execute( query, ('createflatyaml.py', project_name, 0, log_query.decode("utf-8")))
                if lrow is not None:
                    last_row_id = lrow[0]
                    print("Layer {} inserted as {}.".format( lyr["title"], last_row_id )) # 'name': 'geotuga_costanova_short_house_numbers', 'title': 'short_house_numbers'
                    update_sql = """UPDATE {schema}.{table} set active = False where layer = %s and viewid = %s and service = 'WMS'"""
                    query = sql.SQL(update_sql).format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_layer) )
                    cursor.execute( query, ( wms_layer_name, id_of_new_webapp ) )
                    log_query = cursor.query
                    print(log_query)
                    query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
                    cursor.execute( query, ('createflatyaml.py',project_name,0,log_query.decode("utf-8")))
                else:
                    print("Layer {} NOT inserted.".format( lyr["title"] )) # 'name': 'geotuga_costanova_short_house_numbers', 'title': 'short_house_numbers'
                    query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
                    cursor.execute( query, ('createflatyaml.py',project_name,0,"Layer {} NOT inserted.".format( lyr["title"] )))
        conn.commit()
        cursor.close()
    except (Exception, psycopg2.Error) as e:
        print(e)
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    host_name = None
    service_name = None
    project_name = None
    url = None

    parser = argparse.ArgumentParser(
        description='Convert WMS GetCapabilities to MapProxy YAML config',add_help=False)
    parser.add_argument('-h', '--host', help='WMST host url', required=True)
    parser.add_argument('-u', '--prefix', help='WMST url prefix', required=True)
    parser.add_argument('-o', '--operation',
                        help='insert, update or delete project', required=True)
    parser.add_argument('-b', '--dbase', help='Database service')
    parser.add_argument('-s', '--schema', help='Database schema')
    parser.add_argument('-p', '--project', help='Project name')
    parser.add_argument('-f', '--file', help='File system layer')
    parser.add_argument('-d', '--dir', help='YAML save location')
    parser.add_argument(
        '-g', '--grid', help='ID of grid to be used on tiles', required=True)
    parser.add_argument('-c', '--client', help='client short name', required=True)
    parser.add_argument('-w', '--dbaseweb',
            help='web database service', required=False)
    parser.add_argument('-m', '--mapproxyservice',
            help='MapProxy service url', required=True)

    args = parser.parse_args()
    # python3 createflatyaml.py -h 'http://qgis.demo' -u '/postgresql/geotuga/public/costanova/cgi-bin/qgis_mapserv.fcgi' -b 'geotuga' -s 'public' -p 'costanova' -g 'EPSG:3763' -o 'delete' -c cmestarreja -w geotuga -m 'http://mapproxy.qgis.demo/mapproxy/service'
    # python3 createflatyaml.py -u 'http://brgqgis.cm-braga.pt/cgi-bin/qgis_mapserv.fcgi' -f '/home/qgis/projects/ortos_cmbraga_publico.qgz' -g 'EPSG:3763' -o 'insert' -c cmbraga -m 'http://brgqgis.cm-braga.pt/mapproxy/service'
    # python3 createflatyaml.py -u 'http://brgqgis.cm-braga.pt/cgi-bin/qgis_mapserv.fcgi' -f '/home/qgis/projects/ortos_cmbraga_publico.qgz' -g 'EPSG:3763' -o 'insert' -c cmbraga -m 'http://brgqgis.cm-braga.pt/mapproxy/service'
    # python3 createflatyaml.py -u 'http://webcme.cm-espinho.pt/cgi-bin/qgis_mapserv.fcgi' -f '/home/qgis/projects/espinho.qgz' -g 'EPSG:3763' -o 'insert' -c cmespinho -m 'http://webcme.cm-espinho.pt/mapproxy/service'
    if args.dbase is not None and args.project is not None and args.schema is not None:
        host_name = args.host
        urlprefix = args.prefix
        service_name = args.dbase
        project_name = args.project
        schema_name = args.schema

        url = host_name + urlprefix + "?SERVICE=WMTS&VERSION=1.1.1&REQUEST=GetCapabilities"
        map = ''

    # python3 createflatyaml.py -u 'https://geoifcn.madeira.gov.pt/cgi-bin/qgis_mapserv.fcgi' -f '/home/qgis/projects/ifcn.qgz' -g 'EPSG:5016'
    elif args.file is not None:
        host_name = args.host
        urlprefix = args.prefix

        project_name = args.file

        url = host_name + urlprefix + "?MAP=" + project_name + "&SERVICE=WMTS&VERSION=1.1.1&REQUEST=GetCapabilities"
        map = project_name
    else:
        assert False, "Invalid arguments"

    schema = 'users'
    tbl_mapsource = 'mapsource'
    tbl_logger = 'logger'
    tbl_menu = 'menu'
    tbl_menu_routeId = 'routeId'
    tbl_permissao = 'permissao'
    tbl_layer = 'layer'
    tbl_grupo = 'grupo'
    if args.client == 'dgt':
        schema = 'webapp'
        tbl_mapsource = 'mapsources'
        tbl_logger = 'logger'
        tbl_menu = 'menus'
        tbl_menu_routeId = 'route'
        tbl_permissao = 'permissions'
        tbl_layer = 'layers'
        tbl_grupo = 'usergroups'

    # load existing configuration
    try:
        stream = open('mapproxy.yaml', 'r')
        yml_conf = yaml.load(stream, Loader=yaml.FullLoader)

        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        dest = 'mapproxy.yaml' + "-" + timestamp + ".bak"
        copyfile('mapproxy.yaml', dest)

        # stream_grid = open('grids.yaml', 'r')
        # grids = yaml.load(stream_grid, Loader=yaml.FullLoader)
    except IOError:
        yml_conf = dict()

    identifier = get_source_id(service_name, project_name)

    automatic = False
    # if not automatic, preserve layer names
    if args.dbaseweb:
        # if automatic, change geomasterboard
        # if automatic, assign unique identifiers to layers
        automatic = True

    if args.operation.lower() == 'delete':
        delete_project(yml_conf, identifier)
    else:
        # request GetCapabilities xml
        # wms = WebMapService(url, version='1.3.0')
        # identifier = get_source_id(service_name, project_name)

        # request GetCapabilities xml
        # We must select which layers to publish as WMTS
        # QGIS Server bug #33008 https://github.com/qgis/QGIS/issues/33008
        # Já foi feito o commit :-)
        # wmts = WebMapTileService("http://qgis.demo/postgresql/geotuga/public/costanova/cgi-bin/qgis_mapserv.fcgi?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetCapabilities")
        # wmts = WebMapTileService("http://qgis.sig.cm-agueda.pt/postgresql/publica/public/edificadinho/cgi-bin/qgis_mapserv.fcgi?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetCapabilities")
        # wmts = WebMapTileService("http://qgis.sig.cm-agueda.pt/postgresql/ide/public/pmdfci/cgi-bin/qgis_mapserv.fcgi?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetCapabilities")

        print(url)

        response = requests.get(url)
        contents = response.text
        if "<LowerCorner>" in contents:
            contents = contents.replace("UpperCorner", "ows:UpperCorner")
            contents = contents.replace("LowerCorner", "ows:LowerCorner")
        wmts = WebMapTileService(xml=contents, url=url)
        # print(wmts.contents)

        # filter osmram & osmcontinente
        layer_list = [(ln, ly) for ln, ly in wmts.contents.items() if ln not in [
            'osmram', 'osmcontinente']]

        wmts.contents = OrderedDict(layer_list)

        print('identifier')
        print(identifier)
        print('layers:')
        for (layer_name, layer_meta) in wmts.contents.items():
            print(layer_name, layer_meta.name, layer_meta.title)


        # add or replace info in configuration
        # configure_services(yml_conf, wms)

        configure_sources(yml_conf, wmts, identifier,
                          host_name + urlprefix, map, args.operation)
        configure_layers(yml_conf, wmts, identifier, '_cache', args.operation, automatic)
        configure_caches(yml_conf, wmts, identifier, args.grid, args.operation)

        # configure_grids(yml_conf, wms, grids, args.grid)
        # configure_globals(yml_conf, wms)

        if automatic:
            update_geomasterboard_app( args.mapproxyservice, get_layers_by_project(yml_conf, [identifier]), args.dbaseweb, args.client, project_name, identifier, args.grid )

    with open('mapproxy.yaml', 'w') as outfile:
        yaml.safe_dump(yml_conf, outfile, default_flow_style=False,
                       allow_unicode=True, sort_keys=False)
