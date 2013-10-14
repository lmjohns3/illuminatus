#!/bin/bash

# install npm packages with "npm install coffee-script stylus"
node node_modules/coffee-script/bin/coffee -c -w -b -j static/photos.js \
  static/js/{filters,directives,services,controllers,app}.coffee &
node node_modules/stylus/bin/stylus -c -w -o static static/css/photos.styl &

db=${1:-/tmp/photos.db}

lmj-photos --db $db serve --reload
