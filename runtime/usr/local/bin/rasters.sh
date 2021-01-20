SERVER=postgres-server
export PGPASSWORD=20201201

# ------------ORTO--------------

if [ "$( psql -h $SERVER -p 5432 -U drote drote -tAc "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'ortos'" )" = '1' ]
then
    echo "Schema ortos already exists"
else
    echo "Schema ortos does not exist"
    psql -h $SERVER -p 5432 -U drote drote -c "CREATE SCHEMA ortos"
fi

if [ "$( psql -h $SERVER -p 5432 -U drote drote -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema = 'ortos' AND table_name = 'porto_santo_2018'" )" = '1' ]
then
    echo "Table ortos.porto_santo_2018 already exists"
else
    echo "Table ortos.porto_santo_2018 does not exist"
    curl -O https://drote.geomaster.pt/orto_2018.tif
    raster2pgsql -s 5016 -d -I -C -M -l 4,8,16,32,64,128,256,512 orto_2018.tif -F -t 1000x1000 ortos.porto_santo_2018 | psql -h $SERVER -p 5432 -U drote drote
fi

# ------------CADASTRO--------------

if [ "$( psql -h $SERVER -p 5432 -U drote drote -tAc "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'cadastro'" )" = '1' ]
then
    echo "Schema cadastro already exists"
else
    echo "Schema cadastro does not exist"
    psql -h $SERVER -p 5432 -U drote drote -c "CREATE SCHEMA cadastro"
fi

if [ "$( psql -h $SERVER -p 5432 -U drote drote -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema = 'cadastro' AND table_name = '3201015_ad_utm'" )" = '1' ]
then
    echo "Table cadastro.3201015_ad_utm already exist"
else
    echo "Table cadastro.3201015_ad_utm does not exists"
    curl -O https://drote.geomaster.pt/5016/3201015_ad_utm.tif
    curl -O https://drote.geomaster.pt/5016/3201015_ag_utm.tif
    curl -O https://drote.geomaster.pt/5016/3201015_ai_utm.tif
    curl -O https://drote.geomaster.pt/5016/3201015_am_utm.tif
    curl -O https://drote.geomaster.pt/5016/3201015_ao_utm.tif
    curl -O https://drote.geomaster.pt/5016/3201015_ae_utm.tif
    curl -O https://drote.geomaster.pt/5016/3201015_ah_utm.tif
    curl -O https://drote.geomaster.pt/5016/3201015_aj_utm.tif
    curl -O https://drote.geomaster.pt/5016/3201015_an_utm.tif
    for file in *utm.tif
    do
        raster="${file%.*}"
        raster2pgsql -s 5016 -d -I -C -M -l 4,8,16,32,64,128,256,512 $file -F -t 1000x1000 cadastro.$raster | psql -h $SERVER -p 5432 -U drote drote
    done
fi