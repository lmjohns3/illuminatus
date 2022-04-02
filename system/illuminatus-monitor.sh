#!/bin/bash

# A basic shell script for watching an illuminatus library and triggering the
# import + thumbnailing process for new files.

# Set "run" to the command for running illuminatus, and "watch" to the root
# directory where you want to watch for new files.
illuminatus="illuminatus --config /home/bot/illuminatus/config.yaml"
watch=/home/bot/illuminatus/originals

# This watches the file tree and creates a "trigger" file containing the
# timestamp of the most recent event, whenever something gets created. Multiple
# near-simultaneous events will end up with the timestamp of the last event.
trigger=$(mktemp -d)/trigger
inotifywait -mrq -e create ${watch} | \
  while read x ; do
    t=$(mktemp)
    date +%s > ${t}
    mv ${t} ${trigger}  # update trigger file atomically
  done &

# Whenever the "trigger" file is created, wait until it is sufficiently old,
# then start a new import process. Change illuminatus command-line flags here as
# needed.
inotifywait -mq -e create $(dirname ${trigger}) | \
  while read x ; do
    while (( $(date +%s) < $(cat ${trigger}) + 59 )) ; do sleep 31 ; done
    rm -f ${trigger}
    tag="auto-imported-$(date +%s)"
    ${illuminatus} import --tag ${tag} --path-tags 1 --no-wait --quiet ${watch}
    ${illuminatus} thumbnail --no-wait ${tag}
    ${illuminatus} modify --remove-tag ${tag} ${tag}
  done
