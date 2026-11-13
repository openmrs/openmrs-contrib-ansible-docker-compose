# emr-3-audit

O3 Reference Application instance with audit logging: the
[auditlogweb module](https://github.com/openmrs/openmrs-module-auditlogweb)
(Hibernate Envers based) on the backend and
[@openmrs/esm-audit-log-app](https://github.com/openmrs/openmrs-esm-audit-log-app)
on the frontend.

## Images

The `nightly-auditlog` frontend and backend images are built and pushed by
[`build-docker.yml` in openmrs-module-auditlogweb](https://github.com/openmrs/openmrs-module-auditlogweb/blob/main/.github/workflows/build-docker.yml)
(pushes to `main` and a nightly cron). They overlay the module omod and the
audit-log ESM onto the official O3 RefApp `nightly` images. The gateway is the
stock RefApp `nightly` image.

A Docker Hub push of `openmrs/openmrs-reference-application-3-backend:nightly-auditlog`
should trigger automatic redeployment via:

```
deploy-compose-if-newer emr-3-audit openmrs/openmrs-reference-application-3-backend:nightly-auditlog
```

## Envers / audit schema

The backend image bakes in `hibernate.integration.envers.enabled=true` and
`hibernate.hbm2ddl.auto=update` (as `OMRS_EXTRA_*` env var defaults), so the
Envers audit tables (`revision_entity`, `*_AUD`) are created at startup before
core's first audited write. The module additionally creates/syncs audit tables
for anything missing when it starts. No extra configuration is needed here.