#!/bin/bash

# install npm packages with "npm install coffee-script stylus"
node node_modules/coffee-script/bin/coffee -c -w -b -j static/media.js static/js/*.coffee &
node node_modules/stylus/bin/stylus -c -w -o static static/css/*.styl &

db=${1:-/tmp/media.db}

lmj-media --db $db serve --reload
