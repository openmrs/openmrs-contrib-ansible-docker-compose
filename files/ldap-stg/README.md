# Description

LDAP STG (with some test data).


You can check files in `ldifs` ldif files; passwords will be exactly the same as
the username. Check the readme inside the folder for details.

If you want to use the test data, copy the contents of `test-data` into `bootstrap` before starting the container
(or make sure `TEST_DATA_DIR` is not defined in your `.env` file).

By default, it will try to use SSL/letsencrypt certs. Disable it locally by exporting `export LDAP_ENABLE_TLS=no` before running docker compose commands. 

```
# Bring containers up
$ export LDAP_ENABLE_TLS=no
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

## Password hashing

`schemas/passwordhash.ldif` makes OpenLDAP hash passwords with Argon2 instead of the default salted SHA-1
(`{SSHA}`), and makes it hash a password even when a client writes it with a plain modify (otherwise it is
stored in cleartext). Existing hashes in any scheme keep working, and a password is stored with Argon2 the
next time it is written. The OpenMRS ID Keycloak rewrites outdated hashes as users log in (the "Upgrade LDAP
Password Hash" step in openmrs-contrib-itsm-id).

Each bind against an Argon2 hash uses 64 MiB of memory for about 0.1-0.2s. With slapd's default of 16 threads
that is about 1 GiB at peak; lower `m` in the file if the host can't spare it.

The file is only loaded when the directory is first created. To apply it to an existing directory, do this
once, after deploying this version (`docker exec -it <container> bash`, then):

```
# 1. Is there already a ppolicy overlay or a hash setting? If an overlay is listed, remove the last entry from
#    a copy of passwordhash.ldif and add olcPPolicyHashCleartext: TRUE to the existing overlay instead.
ldapsearch -LLL -D "cn=admin,cn=config" -W -b "cn=config" '(|(objectClass=olcPPolicyConfig)(olcPasswordHash=*))' dn olcPasswordHash

# 2. Once the overlay exists, any entry that names a policy in pwdPolicySubentry has that policy enforced.
#    Check which entries do, and that their policy is one you want enforced.
ldapsearch -LLL -D "cn=admin,dc=openmrs,dc=org" -W -b "dc=openmrs,dc=org" '(pwdPolicySubentry=*)' dn pwdPolicySubentry

# 3. Apply it (not idempotent: running it twice loads the module twice)
ldapadd -D "cn=admin,cn=config" -W -f /opt/bitnami/openldap/etc/schema/passwordhash.ldif

# 4. Check: a changed password should now start with {ARGON2}
ldapsearch -LLL -D "cn=admin,dc=openmrs,dc=org" -W -b "uid=<user>,ou=users,dc=openmrs,dc=org" userPassword
```

Do this before enabling the Keycloak rehash step. Until it is done, that step finds LDAP still storing `{SSHA}`,
logs a warning and pauses itself for an hour at a time.

The `bitnami/openldap` images were removed from Docker Hub in 2025; `bitnamilegacy/openldap` is the same build,
but it no longer gets updates.

```
# delete containers and volumes
$ docker-compose down -v
```
