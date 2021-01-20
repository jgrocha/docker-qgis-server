
import sys
from collections import OrderedDict
import argparse
import re
import os
import pprint
import psycopg2
from psycopg2 import sql
import psycopg2.extras
import psycopg2.extensions
import urllib.parse
import json
import socket
import traceback

pp = pprint.PrettyPrinter(indent=8)

# to run on headless servers
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

if os.path.exists("/usr/local/bin/qgis_mapserv.fcgi"):
    sys.path.insert(0,'/usr/local/share/qgis/python')

# move from qgis.core import * to here!
# from qgis.core import *
from qgis.core import *

if os.path.exists("/usr/local/bin/qgis_mapserv.fcgi"):
    QgsApplication.setPrefixPath("/usr/local", True)    
else:
    QgsApplication.setPrefixPath('/usr', True)

# move from qgis.server import * to here!
from qgis.server import *
# move from qgis.gui import * to here!
from qgis.gui import *

qgs = QgsApplication([], False)
# Load providers
qgs.initQgis()
# debug paths
# also available on QGIS Python console
print(QgsApplication.showSettings())
#
# Tipos suportados (tipos do ExtJS)
# boolean, int, float, string, date
#
maptypes = {
    "bool": "boolean",
    "float4": "float",
    "float8": "float",
    "numeric": "float",
    "Real": "float",
    "int2": "int",
    "int4": "int",
    "int8": "int",
    "varchar": "string",
    "text": "string",
    "character": "string",
    "date": "date",
    "timestamp": "date",
    "timestamptz": "date",
    "json": "string",
    "jsonb": "string" #, "geometry": "geometry"
}

mapGeometryType = {
    0: "Point",
    1: "Line",
    2: "Polygon",
    3: "UnknownGeometry",
    4: "NullGeometry",
}

webmapproject = {}
webmaplayers = {}
webmaplayerswithnonint4keys = []

def getGroupLayers(parent, group):
    if parent:
        grouppath = parent + '/' + group.name()
        # if group.itemVisibilityChecked():
        #     grouppath += '[true]'
        # else:
        #     grouppath += '[false]'
    else:
        if not isinstance(group, QgsLayerTree):
            grouppath = group.name()
            # if group.itemVisibilityChecked():
            #     grouppath += '[true]'
            # else:
            #     grouppath += '[false]'
        else:
            grouppath = ''
    # print('- group:' + grouppath)
    for child in group.children():
        if isinstance(child, QgsLayerTreeGroup):
            if re.search('--$', group.name()):
                continue
            else:
                getGroupLayers(grouppath, child)
        else:
            # instanceof QgsLayerTreeLayer
            # if child.isVisible():
            #     visible = '[true]'
            # else:
            #     visible = '[false]'
            print(grouppath + '  - layer:' + child.name())
            if re.search('--$', child.name()):
                continue
            query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
            cursor.execute( query, (parser.prog, project_name, 2, "{}/{}".format(grouppath, child.name())))
            layer = child.layer()
            layerid = layer.id()

            if layer.shortName():
                layername = layer.shortName()
            else:
                layername = layer.name()

            # layer = iface.activeLayer()
            # layer.vectorJoins()
            # layer.vectorJoins()[0].joinFieldName()
            # 'id_geomedia'
            # layer.vectorJoins()[0].joinLayer().name()
            # 'lot2020_tabela_excel'
            # layer.vectorJoins()[0].joinFieldNamesSubset()
            # 'alvara_tipo_codigo_serie', 'alvara_tipo', 'alvara_id', 'alvaras_relacionados', 'alvaras_mesmo_processo', 'alteracoes', 'loteador', 'local', 'rec_prov_data_ultima', 'rec_prov_referencia', 'rec_def_data_ultima', 'rec_def_referencia', 'caducidade_data', 'infraestruturas_estado', 'notas_websig', 'processo_spo'
            # layer.vectorJoins()[0].prefix()
            # '_'
            # mylist = 'alvara_tipo_codigo_serie', 'alvara_tipo', 'alvara_id', 'alvaras_relacionados', 'alvaras_mesmo_processo', 'alteracoes', 'loteador', 'local', 'rec_prov_data_ultima', 'rec_prov_referencia', 'rec_def_data_ultima', 'rec_def_referencia', 'caducidade_data', 'infraestruturas_estado', 'notas_websig', 'processo_spo'
            # [ 'lte.' + s + ' as _' + s for s in mylist]

            # To add a view, use DB Manager to select the primary key
            #
            # CREATE OR REPLACE VIEW urbanizacao.base_sig2019_loteamentos_x_lot2020_tabela_excel AS 
            # select l.*,  lte.alvara_tipo_codigo_serie as _alvara_tipo_codigo_serie, lte.alvara_tipo as _alvara_tipo, lte.alvara_id as _alvara_id, lte.alvaras_relacionados as _alvaras_relacionados, lte.alvaras_mesmo_processo as _alvaras_mesmo_processo, lte.alteracoes as _alteracoes, lte.loteador as _loteador, lte.local as _local, lte.rec_prov_data_ultima as _rec_prov_data_ultima, lte.rec_prov_referencia as _rec_prov_referencia, lte.rec_def_data_ultima as _rec_def_data_ultima, lte.rec_def_referencia as _rec_def_referencia, lte.caducidade_data as _caducidade_data, lte.infraestruturas_estado as _infraestruturas_estado, lte.notas_websig as _notas_websig, lte.processo_spo as _processo_spo
            # from urbanizacao.base_sig2019_loteamentos l, urbanizacao.lot2020_tabela_excel lte 
            # where id1_geomedia = REGEXP_REPLACE(COALESCE(lte.id_geomedia, '0'), '[^0-9]*' ,'0')::integer;

            # read varibales defined in the layer
            layer_scope = QgsExpressionContextUtils.layerScope(layer)
            if layer_scope.variable('gmb_search_columns'):
                print(layer_scope.variable('gmb_search_columns'))

            legendUrl = layer.legendUrl()
 
            webmaplayers[layerid] = {
                "title": layer.name(),
                "layer": layername,
                "layergroup": grouppath}
            webmaplayers[layerid]["attribution"] = layer.attribution()
            webmaplayers[layerid]["type"] = layer.type()
            webmaplayers[layerid]["provider"] = layer.providerType()
            #
            webmaplayers[layerid]["legendurl"] = legendUrl
            webmaplayers[layerid]["visible"] = child.isVisible()
            webmaplayers[layerid]["style"] = layer.styleManager().currentStyle()
            webmaplayers[layerid]["srid"] = layer.crs().postgisSrid()

            service = ""
            source = layer.source()

            # vou precisar para os WMTS
            webmaplayers[layerid]["source"] = source

            print('|{}|'.format(source))
            # crs=EPSG:3763&dpiMode=7&format=image/png&layers=militares_2015&styles=default&tileMatrixSet=EPSG:3763&url=http://brgqgis.cm-braga.pt/mapproxy/service?REQUEST%3DGetCapabilities%26SERVICE%3DWMTS
            newsource = source

            # Only VectorLayers with geometry can be identifiable and/or searchable
            webmaplayers[layerid]["searchable"] = False
            # Unable (?) to read the other "Ready-only" flag
            webmaplayers[layerid]["identifiable"] = False

            if webmaplayers[layerid]["type"] == QgsMapLayer.VectorLayer:

                # source = """service='geotuga' sslmode=disable key='ogc_fid' srid=3763 type=MultiPolygon checkPrimaryKeyUnicity='0' table="edificado"."edificado" (wkb_geometry) sql="""
                # source = """service='base' sslmode=disable key='id' srid=3763 type=MultiPolygon checkPrimaryKeyUnicity='1' table="cartografia"."crt2017_area_lazer" (geom) sql="layer" = 'Área Verde em Geral'  OR "layer" = 'Parques e Jardins em geral' OR "layer" = 'Campo de Jogos com Bancadas' OR "layer" = 'Campo de Jogos sem Bancadas'"""

                if not legendUrl:
                    if args.client == 'cmbraga':
                        legendUrl = "{}?&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetLegendGraphic&LAYER={}&FORMAT=image/png&STYLE={}&SLD_VERSION=1.1.0&LAYERTITLE=false&TRANSPARENT=true&ITEMFONTFAMILY=FreightSans".format(
                            urlprefix, layername, layer.styleManager().currentStyle())
                    else:
                        legendUrl = "{}?&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetLegendGraphic&LAYER={}&FORMAT=image/png&STYLE={}&SLD_VERSION=1.1.0&LAYERTITLE=false&TRANSPARENT=true&ITEMFONTFAMILY=DejaVu Sans".format(
                            urlprefix, layername, layer.styleManager().currentStyle())                

                webmaplayers[layerid]["legendurl"] = legendUrl

                print("source") # print(source)
                source = re.sub('\n', ' ', source)
                print(source)

                sqlfilter = ''
                if re.search(' sql=(.*)$', source):
                    sqlfilter = re.search(' sql=(.*)$', source).group(1)

                newsource = re.sub(' sql=.*$', '', source)
                # source = """service='geotuga' key='id' checkPrimaryKeyUnicity='1' table="(select e.* from edificios.edificios_svv_osm e, caop.severdovouga s where s.freguesia ilike '%pessegueiro%' and st_contains(s.geom, e.geom) )" (geom)"""

                # re.search('table=("[^"]+"."[^"]+")\s*', source)
                # re.search('table=("\([^"]+")\s*', source)

                # two possible syntax for tables
                if (re.search('table=("[^"]+"."[^"]+")\s*', newsource)):
                    table = re.search(
                        'table=("[^"]+"."[^"]+")\s*', newsource).group(1)
                    newsource = re.sub(
                        'table=("[^"]+"."[^"]+")\s*', '', newsource)
                elif re.search('table=("\([^"]+")\s*', newsource):
                    table = re.search(
                        'table=("\([^"]+")\s*', newsource).group(1)
                    newsource = re.sub(
                        'table=("\([^"]+")\s*', '', newsource)
                    print("Warning: table {} for layer {} should be replaced by a view".format(table, layername))
                    query = sql.SQL("INSERT INTO {schema}.{table} (subject,project,loglevel,detail) VALUES (%s, %s, %s, %s);").format(
                        schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger))
                    cursor.execute( query, (parser.prog, project_name, 1, "Warning: table {} for layer {} should be replaced by a view".format(table, layername)))
                else:
                    print("table not detected for layer {}".format(layername))
                    table = ''

                webmaplayers[layerid]["sqlfilter"] = sqlfilter
                webmaplayers[layerid]["comment"] = layer.dataComment()
                webmaplayers[layerid]["geomType"] = mapGeometryType[layer.geometryType()]
                
                if mapGeometryType[layer.geometryType()] != "NullGeometry":
                    # Project Properties → Data Sources
                    webmaplayers[layerid]["searchable"] = bool(
                        QgsMapLayer.LayerFlag(layer.flags()) & 4)
                    # Unable (?) to read the other "Ready-only" flag
                    webmaplayers[layerid]["identifiable"] = bool(
                        QgsMapLayer.LayerFlag(layer.flags()) & 1)
                    # get and remove geometry column
                    geometrycolumn = re.search(
                        '\(([^\)]+)\)', newsource).group(1)
                    newsource = re.sub(' \([^\)]+\)', '', newsource)

                    webmaplayers[layerid]["geomColumn"] = geometrycolumn
                # else:
                #     webmaplayers[layerid]["api"] = [] # ["read", "update", "destroy", "create"]
                webmaplayers[layerid]["api"] = []

                print('|{}|'.format(newsource.strip()))

                res = dict(item.split("=") for item in newsource.strip().split(' '))
                print(res["service"], table)
                service = res["service"].strip("\'")
                webmaplayers[layerid]["service"] = service
                webmaplayers[layerid]["table"] = table

                primarykey = []
                for pk in layer.dataProvider().pkAttributeIndexes():
                    primarykey.append(layer.fields()[pk].name())
                layer_primarykey = ','.join(primarykey)
                webmaplayers[layerid]["key"] = layer_primarykey

                fields = {}

                attributeTableColumns = layer.attributeTableConfig().columns()
                # This represents the correct order of the fields
                order = 1
                for col in attributeTableColumns:
                    print(order, ' attributeTableColumns: ', col.name, ', ',
                          col.type, ', ', col.hidden, ', ', col.width)
                    if not col.hidden:
                        # there is always one additional column; maybe related with "Action widget", tagged as hidden
                        fields[col.name] = {
                            "name": col.name,
                            "order": order }
                        order = order + 1

                # TODO: column hidden are not visible - maybe we need to check the widget type

                # layers excluded in AttributesWms → will not be visible in forms (GIF, search details, intersection details, etc)
                # layers included in AttributesWfs → the only ones visible in search results (headers); the only ones printed in intersection details
                for field in layer.fields():
                    # print("Field: ", field.name(), ' (', field.alias(), ') -> ', field.typeName(), ' -> ',
                    #       maptypes[field.typeName()])
                    if field.name() not in layer.excludeAttributesWms() and field.typeName() in maptypes:
                        newfield = {
                            # the field name is protected in the query at server/direct/SearchTables.js
                            # "name": '"' + field.name() + '"',
                            "name": field.name(),
                            "type": maptypes[field.typeName()]
                            # "comment": '' # field.comment()
                        }
                        if field.comment():
                            newfield["comment"] = field.comment()
                        # Check if primary key is int8: if it is, QGIS Server GetFeatureInfo might fail
                        # https://github.com/qgis/QGIS/issues/32844
                        # reported at the end of the script
                        if (field.name() == layer_primarykey):
                            if (field.typeName() != 'int4'):
                                webmaplayerswithnonint4keys.append({
                                    "layer": layername,
                                    "key": layer_primarykey,
                                    "type": field.typeName()
                                })

                        if field.name() not in layer.excludeAttributesWfs():
                            if not hasattr(newfield, 'comment'):
                                newfield["comment"] = "show"

                        if field.alias():
                            newfield["alias"] = field.alias()
                        else:
                            newfield["alias"] = field.name()

                        if (field.name() in fields.keys()):
                            fields[field.name()]["type"] = newfield["type"]
                            fields[field.name()]["alias"] = newfield["alias"]
                            if hasattr(newfield, 'comment'):
                                fields[field.name()]["comment"] = newfield["comment"]

                        # hidden columns were already skipped
                        #  
                        # if (field.editorWidgetSetup().type() == 'Hidden'):
                        #     print("~~~~~~~~~~~~~~~~~~~~ {} is hidden ~~~~~~~~~~~~~~~~".format(field.name()))
                        #     fields[field.name()]["hidden"] = True
                        #     if hasattr(fields[field.name()], 'comment'):
                        #         del fields[field.name()]["comment"]

                    else:
                        print("Field: {} excluded".format(field.name()))
                        if field.typeName() not in maptypes:
                            print("Field: {} map type missing for {}".format(field.name(), field.typeName()))
                        del fields[field.name()]

                webmaplayers[layerid]["fields"] = list(fields.values())

                print("webmaplayers[layerid][\"fields\"]")
                print(webmaplayers[layerid]["fields"])

                webmaplayers[layerid]["gfiheadercolumn"] = webmaplayers[layerid]["fields"][0]["name"]
                print("---> gfiheadercolumn for layer {} is {}".format(layerid, webmaplayers[layerid]["gfiheadercolumn"] ))

                # Project Properties → Data Sources
                webmaplayers[layerid]["searchable"] = bool(
                    QgsMapLayer.LayerFlag(layer.flags()) & 4)
                # Unable (?) to read the other "Ready-only" flag
                webmaplayers[layerid]["identifiable"] = bool(
                    QgsMapLayer.LayerFlag(layer.flags()) & 1)

# http://qgis.demo/postgresql/geotuga/public/super/cgi-bin/qgis_mapserv.fcgi?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetLegendGraphic&LAYER=edificios&FORMAT=image/png&STYLE=segundo&SLD_VERSION=1.1.0
# http://qgis.demo/postgresql/geotuga/public/super/cgi-bin/qgis_mapserv.fcgi?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetLegendGraphic&LAYER=edificios&FORMAT=image/png&STYLE=default&SLD_VERSION=1.1.0&LAYERTITLE=false&TRANSPARENT=true
# http://qgis.demo/postgresql/geotuga/public/super/cgi-bin/qgis_mapserv.fcgi?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities
# http://qgis.demo/postgresql/geotuga/public/super/cgi-bin/qgis_mapserv.fcgi?&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetLegendGraphic&LAYER=Ruins&FORMAT=image/png&STYLE=default&SLD_VERSION=1.1.0


host_name = None
service_name = None
project_name = None
url = None
projectpath = None

parser = argparse.ArgumentParser(
    description='Convert QGIS project to GeomasterBoard webapp', add_help=False)
parser.add_argument('-o', '--operation',
                    help='insert, update or delete project', required=True)
parser.add_argument('-h', '--host', help='WMS host url', required=True)
parser.add_argument('-u', '--prefix', help='Url prefix', required=True)
parser.add_argument('-b', '--dbase', help='Database service', required=True)
parser.add_argument('-s', '--schema', help='Database schema', required=True)
parser.add_argument('-p', '--project', help='Project name', required=True)
parser.add_argument('-c', '--client', help='client short name', required=True)
parser.add_argument('-w', '--dbaseweb',
                    help='web database service', required=True)

args = parser.parse_args()

# Layers with relative URLs
# python3 createsuperwebapp.py -h http://qgis.demo -u /postgresql/geotuga/public/costanova/cgi-bin/qgis_mapserv.fcgi -o INSERT -b geotuga -s public -p costanova -c cmestarreja -w geotuga
# python3 createsuperwebapp.py -h 'http://qgis.demo' -u '/postgresql/geotuga/public/um_tres_teste/cgi-bin/qgis_mapserv.fcgi' -o UPDATE -b 'geotuga' -s 'public' -p 'um_tres_teste' -c 'geomaster' -w 'geodashboard'

# python3 createsuperwebapp.py -h 'http://webcme.cm-espinho.pt' -u '/postgresql/web/public/testewfs/cgi-bin/qgis_mapserv.fcgi' -o UPDATE -b 'web' -s 'public' -p 'testewfs' -c 'cmespinho' -w 'web'

if args.dbase is not None and args.project is not None and args.schema is not None:
    host_name = args.host
    urlprefix = args.prefix
    service_name = args.dbase
    project_name = args.project
    schema_name = args.schema
    # to be used by project.read(projectpath)
    projectpath = 'postgresql:?service={0}&sslmode=disable&dbname=&schema={1}&project={2}'.format(
        service_name, schema_name, project_name)
    # to get the project's WMS capabilities
    # to store in mapsource table
    capabilitiesurl = host_name + urlprefix + \
        "?service=WMS&request=GetCapabilities&version=1.3.0"
else:
    assert False, "Invalid arguments"

schema = 'users'
tbl_mapsource = 'mapsource'
tbl_mapsource_capabilitiesurl = 'capabilitiesurl'
tbl_logger = 'logger'
tbl_menu = 'menu'
tbl_menu_routeId = 'routeId'
tbl_permissao = 'permissao'
tbl_layer = 'layer'
tbl_grupo = 'grupo'
if args.client == 'dgt':
    schema = 'webapp'
    tbl_mapsource = 'mapsources'
    tbl_mapsource_capabilitiesurl = 'capabilities_url'
    tbl_logger = 'logger'
    tbl_menu = 'menus'
    tbl_menu_routeId = 'route'
    tbl_permissao = 'permissions'
    tbl_layer = 'layers'
    tbl_grupo = 'usergroups'

try:
    conn = psycopg2.connect("service=" + args.dbaseweb)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if args.operation.lower() == 'delete': # or args.operation.lower() == 'update':
        #
        # delete entry from users.mapsource
        #
        query = sql.SQL("select count(*) from {schema}.{table} where lower({capabilities}) = lower(%s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_mapsource), capabilities=sql.Identifier(tbl_mapsource_capabilitiesurl) )
        cursor.execute( query, (capabilitiesurl,))
        result = cursor.fetchone()
        print(result['count'])
        if result['count'] == 0:
            print('mapsource does not exist. Skip.')
        else:
            print('mapsource exist. Deleting...')
            query = sql.SQL("DELETE FROM {schema}.{table} WHERE {capabilities} = %s").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_mapsource), capabilities=sql.Identifier(tbl_mapsource_capabilitiesurl) )
            cursor.execute(query, (capabilitiesurl,))
            log_query = cursor.query
            print(log_query)
            query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
            cursor.execute( query, (parser.prog, project_name, 1, log_query.decode("utf-8")))

        #
        # delete application
        # layers will be deleted (cascade)
        #
        # query = sql.SQL('select * from {schema}.{table} where client = %s and lower({route}) = lower(%s)').format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu), route=sql.Identifier(tbl_menu_routeId) )
        # cursor.execute( query, (args.client, args.project))
        query = sql.SQL('select * from {schema}.{table} where lower({route}) = lower(%s)').format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu), route=sql.Identifier(tbl_menu_routeId) )
        cursor.execute( query, (args.project, ))
        row = cursor.fetchone()
        if row is None:
            print('webapp does not exist. Skip.')
        else:
            print('webapp {0} exist. Deleting...'.format(args.project))
            id_of_new_webapp = row['id']
            # cascade delete: permissions and layers will be deleted
            query = sql.SQL("DELETE FROM {schema}.{table} WHERE id = %s").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu) )
            cursor.execute(query, (id_of_new_webapp,))
            log_query = cursor.query
            print(log_query)
            query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
            cursor.execute( query, (parser.prog, project_name, 1, log_query.decode("utf-8")))
        print('--fim: ok--------------------------------------------------------')
        query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
        cursor.execute( query, (parser.prog, project_name, 0, "Projeto {} removido.".format( project_name )))
    if args.operation.lower() == 'insert' or args.operation.lower() == 'update':
        # 'UPDATE' or 'INSERT'
        project = QgsProject.instance()
        root = project.layerTreeRoot()

        canvas = QgsMapCanvas()
        bridge = QgsLayerTreeMapCanvasBridge(root, canvas)
        project.read(projectpath)

        # Must be provided by the user
        webmapproject["title"] = project.baseName()
        if project.title():
            webmapproject["title"] = project.title()

        webmapproject["crs"] = project.crs().authid()
        webmapproject["srid"] = project.crs().postgisSrid()
        webmapproject["mapUnits"] = QgsUnitTypes.toString(
            project.crs().mapUnits())

        print("----title, crs and units-----")
        print(webmapproject["title"])
        print(webmapproject["crs"])
        print(webmapproject["mapUnits"])

        # doesn't work..
        # webmapproject["backgroundColor"] = canvas.mapSettings().backgroundColor().name()
        # only in 3.10 and up
        webmapproject["backgroundColor"] = project.backgroundColor().name()
        print("----backgroundColor-----")
        print(webmapproject["backgroundColor"])

        center = canvas.center()
        e = canvas.extent()
        webmapproject["scale"] = canvas.scale()

        if webmapproject["mapUnits"] == "meters":
            webmapproject["center"] = "[{},{}]".format(
                round(center.x()), round(center.y()))
            webmapproject["extent"] = "[{},{},{},{}]".format(round(e.xMinimum()), round(e.yMinimum()), round(e.xMaximum()), round(
                e.yMaximum()))
        else:
            webmapproject["center"] = "[{},{}]".format(
                round(center.x(), 7), round(center.y(), 7))
            webmapproject["extent"] = "[{},{},{},{}]".format(round(e.xMinimum(), 7), round(e.yMinimum(), 7), round(e.xMaximum(), 7), round(
                e.yMaximum(), 7))

        transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:3763"),
                                           QgsCoordinateReferenceSystem("EPSG:4326"), project)
        e_4326 = transform.transform(e)
        # https://gis.stackexchange.com/questions/8650/measuring-accuracy-of-latitude-and-longitude/8674#8674
        webmapproject["extentWgs84"] = "{},{},{},{}".format(round(e_4326.xMinimum(), 7), round(e_4326.yMinimum(), 7), round(e_4326.xMaximum(), 7), round(
            e_4326.yMaximum(), 7))
        # not used

        print(webmapproject["center"])
        print(webmapproject["extent"])
        print(webmapproject["extentWgs84"])
        print(webmapproject["scale"])

        INCHES_PER_METER = 39.37
        DPI = 96
        resolution = webmapproject["scale"] / (INCHES_PER_METER * DPI)
        grid = [1200, 600, 300, 150, 75, 37.5, 18.75, 9.375, 4.6875, 2.34375,
                1.171875, 0.5859375, 0.29296875, 0.146484375, 0.0732421875]
        best_match = min(grid, key=lambda x: abs(x-resolution))
        zoom = grid.index(best_match)
        print('ZOOM (OpenLayers):', zoom, ' SCALE: ', webmapproject["scale"])

        # calcular manualmente
        # https://github.com/qgis/QGIS/blob/master/src/core/qgsscalecalculator.cpp

        #
        # olmap = Ext.ComponentQuery.query('geoxfullmap')[0].getOlMap();
        # olmap.getView().getResolution();
        # olmap.getView().getZoom();

        print("--fim-da-fase-1-project-settings-")

        # project = QgsProject.instance()
        # cartaz = project.layoutManager().layouts()[0]
        # cartaz.name()
        # pagina = cartaz.pageCollection().pages()[0]
        # map = cartaz.referenceMap() # QgsLayoutItemMap
        # map.sizeWithUnits()
        # <QgsLayoutSize: 111.702 x 139.542 mm >
        # map.sizeWithUnits().height()
        # map.sizeWithUnits().width()
        # map.displayName()
        # map.extent().toString(5)
        #   '-43636.05284,144702.22539 : -40636.05284,150702.22540'
        # extent = map.extent()
        # "[ {}, {}, {}, {}]".format(extent.xMaximum(), extent.yMinimum (), extent.xMinimum(), extent.yMinimum() )
        # '[ -41536.0528393025, 146502.22539544175, -42736.05284052651, 146502.22539544175]'

        # read layouts just to enable print tool
        # Layouts are being read from GetProjectSettings
        # <ComposerTemplates>
        #     <ComposerTemplate atlasEnabled="1" width="210" height="297" name="Layout 1" atlasCoverageLayer="geo_polygonquery_detail_polygon">
        #         <ComposerMap width="63.1504" height="80.46583225806475" name="map0"/>
        #     </ComposerTemplate>
        # </ComposerTemplates>

        layouts = []
        projectLayoutManager = project.layoutManager()
        for layout in projectLayoutManager.layouts():
            print(layout.name())
            layouts.append(layout.name())
        #     for var in QgsExpressionContextUtils.layoutScope(layout).variableNames():
        #         print(var)
        #
        # Atlas layouts must be printed using a QGIS Server plugin
        # https://github.com/3liz/qgis-atlasprint/blob/master/atlasprint/service.py

        # Print normal
        # http://qgis.demo/postgresql/geotuga/public/atlas_teste/cgi-bin/qgis_mapserv.fcgi?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetPrint&FORMAT=pdf&TRANSPARENT=true&TEMPLATE=Layout 1&DPI=400&SRS=EPSG:3763&map0:extent=-20736.92310794624,115831.52404184898,-15167.408312666243,122928.16386164125&LAYERS=geo_polygonquery,geo_polygonquery_detail_polygon,geo_polygonquery_detail_point
        # ATLAS_PK
        # http://qgis.demo/postgresql/geotuga/public/atlas_teste/cgi-bin/qgis_mapserv.fcgi?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetPrint&FORMAT=pdf&TRANSPARENT=true&TEMPLATE=Layout 1&ATLAS_PK=140&DPI=400&SRS=EPSG:3763&map0:extent=-20736.92310794624,115831.52404184898,-15167.408312666243,122928.16386164125&LAYERS=geo_polygonquery,geo_polygonquery_detail_polygon,geo_polygonquery_detail_point
        # http://qgis.demo/postgresql/geotuga/public/atlas_teste/cgi-bin/qgis_mapserv.fcgi?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetPrint&FORMAT=pdf&TRANSPARENT=true&TEMPLATE=polymasterdetail&ATLAS_PK=93,94,95,96,97&DPI=400&SRS=EPSG:3763&map0:extent=-20736.92310794624,115831.52404184898,-15167.408312666243,122928.16386164125&LAYERS=geo_polygonquery,geo_polygonquery_detail_polygon,geo_polygonquery_detail_point
        #
        # x_min(geometry(get_feature_by_id('geo_polygon', attribute( @atlas_feature, 'requestid'))))

        print("--fim-da-fase-2-layouts-")

        getGroupLayers('', root)

        # for l in webmaplayers:
        #     # the order of the relations is important. It *works* with the default sort order.
        #     # relation id and name
        #     print(' ---> ', l, '->', webmaplayers[l]["layer"])

        # project = QgsProject.instance()
        # from qgis.server import QgsServerProjectUtils
        # QgsServerProjectUtils.wfsLayerIds(project)

        print("--fim-da-fase-3-layer-groups-")

        for lyrid in QgsServerProjectUtils.wfsLayerIds(project):
            print("wfsLayerIds: " + lyrid)
            if lyrid not in webmaplayers:
                print("https://github.com/qgis/QGIS/issues/30764")
            else:
                webmaplayers[lyrid]["api"].append("read")
        for lyrid in QgsServerProjectUtils.wfstInsertLayerIds(project):
            if lyrid not in webmaplayers:
                print("https://github.com/qgis/QGIS/issues/30764")
            else:
                webmaplayers[lyrid]["api"].append("create")
        for lyrid in QgsServerProjectUtils.wfstUpdateLayerIds(project):
            if lyrid not in webmaplayers:
                print("https://github.com/qgis/QGIS/issues/30764")
            else:
                webmaplayers[lyrid]["api"].append("update")
        for lyrid in QgsServerProjectUtils.wfstDeleteLayerIds(project):
            if lyrid not in webmaplayers:
                print("https://github.com/qgis/QGIS/issues/30764")
            else:
                webmaplayers[lyrid]["api"].append("destroy")

        print("--na-fase-4-juntar toda a informação sobre as camadas-")

        for layerid in webmaplayers:
            if webmaplayers[layerid]["type"] == QgsMapLayer.VectorLayer:
                # necessary to create gficolumns
                webmaplayers[layerid]["gficolumns"] = {
                    "title": webmaplayers[layerid]["title"],
                    "service": webmaplayers[layerid]["service"],
                    "table": webmaplayers[layerid]["table"],
                    "sqlfilter": webmaplayers[layerid]["sqlfilter"],
                    "key": webmaplayers[layerid]["key"],
                    "api": webmaplayers[layerid]["api"],
                    "searchable": webmaplayers[layerid]["searchable"],
                    "identifiable": webmaplayers[layerid]["identifiable"],
                    "fields": webmaplayers[layerid]["fields"]}
                if webmaplayers[layerid]["geomType"] != "NullGeometry":
                    webmaplayers[layerid]["gficolumns"]["geomColumn"] = webmaplayers[layerid]["geomColumn"]
                    webmaplayers[layerid]["gficolumns"]["geomType"] = webmaplayers[layerid]["geomType"]

        print("--fim-da-fase-4-colunas-tabelas-vetoriais-mesmo-sem-geometria-")

        relmanager = project.relationManager()
        rels = relmanager.relations()

        for key in rels:
            # the order of the relations is important. It *works* with the default sort order.
            # relation id and name
            print("-----------relation----------")
            print(key, '->', rels[key].name())
            # print(len(rels[key].referencedFields()))
            # print(len(rels[key].fieldPairs()))
            fieldPairs = rels[key].fieldPairs()
            for p in fieldPairs:
                print(p, fieldPairs[p])
            if rels[key].referencedLayer().shortName():
                referencedLayer = rels[key].referencedLayer().shortName()
            else:
                referencedLayer = rels[key].referencedLayer().name()
            if rels[key].referencingLayer().shortName():
                referencingLayer = rels[key].referencingLayer().shortName()
            else:
                referencingLayer = rels[key].referencingLayer().name()
            referencedLayerId = rels[key].referencedLayer().id()
            referencingLayerId = rels[key].referencingLayer().id()

            print("acrescentar à tabela ", referencedLayer,
                  " o detalhe ", referencingLayer)

            for f in webmaplayers[referencedLayerId]["gficolumns"]["fields"]:
                if f["name"] == fieldPairs[p]:
                    webmaplayers[referencingLayerId]["gficolumns"]["fkey"] = p
                    if "foreign" in f:
                        f["foreign"].append(
                            webmaplayers[referencingLayerId]["gficolumns"])
                    else:
                        f["foreign"] = [
                            webmaplayers[referencingLayerId]["gficolumns"]]

        print("--fim-da-fase-5-relacoes-")

        # print(webmaplayers)
        # print(webmapproject)

        # TODO
        excluded_layers = ['osmram', 'osmcontinente']

        #
        # update users.mapsource
        #

        query = sql.SQL("select count(*) from {schema}.{table} where lower({capabilities}) = lower(%s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_mapsource), capabilities=sql.Identifier(tbl_mapsource_capabilitiesurl) )
        cursor.execute( query, (capabilitiesurl,))
        result = cursor.fetchone()
        print(result['count'])
        if result['count'] == 0:
            print('mapsource does not exist: creating...')
            query = sql.SQL("SELECT setval(pg_get_serial_sequence(%s, 'id'), (SELECT MAX(id) FROM {schema}.{table}))").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_mapsource) )
            cursor.execute(query, ("{}.{}".format( schema, tbl_mapsource),) )
            query = sql.SQL("INSERT INTO {schema}.{table} ({capabilities}) VALUES (%s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_mapsource), capabilities=sql.Identifier(tbl_mapsource_capabilitiesurl) )
            cursor.execute(query, (capabilitiesurl,))
            log_query = cursor.query
            print(log_query)
            query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
            cursor.execute( query, (parser.prog, project_name, 2, log_query.decode("utf-8")))
        else:
            print('mapsource exists')


        if args.client == 'cmbraga':
            geo_search = {
                "xtype": "geo_search",
                "displayField": "nome_rua",
                "valueField": "nome_rua",
                "emptyText": "Pesquisar rua ...",
                "queryParam": "q",
                "params": {
                    "service": "urbanismo",
                    "model": "toponimia.top_sig2017_linha_nome_rua_view",
                    "pkey": "id",
                    "queryField": "nome_rua,codigo_postal",
                    "displayField": "nome_rua",
                    "valueField": "id",
                    "rootProperty": "result",
                    "geomColumn": "wkb_geometry",
                    "api": "Server.SearchTables.searchByAtrr",
                    "template": "{nome_rua} - {codigo_postal}",
                    "fromEpsg": 4326,
                    "zoom": "12",
                    "duration": "3000"
                }
            }
        elif args.client == 'cmestarreja':
            # view edificado.npc_publi_freg
            # se der erro, incluir "valueField" nos "params"
            geo_search = {
                "xtype": "geo_search",
                "displayField": "nome",
                "valueField": "nome",
                "emptyText": "Pesquisar rua ...",
                "queryParam": "q",
                "params": {
                    "service": "sigig",
                    "model": "edificado.npc_publi_freg",
                    "queryField": "nome",
                    "geomColumn": "wkb_geometry",
                    "template": "{nome} - {des_simpli}",
                    "fromEpsg": 4326,
                    "zoom": 12,
                    "duration": 3000
                }
            }
        else:
            geo_search = {
                "xtype": "geo_search",
                "displayField": "name",
                "valueField": "lonlat",
                "emptyText": "Procurar...",
                "zoom": 10,
                "queryParam": "q",
                "params": {
                    "url": "https://nominatim.openstreetmap.org/search?format=json&bounded=1&viewboxlbrt=" + webmapproject["extentWgs84"],
                    "fromEpsg": 4326
                }
            }

        if args.client == 'cmestarreja':
            noZoom = True
        else:
            noZoom = False

        if args.client == 'cmbraga':
            geo_query = {"xtype":"geo_query", "simple": True}
        else:
            geo_query = {"xtype":"geo_query"}

        projecttools = {}
        alltools = {
            "geo_zoomin": {"xtype": "geo_zoomin"}, 
            "geo_zoomout": {"xtype": "geo_zoomout"}, 
            "geo_extent": {"xtype": "geo_extent"}, 
            "geo_query": geo_query, 
            "geo_getcoordinate": {"xtype": "geo_getcoordinate", "precision": 6}, 
            "geo_distance": {"xtype": "geo_distance"}, 
            "geo_area": {"xtype": "geo_area"}, 
            "geo_sketch": {"xtype": "geo_sketch"}, 
            "geo_goto": {"xtype": "geo_goto"}, 
            "geo_layers": {"xtype": "geo_layers"},
            "geo_query2": {"xtype": "geo_query2", "noZoom": noZoom}, 
            "geo_mapprint": {"xtype": "geo_mapprint"}, 
            "geo_polygonquery": {"xtype": "geo_polygonquery"},
            "geo_mouseposition": {"xtype": "geo_mouseposition", "pos": [ 0, 0], "posAnchorX": "center", "posAnchorY": "down"}, 
            "geo_searchlayer": {"xtype": "geo_searchlayer"},
            "geo_search": geo_search
        }
        # header → headerTools
        validposition = [ "header", "left", "right", "custom", "off" ]

        h = {
            "headerTools": [],
            "tools": {
                "left": [],
                "right": [],
                "custom": []
            }
        }

        print('----------------------------------------------------------')
        # geo_zoomin → right
        # geo_zoomout → off
        # geo_query2 → right;hidden=True
        # geo_mouseposition → custom;posAnchorX=center;pos=0,0;posAnchorY=down
        # geo_mapprint → left
        # geo_searchlayer → header
        # geo_search → custom;outro=nome_rua;params.outro=nome_freguesia
        # geo_search → custom;zoom=6;params.year=2020;params.template={nome} - {freguesia}
        # geo_query2 → right;noZoom=False;hidden=True

        for t in alltools.keys():
            tool = QgsExpressionContextUtils.projectScope(project).variable(t)
            if tool:
                print("tool {} is defined in project with value {}".format(t, tool))
                options = tool.split(";")
                if options[0] in validposition:
                    if t == 'geo_search':
                        print('geo_search on pos {}'.format(options[0]))
                        projecttools[t] = geo_search
                        projecttools[t]["position"] = options[0]
                    else:
                        projecttools[t] = {
                            "xtype": t,
                            "position": options[0]
                            }
                    length = len(options)
                    i = 1
                    while i < length: 
                        if options[i]:
                            extraoption = options[i].split("=")
                            if (len(extraoption) == 2):
                                extraoptionlist = extraoption[1].split(",")
                                if (len(extraoptionlist) > 1):
                                    value = extraoptionlist
                                else:
                                    value = extraoption[1]
                                extraoptionkeys = extraoption[0].split(".")
                                if len(extraoptionkeys) > 1:
                                    # params.outro
                                    projecttools[t][extraoptionkeys[0]][extraoptionkeys[1]] = value
                                else:
                                    if (value.lower() == 'true'):
                                        projecttools[t][extraoptionkeys[0]] = True
                                    elif (value.lower() == 'false'):
                                        projecttools[t][extraoptionkeys[0]] = False
                                    else:
                                        projecttools[t][extraoptionkeys[0]] = value
                        i += 1
                else:
                    continue

        toolskeys = projecttools.keys()
        query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
        cursor.execute( query, (parser.prog, project_name, 2, list(toolskeys)))

        # default tools on the left
        for t in [ "geo_zoomin", "geo_zoomout", "geo_extent", "geo_goto", "geo_getcoordinate", "geo_distance", "geo_area" ]:
            if (t in toolskeys):
                pos = projecttools[t]["position"]
                if pos != "off" and pos in ["left", "right"]:
                    del projecttools[t]["position"]
                    h["tools"][pos].append(projecttools[t])
            else:
                # use default
                h["tools"]["left"].append(alltools[t])

        # default tools on the right
        for t in [ "geo_query", "geo_query2", "geo_sketch", "geo_layers" ]:
            if (t in toolskeys):
                pos = projecttools[t]["position"]
                if pos != "off" and pos in ["left", "right"]:
                    del projecttools[t]["position"]
                    h["tools"][pos].append(projecttools[t])
            else:
                # use default
                h["tools"]["right"].append(alltools[t])

        # default geo_mapprint right
        for t in [ "geo_mapprint" ]:
            if (t in toolskeys):
                pos = projecttools[t]["position"]
                if pos != "off" and pos in ["left", "right"]:
                    del projecttools[t]["position"]
                    if len(layouts) > 0:
                        h["tools"][pos].append(projecttools[t])
            else:
                # use default
                if len(layouts) > 0:
                    h["tools"]["right"].append(alltools[t])

        # non default tools left|right
        for t in [ "geo_polygonquery" ]:
            if (t in toolskeys):
                pos = projecttools[t]["position"]
                if pos != "off" and pos in ["left", "right"]:
                    del projecttools[t]["position"]
                    h["tools"][pos].append(projecttools[t])

        # default tools custom
        for t in [ "geo_mouseposition" ]:
            if (t in toolskeys):
                pos = projecttools[t]["position"]
                if pos != "off" and pos in ["custom"]:
                    del projecttools[t]["position"]
                    h["tools"][pos].append(projecttools[t])
            else:
                # use default
                h["tools"]["custom"].append(alltools[t])

        # default tools custom
        for t in [ "geo_search" ]:
            if (t in toolskeys):
                pos = projecttools[t]["position"]
                if pos != "off" and pos in ["custom", "header"]:
                    del projecttools[t]["position"]
                    if pos == "custom":
                        h["tools"][pos].append(projecttools[t])
                    if pos == "header":
                        h["headerTools"].append(projecttools[t])
            else:
                # use default
                h["tools"]["custom"].append(alltools[t])

        # non default tools top
        for t in [ "geo_searchlayer" ]:
            if (t in toolskeys):
                pos = projecttools[t]["position"]
                if pos != "off" and pos in ["header"]:
                    del projecttools[t]["position"]
                    h["headerTools"].append(projecttools[t])

        print('----------------------------------------------------------')

        # check if application already exists
        # query = sql.SQL('select * from {schema}.{table} where client = %s and {route} = %s').format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu), route=sql.Identifier(tbl_menu_routeId) )
        # cursor.execute(query, (args.client, project_name))        
        query = sql.SQL('select * from {schema}.{table} where {route} = %s').format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu), route=sql.Identifier(tbl_menu_routeId) )
        cursor.execute(query, (project_name, ))
        row = cursor.fetchone()
        if row is None:
            print('webapp does not exist: creating...')
            query = sql.SQL("SELECT setval(pg_get_serial_sequence(%s, 'id'), (SELECT MAX(id) FROM {schema}.{table}))").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu) )
            cursor.execute(query, ("{}.{}".format( schema, tbl_menu),) )

            if args.client == 'dgt':
                insert_sql = """INSERT INTO {schema}.{table} (title, icon, {route}, hidden) 
                    values ( %s, 'mdi-map', %s, false) RETURNING id"""
                query = sql.SQL(insert_sql).format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu), route=sql.Identifier(tbl_menu_routeId) )
                cursor.execute(query, (webmapproject["title"], project_name))
            else:
                insert_sql = """INSERT INTO {schema}.{table} (text, "iconCls", idparent, {route}, "viewType", center, projection, extent, zoom, client, custom, maptools, qgis_url, background)
                    select %s as "text", 'x-fa fa-navicon' as "iconCls", m.id as idparent, %s as {route}, 'universal' as "viewType", %s as center, %s as projection,
                        %s as extent, %s as zoom,  %s as client, true as custom, %s as maptools, %s as qgis_url, %s as background
                    from {schema}.{table} m
                    where idparent is null and {route} = 'sig-parent'
                    RETURNING id;"""
                query = sql.SQL(insert_sql).format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu), route=sql.Identifier(tbl_menu_routeId) )
                cursor.execute(query, (webmapproject["title"], project_name,
                                    webmapproject["center"], webmapproject["crs"],
                                    webmapproject["extent"], zoom, args.client, json.dumps(h), urlprefix, webmapproject["backgroundColor"]))

            res_one = cursor.fetchone()
            if res_one is not None:
                id_of_new_webapp = res_one[0]
            else:
                id_of_new_webapp = 0
            log_query = cursor.query
            print(log_query.decode())

            query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
            cursor.execute(query, (parser.prog, project_name, 1, "GeomasterBoard app created with id {0}".format(id_of_new_webapp)))
            query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
            cursor.execute(query, (parser.prog, project_name, 2, log_query.decode("utf-8")))
            #
            # give permissions to every group
            #
            query = sql.SQL("insert into {schema}.{tableper} (idmenu, idgrupo) select %s, id from {schema}.{tablegrp}").format( schema=sql.Identifier(schema), tableper=sql.Identifier(tbl_permissao), tablegrp=sql.Identifier(tbl_grupo) )
            cursor.execute(query, (id_of_new_webapp,))
            print("Permissions granted for app {0}".format(project_name))
        else:
            # Update the existing application
            # This way, we don't change permissions
            # If the user wants to change it, he has to remove it
            id_of_new_webapp = row['id']
            print('webapp {} exists with id {}'.format(
                project_name, id_of_new_webapp))
            print('webapp exists: updating...')

            if args.client == 'dgt':
                update_sql = """update {schema}.{table} set title = %s WHERE {route} = %s"""
                query = sql.SQL(update_sql).format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu), route=sql.Identifier(tbl_menu_routeId) )
                cursor.execute(query, (webmapproject["title"], project_name ))
            else:
                update_sql = """update {schema}.{table} set
                    text = %s, projection = %s, maptools = %s, qgis_url = %s, background = %s WHERE client = %s and {route} = %s"""
                query = sql.SQL(update_sql).format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_menu), route=sql.Identifier(tbl_menu_routeId) )
                cursor.execute(query, (webmapproject["title"], 
                                webmapproject["crs"], json.dumps(h), urlprefix, webmapproject["backgroundColor"], args.client, project_name))

            log_query = cursor.query
            print(log_query.decode())
            # logger
            query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
            cursor.execute( query, (parser.prog, project_name, 1, 'webapp {} with id {} updated'.format(project_name, id_of_new_webapp)))
            

        # (re)create layers
        #
        # handle raster and vector layers
        #
        # remove all previous layers added by this script (baselayer is False)
        #     - manually added layers must have baseLayer = True
        # recreate all layers, instead of updating them
        if args.client == 'dgt':
            query = sql.SQL("delete from {schema}.{table} where menu_id = %s and not baselayer").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_layer) )
        else:
            query = sql.SQL("delete from {schema}.{table} where viewid = %s and not baselayer").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_layer) )
        cursor.execute( query, (id_of_new_webapp,))
        #
        ord = 10
        for layerid in webmaplayers:
            # print(webmaplayers[layerid]["layer"])
            if webmaplayers[layerid]["type"] == QgsMapLayer.VectorLayer:
                if webmaplayers[layerid]["geomType"] != "NullGeometry":
                    print("Layer {0} does not exist. Will be created.".format(
                        webmaplayers[layerid]["layer"]))

                    if args.client == 'dgt':
                        insert_sql = """INSERT INTO {schema}.{table} (
                            ord, title, layer, layer_group, url, 
                            service, srid, "style", qtip, baselayer, single_tile,
                            active, visible, attribution, menu_id, opacity, 
                            legend_url, gfi, gfi_headers, gfi_columns, type)
                            VALUES(%s, %s, %s, %s, %s, 
                            'WMS', %s, %s, NULL, false, true, 
                            true, %s::bool, %s, %s, 1, 
                            %s, %s, %s, %s, %s );"""
                    else:
                        insert_sql = """INSERT INTO {schema}.{table} (
                            ord, title, layer, layergroup, url, 
                            service, srid, "style", qtip, baselayer, singletile,
                            active, visible, attribution, viewid, opacity, 
                            legendurl, getfeatureinfo, gfiheadercolumns, gficolumns, type)
                            VALUES(%s, %s, %s, %s, %s, 
                            'WMS', %s, %s, NULL, false, true, 
                            true, %s::bool, %s, %s, 1, 
                            %s, %s, %s, %s, %s );"""
                    query = sql.SQL(insert_sql).format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_layer) )
                    cursor.execute(query, (ord, webmaplayers[layerid]["title"], webmaplayers[layerid]["layer"], webmaplayers[layerid]["layergroup"], urlprefix,
                                         webmapproject["srid"], webmaplayers[layerid]["style"],
                                         webmaplayers[layerid]["visible"], webmaplayers[layerid]["attribution"], id_of_new_webapp,
                                         webmaplayers[layerid]["legendurl"], webmaplayers[layerid]["identifiable"], webmaplayers[layerid]["gfiheadercolumn"], json.dumps(webmaplayers[layerid]["gficolumns"]), webmaplayers[layerid]["geomType"]))
                    log_query = cursor.query
                    if (cursor.rowcount != 1):
                        print('Error inserting layer {}'.format(webmaplayers[layerid]["title"]))
                        print(log_query.decode())
                    else:
                        print('OK inserting layer {}'.format(webmaplayers[layerid]["title"]))

                    query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
                    cursor.execute( query, (parser.prog, project_name, 2, log_query.decode("utf-8")))

            else:
                print("Layer {0} does not exist. Will be created.".format(
                    webmaplayers[layerid]["layer"]))

                source = webmaplayers[layerid]["source"]

                if re.search('wmts', source.lower()) and host_name.lower() in source.lower():
                    try:
                        res = dict(item.split("=") for item in source.split("&"))
                        if res['url'].startswith(host_name):
                            print(host_name);
                            grid = res['tileMatrixSet']
                            if grid == 'EPSG:3763':
                                tilematrix = """{"matrixSet":"EPSG:3763","tileGrid":{"origin":[-127200,278552],"resolutions":[1200, 600, 300, 150, 75, 37.5, 18.75, 9.375, 4.6875, 2.34375, 1.171875, 0.5859375, 0.29296875, 0.146484375, 0.0732421875],"matrixIds":["00","01","02","03","04","05","06","07","08","09","10","11","12","13","14"],"minZoom":0,"maxZoom":14}}"""
                            if grid == 'EPSG:5016':
                                # tilematrix = """{"matrixSet":"EPSG:5016","tileGrid":{"origin":[270000, 3650000],"resolutions":[312.5, 156.25, 78.125, 39.0625, 19.53125, 9.765625, 4.8828125, 2.44140625, 1.220703125, 0.6103515625, 0.30517578125, 0.152587890625, 0.0762939453125, 0.03814697265625, 0.019073486328125],"matrixIds":["00","01","02","03","04","05","06","07","08","09","10","11","12","13","14"],"minZoom":0,"maxZoom":14}}"""
                                tilematrix = """{"matrixSet":"EPSG:5016","tileGrid":{"origin":[270000, 3570000],"resolutions":[500, 250, 125, 62.5, 31.25, 15.625, 7.8125, 3.90625, 1.953125, 0.9765625, 0.48828125, 0.244140625, 0.1220703125, 0.06103515625, 0.030517578125],"matrixIds":["00","01","02","03","04","05","06","07","08","09","10","11","12","13","14"],"minZoom":0,"maxZoom":14}}"""
                            wmts_layer_name = res['layers']

                            if not webmaplayers[layerid]["legendurl"]:
                                # webmaplayers[layerid]["legendurl"] = "{}/qgis/mIconRaster.png".format( host_name )
                                webmaplayers[layerid]["legendurl"] = "/qgis/mIconRaster.png"

                            if args.client == 'dgt':
                                insert_sql = """INSERT INTO {schema}.{table} (
                                    ord, title, layer, layer_group, url, 
                                    service, srid, "style", qtip, baselayer, single_tile,
                                    active, visible, attribution, menu_id, opacity, 
                                    legend_url, gfi, notes)
                                    VALUES(%s, %s, %s, %s, %s, 
                                    'GWC', %s, %s, NULL, false, false, 
                                    true, %s::bool, %s, %s, 1, 
                                    %s, %s, %s );"""
                            else:
                                insert_sql = """INSERT INTO {schema}.{table} (
                                    ord, title, layer, layergroup, url, 
                                    service, srid, "style", qtip, baselayer, singletile,
                                    active, visible, attribution, viewid, opacity, 
                                    legendurl, getfeatureinfo, notes)
                                    VALUES(%s, %s, %s, %s, %s, 
                                    'GWC', %s, %s, NULL, false, false, 
                                    true, %s::bool, %s, %s, 1, 
                                    %s, %s, %s );"""                                

                            # print(sql)
                            query = sql.SQL(insert_sql).format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_layer) )
                            cursor.execute(query, (ord+1, webmaplayers[layerid]["title"], wmts_layer_name, webmaplayers[layerid]["layergroup"], '/mapproxy/service',
                                                webmapproject["srid"], webmaplayers[layerid]["style"],
                                                webmaplayers[layerid]["visible"], webmaplayers[layerid]["attribution"], id_of_new_webapp,
                                                webmaplayers[layerid]["legendurl"], webmaplayers[layerid]["identifiable"], tilematrix ))
                            is_local_wmts = True
                        else:
                            is_local_wmts = False
                    except (Exception, ValueError) as e:
                        print('skip')
                        is_local_wmts = False
                else:
                    is_local_wmts = False

                if not is_local_wmts:
                    print('Non WMTS raster layer')
                    if not webmaplayers[layerid]["legendurl"]:
                        webmaplayers[layerid]["legendurl"] = "{}?&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetLegendGraphic&LAYER={}&FORMAT=image/png&STYLE={}&SLD_VERSION=1.1.0&LAYERTITLE=false&TRANSPARENT=true".format(
                            urlprefix, webmaplayers[layerid]["layer"], webmaplayers[layerid]["style"] )

                    if args.client == 'dgt':
                        insert_sql = """INSERT INTO {schema}.{table} (
                            ord, title, layer, layer_group, url, 
                            service, srid, "style", qtip, baselayer, single_tile,
                            active, visible, attribution, menu_id, opacity, 
                            legend_url, gfi)
                            VALUES(%s, %s, %s, %s, %s, 
                            'WMS', %s, %s, NULL, false, true, 
                            true, %s::bool, %s, %s, 1, 
                            %s, %s )"""
                    else:
                        insert_sql = """INSERT INTO {schema}.{table} (
                            ord, title, layer, layergroup, url, 
                            service, srid, "style", qtip, baselayer, singletile,
                            active, visible, attribution, viewid, opacity, 
                            legendurl, getfeatureinfo)
                            VALUES(%s, %s, %s, %s, %s, 
                            'WMS', %s, %s, NULL, false, true, 
                            true, %s::bool, %s, %s, 1, 
                            %s, %s )"""
                    # print(insert_sql)
                    query = sql.SQL(insert_sql).format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_layer) )
                    cursor.execute(query, (ord, webmaplayers[layerid]["title"], webmaplayers[layerid]["layer"], webmaplayers[layerid]["layergroup"], urlprefix,
                                        webmapproject["srid"], webmaplayers[layerid]["style"],
                                        webmaplayers[layerid]["visible"], webmaplayers[layerid]["attribution"], id_of_new_webapp,
                                        webmaplayers[layerid]["legendurl"], webmaplayers[layerid]["identifiable"]))

                log_query = cursor.query
                if (cursor.rowcount != 1):
                    print('Error inserting raster layer {}'.format(webmaplayers[layerid]["title"]))
                    print(log_query.decode())
                else:
                    print('OK inserting raster layer {}'.format(webmaplayers[layerid]["title"]))

                query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
                cursor.execute( query, (parser.prog, project_name, 2, log_query.decode("utf-8")))

            ord = ord+10

        for l in webmaplayerswithnonint4keys:
            print("Warning: layer {} has primary key {} of type {}. GetFeatureInfo calls might fail.".format(l["layer"], l["key"], l["type"] ))
            query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
            cursor.execute( query, (parser.prog, project_name, 1, "Warning: layer {} has primary key {} of type {}. GetFeatureInfo calls might fail.".format(l["layer"], l["key"], l["type"] )))

        print('----------------------------------------------------------')
        print(h)
        print('--fim: ok--------------------------------------------------------')
        query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
        cursor.execute( query, ( parser.prog, project_name, 0, "Projeto {} publicado.".format( project_name )))

except (Exception, psycopg2.Error) as e:
    print('--------------Exception-----Exception-----Exception--------------------------------------------------------------------------------')
    print(e)
    print(traceback.format_exc())
    query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
    cursor.execute( query, (parser.prog, project_name, 0, "{}".format(e)))
    query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
    cursor.execute( query, (parser.prog, project_name, 0, "{}".format(traceback.format_exc())))
    query = sql.SQL("INSERT INTO {schema}.{table}(subject,project,loglevel,detail) VALUES (%s, %s, %s, %s)").format( schema=sql.Identifier(schema), table=sql.Identifier(tbl_logger) )
    cursor.execute( query, (parser.prog, project_name, 0, "Erro na publicação do projeto {}.".format( project_name )))                   

finally:
    if cursor is not None:
        cursor.close()
    if conn is not None:
        conn.close()

qgs.exitQgis()
