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


## Password hashing

`schemas/passwordhash.ldif` makes Argon2 the default password hash and enables the ppolicy overlay so that
passwords written with a plain modify are hashed rather than stored in cleartext. Like everything in
`schemas/`, it is only applied when the directory is created; changes to it must be applied to an existing
directory by hand with `ldapmodify` against `cn=config`.

Argon2 binds use `m` KiB of memory each (64 MiB), so up to about 1 GiB with slapd's 16 threads.

```
# delete containers and volumes
$ docker-compose down -v
```
