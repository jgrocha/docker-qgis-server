#!/bin/bash
set -e

cd /build

#TODO: remove desktop
cmake /src \
      -GNinja \
      -DQWT_INCLUDE_DIR=/usr/include/qwt \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/usr/local \
      -DPYTHON_LIBRARY=/usr/lib/x86_64-linux-gnu/libpython2.7.so \
      -DQSCINTILLA_INCLUDE_DIR=/usr/include/qt4 \
      -DQWT_LIBRARY=/usr/lib/libqwt.so \
      -DWITH_DESKTOP=ON \
      -DWITH_SERVER=ON \
      -DBUILD_TESTING=OFF  \

      #-DWITH_INTERNAL_QWTPOLAR=ON

ninja install