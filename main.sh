#!/bin/bash

# install npm packages with "npm install coffee-script stylus"

node node_modules/coffee-script/bin/coffee -c -w -b static/js &
node node_modules/stylus/bin/stylus -c -w static/css &
python main.py --reload
