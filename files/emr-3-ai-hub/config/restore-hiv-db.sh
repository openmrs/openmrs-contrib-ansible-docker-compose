#!/bin/sh
set -eu

MODE="${1:-}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${OMRS_DB_NAME:-openmrs}"
DB_USER="${RESTORE_DB_USER:-root}"
DB_PASSWORD="${MYSQL_ROOT_PASSWORD:-${OMRS_DB_PASSWORD:-}}"
STAGING_DIR="${STAGING_DIR:-/staging}"
BASELINE_IMAGE="${HIV_BASELINE_IMAGE:-ghcr.io/pmanko/openclinai-hiv-baseline@sha256:6d828211831ef5bf1d37955bf024bc422383a63b9af728d1fa40e4c1acbd5394}"

if [ -z "$DB_PASSWORD" ]; then
  echo "[hiv-db] ERROR: database password is empty" >&2
  exit 1
fi

run_mariadb() {
  mariadb -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" --password="$DB_PASSWORD" "$@"
}

sql_escape() {
  printf '%s' "$1" | sed "s/'/''/g"
}

mkdir -p "$STAGING_DIR"

case "$MODE" in
  probe)
    CURRENT=""
    if [ "${HIV_BASELINE_ENABLED:-true}" != "false" ]; then
      CURRENT="$(run_mariadb -Nse \
        "SELECT property_value FROM global_property WHERE property='openclinai.hivBaseline.image' LIMIT 1" \
        "$DB_NAME" 2>/dev/null || true)"
    fi
    printf '%s\n' "$CURRENT" > "${STAGING_DIR}/db-baseline-image"
    echo "[hiv-db] Probed baseline tag: ${CURRENT:-<none>}"
    ;;

  restore)
    NEEDS_RESTORE="no"
    if [ -f "${STAGING_DIR}/needs-db-restore" ]; then
      NEEDS_RESTORE="$(tr -d '\r\n' < "${STAGING_DIR}/needs-db-restore")"
    fi

    if [ "$NEEDS_RESTORE" != "yes" ]; then
      echo "[hiv-db] Database already matches HIV baseline; skipping import"
      rm -f "${STAGING_DIR}/openmrs.sql.gz"
      exit 0
    fi

    DUMP_FILE="${STAGING_DIR}/openmrs.sql.gz"
    if [ ! -f "$DUMP_FILE" ]; then
      echo "[hiv-db] ERROR: expected staged dump at $DUMP_FILE" >&2
      exit 1
    fi

    SAFE_DB="$(printf '%s' "$DB_NAME" | tr -cd 'A-Za-z0-9_')"
    if [ "$SAFE_DB" != "$DB_NAME" ] || [ -z "$SAFE_DB" ]; then
      echo "[hiv-db] ERROR: unsafe database name '$DB_NAME'" >&2
      exit 1
    fi

    APP_DB_USER="${OMRS_DB_USER:-openmrs}"
    SAFE_USER="$(printf '%s' "$APP_DB_USER" | tr -cd 'A-Za-z0-9_.-')"
    if [ "$SAFE_USER" != "$APP_DB_USER" ] || [ -z "$SAFE_USER" ]; then
      echo "[hiv-db] ERROR: unsafe database user '$APP_DB_USER'" >&2
      exit 1
    fi
    ESCAPED_USER="$(sql_escape "$APP_DB_USER")"

    echo "[hiv-db] Recreating database $DB_NAME and importing $DUMP_FILE..."
    run_mariadb -e "
      DROP DATABASE IF EXISTS \`${DB_NAME}\`;
      CREATE DATABASE \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
      GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${ESCAPED_USER}'@'%';
      FLUSH PRIVILEGES;
    "
    gzip -dc "$DUMP_FILE" | run_mariadb --default-character-set=utf8mb4 "$DB_NAME"

    OUTBOX_CHANGESET="20260519-create-outbox-event-table"
    OUTBOX_TABLE="$(run_mariadb -Nse "
      SELECT COUNT(*) FROM information_schema.tables
      WHERE table_schema = DATABASE() AND table_name = 'outbox_event';" "$DB_NAME" || echo 0)"
    if [ "$OUTBOX_TABLE" = "1" ]; then
      OUTBOX_ROWS="$(run_mariadb -Nse "SELECT COUNT(*) FROM outbox_event;" "$DB_NAME" || echo 0)"
      if [ "$OUTBOX_ROWS" != "0" ]; then
        echo "[hiv-db] ERROR: outbox_event holds ${OUTBOX_ROWS} rows for changeset ${OUTBOX_CHANGESET}; migrate explicitly" >&2
        exit 1
      fi
      echo "[hiv-db] Dropping empty outbox_event table so Core Liquibase recreates it cleanly..."
      run_mariadb "$DB_NAME" -e "
        DROP TABLE outbox_event;
        DELETE FROM liquibasechangelog WHERE ID = '${OUTBOX_CHANGESET}' AND AUTHOR = 'rkorytkowski';
      "
    fi

    ESCAPED_IMAGE="$(sql_escape "$BASELINE_IMAGE")"
    run_mariadb "$DB_NAME" -e "
      INSERT INTO global_property (property, property_value, description, uuid)
      VALUES
        ('openclinai.hivBaseline.image', '${ESCAPED_IMAGE}', 'Loaded OpenClinAI HIV baseline OCI artifact reference', UUID()),
        ('chartsearchai.demo.seededDataset', '5284-2026-05-19', 'Marker preventing demo-seed from overwriting the preloaded HIV baseline', UUID()),
        ('referencedemodata.createDemoPatientsOnNextStartup', '0', 'Prevent ReferenceDemoDataActivator from generating synthetic patients over the HIV baseline', UUID()),
        ('querystore.backend', 'elasticsearch', 'QueryStore CQRS read-store backend', UUID()),
        ('querystore.embedding.modelFilePath', 'chartsearchai/model.onnx', 'Path relative to OpenMRS app data directory for all-MiniLM-L6-v2 ONNX model', UUID()),
        ('querystore.embedding.vocabFilePath', 'chartsearchai/vocab.txt', 'Path relative to OpenMRS app data directory for WordPiece vocab', UUID()),
        ('querystore.bootstrap.autostart', 'true', 'Verify/resume QueryStore bootstrap cursor on startup', UUID()),
        ('chartsearchai.querystore.enabled', 'true', 'Enable QueryStore retrieval path in ChartSearchAI', UUID())
      ON DUPLICATE KEY UPDATE property_value = VALUES(property_value);
    "

    rm -f "$DUMP_FILE"
    echo "[hiv-db] HIV baseline database restore complete"
    ;;

  *)
    echo "Usage: $0 {probe|restore}" >&2
    exit 2
    ;;
esac
