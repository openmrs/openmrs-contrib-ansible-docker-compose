# Description

LDAP containers, updated to bitnami image

Contrary to the `ldap`, this docker compose relies on the structure already being configured.
Use a backup or the files from the staging docker compose.
<https://wiki.openmrs.org/x/6QDfAw>


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

After importing the files into production, make sure to update the password for atlas and omrsid system users. 


```
# delete containers and volumes
$ docker-compose down -v
```
