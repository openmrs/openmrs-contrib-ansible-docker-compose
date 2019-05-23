# Description

LDAP STG (with some test data).
It currently have two ldap containers (as we'll be migrating the data from the old one to the new one soon).


You can check files in `bootstrap` ldif files; passwords will be exactly the same as
the username.

By default, it will answer using SSL (but you need to skip certificate verification, as it's self-signed).


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

If connecting from your local machine:

```
ldapsearch -LLL -D "cn=admin,cn=config" -W -h 127.0.0.1 -p 3389 -b "cn=config"
```

```
# delete containers and volumes
$ docker-compose down -v
```
