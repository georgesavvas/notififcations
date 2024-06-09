#!/bin/bash

set -ex

docker build --build-arg UID=$(id -u) --build-arg GID=$(id -g) -t george/cue_rest_api .
