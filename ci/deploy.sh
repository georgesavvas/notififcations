#!/bin/bash

set -ex

cd /users/george/dev/services/docker
docker-compose up --remove-orphans -d
