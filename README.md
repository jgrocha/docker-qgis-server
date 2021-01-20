# Docker image for QGIS server

This image is based on Camptocamp [docker-qgis-server](https://github.com/camptocamp/docker-qgis-server)

This fork uses Apache fcgi support to call qgis_mapserv.fcgi.

This fork was created to support Apache rewrite rules able to change environment variables, like `QGIS_PROJECT_FILE`.

## MapProxy

This image includes MapProxy. MapProxy can be used in front of QGIS Server to provide a fast tile service.

## Usage

This image is used together with Postgresql and a Web app called Geomasterboard.
