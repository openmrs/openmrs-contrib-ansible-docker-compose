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

## Deployment notes

- Gateway (web UI) is exposed on port **8090**.
- `deploy.env` sets `HEALTH_CHECK_TIMEOUT=3600`: the very first boot runs the
  liquibase install and demo-data generation with every write audited, which
  can take well over 30 minutes. Subsequent boots are fast.
- Volumes are kept between deployments (`DESTROY_VOLUMES=false`).
- Secrets live in the vaulted `.env` (`OPENMRS_DB`, `OPENMRS_DB_USER`,
  `OPENMRS_DB_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`).

## Monitoring

Includes the same Grafana/Loki/Alloy log monitoring stack as `emr-3-dev`,
reachable under `/grafana/` on the gateway.