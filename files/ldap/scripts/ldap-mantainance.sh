#!/bin/bash

set -eux

echo hi

#apk update && apk add db db-util

# This script checkpoints the ldab db and then archives the log files.
# Use && to ensure checkpoint is successful before archiving.
# Runs this nightly from crontab.
# db5.3_checkpoint -1 -v -h /ldap_database_data/_data/ && db5.3_archive -d -v -h /ldap_database_data/_data/
