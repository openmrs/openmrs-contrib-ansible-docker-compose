## ID staging - keycloak and postfix

Details can be found [openmrs-contrib-itsm-id](https://github.com/openmrs/openmrs-contrib-itsm-id/tree/main). 

When this instance starts from an empty container, `realm-export.json` will be imported as `openmrs` realm. It can be accessed in `https://id-stg.openmrs.org` . This realm file is only imported if the realm doesn't already exist ([docs](https://www.keycloak.org/server/importExport#_importing_a_realm_during_startup))


Master domain can be access with username and password defined in `.env` file. It can accessed via `https://id-stg.openmrs.org/admin` . This is how one can apply changes to Keycloak. 

The exported realm do _not_ have clients, including the Atlassian client configured (via SAML). If that's needed on any environment, check the [docs](https://github.com/openmrs/openmrs-contrib-itsm-id/tree/main?tab=readme-ov-file#connecting-to-atlassian) to configure after startup. It also doesn't have groups or roles exported. 

The realm file was generated by exporting the production realm (no roles, groups or clients), and manually adding the SMTP and ldap passwords, as well as editing the LDAP address and email domain. Recaptcha also needs to be updated.

We are currently not doing backups on postgres, as most of the configurations can be loaded from the exported configuration file. 