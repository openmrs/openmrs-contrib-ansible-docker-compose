# Bootstrap data

Contrary to the `ldap-stg`, this docker compose relies on the structure already being configured.
Use a backup or the files from the staging docker compose.
<https://wiki.openmrs.org/x/6QDfAw>


During boot, it will overridd olcsizelimit <https://issues.openmrs.org/browse/ITSM-4251> to allow more than 500 users to be synced in crowd. Pagination didn't work for some reason and this value seems to change every time the container restart.
