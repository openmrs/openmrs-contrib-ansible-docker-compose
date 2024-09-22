# Description

LDAP STG (with some test data).


You can check files in `ldifs` ldif files; passwords will be exactly the same as
the username. Check the readme inside the folder for details.

If you want to use the test data, copy the contents of `test-data` into `bootstrap` before starting the container
(or make sure `TEST_DATA_DIR` is not defined in your `.env` file).

By default, it will try to use SSL/letsencrypt certs. Disable it locally by exporting `export LDAP_ENABLE_TLS=no` before running docker compose commands. 

```
# Bring containers up
$ docker-compose up -d
```

To investigate data:
```
docker exec -it ldap-stg_openldap_1 bash

# see all data
ldapsearch -LLL -D "cn=admin,dc=openmrs,dc=org" -W -b "dc=openmrs,dc=org"
>>> password: admin

## see all config
ldapsearch -LLL -D "cn=admin,cn=config" -W -b "cn=config"
>>> password: config

## test password
ldapwhoami -D "uid=testadmin,ou=users,dc=openmrs,dc=org" -W
>>> testadmin

```
# delete containers and volumes
$ docker-compose down -v
```
