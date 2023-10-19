# Bootstrap data

The ldif files will create all the basic structure of the ldap: <https://wiki.openmrs.org/x/6QDfAw>
  - Enable ppolicy module
  - Create all `ou=policy` nodes
  - Create top nodes `ou=users`, `ou=groups`, `ou=system`
  - Creates all system users
  - Grant permissions to system users
  - Change olcsizelimit <https://issues.openmrs.org/browse/ITSM-4251> to allow more than 500 users to be synced in crowd. Pagination didn't work for some reason.
