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

    echo "[hiv-db] Recreating database $DB_NAME and importing $DUMP_FILE..."
    run_mariadb -e \
      "DROP DATABASE IF EXISTS \`${DB_NAME}\`; CREATE DATABASE \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    gzip -dc "$DUMP_FILE" | run_mariadb "$DB_NAME"

    ESCAPED_IMAGE="$(sql_escape "$BASELINE_IMAGE")"
    run_mariadb "$DB_NAME" -e "
      INSERT INTO global_property (property, property_value, description, uuid)
      VALUES (
        'openclinai.hivBaseline.image',
        '${ESCAPED_IMAGE}',
        'Loaded OpenClinAI HIV baseline OCI artifact reference',
        UUID()
      )
      ON DUPLICATE KEY UPDATE property_value = VALUES(property_value);

      INSERT INTO global_property (property, property_value, description, uuid)
      VALUES (
        'chartsearchai.demo.seededDataset',
        'openclinai-hiv-baseline',
        'Marker preventing demo-seed from overwriting the preloaded HIV baseline',
        UUID()
      )
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
