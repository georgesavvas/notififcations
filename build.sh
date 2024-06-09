#!/usr/bin/bash
SRC=${REZ_BUILD_SOURCE_PATH}/source
DEST=${REZ_BUILD_INSTALL_PATH}

# Copy the files into place
cp -ruv ${SRC}/bin ${SRC}/python ${DEST}

# change it's permissions
chmod +x ${DEST}/bin/*
find ${DEST}/python -type f -not -perm 644 -exec chmod 644 {} \;
find ${DEST}/python -type d -not -perm 755 -exec chmod 755 {} \;
