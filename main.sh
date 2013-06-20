#!/bin/bash

# install npm packages with "npm install coffee-script stylus"

node_modules/coffee-script/bin/coffee -cbw static/js &
coffee_pid=$!

node_modules/stylus/bin/stylus -c -w static/css &
stylus_pid=$!

python main.py --reload

kill $stylus_pid
kill $coffee_pid
