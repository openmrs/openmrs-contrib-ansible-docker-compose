# Description

LDAP containers.

Contrary to the `ldap`, this docker compose relies on the structure already being configured.
Use a backup or the files from the staging docker compose.
<https://wiki.openmrs.org/x/6QDfAw>

By default, it will answer using SSL (but you need to skip certificate verification, as it's self-signed).


```
# Bring containers up
$ docker-compose up -d
```

To investigate data:
```
docker exec -it ldap_openldap_1 bash

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
