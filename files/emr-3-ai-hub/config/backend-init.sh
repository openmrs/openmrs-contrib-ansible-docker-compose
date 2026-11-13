#!/bin/sh
# Container initialization for emr-3-ai-hub backend:
#   - Heals /openmrs/data ownership when launched as root, then drops to openmrs (uid 1001).
#   - Disables ReferenceDemoDataActivator patient generation (referencedemodata.createDemoPatients=false)
#     so OpenMRS does not spend startup generating 50 synthetic patients over the restored HIV baseline.
#   - Writes /openmrs/data/openmrs-runtime.properties when the pre-restored HIV baseline database
#     already holds an OpenMRS schema, bypassing the first-install wizard on clean boots.
#   - Ensures all-MiniLM-L6-v2 ONNX embedder files exist under /openmrs/data/chartsearchai/
#     (provisioned by hiv-baseline-stage, with HuggingFace fallback if HIV_BASELINE_ENABLED=false).
#   - Delegates to /openmrs/startup.sh without downloading duplicate e5/GGUF weights.
set -eu

if [ "$(id -u)" = "0" ]; then
  chown -R 1001:1001 /openmrs/data 2>/dev/null || true
  exec runuser -u openmrs -- "$0" "$@"
fi

cd /openmrs
touch openmrs-extra.properties
awk '
  BEGIN { print "referencedemodata.createDemoPatients=false" }
  $0 !~ /^[[:space:]]*referencedemodata[.]createDemoPatients[[:space:]]*[:=]/ { print }
' openmrs-extra.properties > openmrs-extra.properties.next
mv openmrs-extra.properties.next openmrs-extra.properties

DB_HOST="${OMRS_DB_HOSTNAME:-${OMRS_CONFIG_CONNECTION_SERVER:-db}}"
DB_PORT="${OMRS_DB_PORT:-3306}"
DB_NAME="${OMRS_DB_NAME:-${OMRS_CONFIG_CONNECTION_DATABASE:-openmrs}}"
DB_USER="${OMRS_DB_USERNAME:-${OMRS_CONFIG_CONNECTION_USERNAME:-openmrs}}"
DB_PASS="${OMRS_DB_PASSWORD:-${OMRS_CONFIG_CONNECTION_PASSWORD:-openmrs}}"

MARIADB_SSL_FLAG=""
if command -v mariadb >/dev/null 2>&1 && mariadb --help 2>/dev/null | grep -q -- '--skip-ssl'; then
  MARIADB_SSL_FLAG="--skip-ssl"
fi

query_db() {
  MYSQL_PWD="$DB_PASS" mariadb $MARIADB_SSL_FLAG -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$@"
}

schema_present() {
  command -v mariadb >/dev/null 2>&1 || return 1
  _tables="$(query_db -Nse \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}' \
     AND table_name IN ('global_property','patient','person','users')" 2>/dev/null | tr -dc '0-9')"
  [ -n "$_tables" ] && [ "$_tables" -ge 4 ]
}

if schema_present; then
  echo "[backend-init] '${DB_NAME}' already carries an OpenMRS schema; setting create_tables=false."
  OMRS_CONFIG_CREATE_TABLES=false
  OMRS_CREATE_TABLES=false
  export OMRS_CONFIG_CREATE_TABLES OMRS_CREATE_TABLES

  RTP_FILE="/openmrs/data/openmrs-runtime.properties"
  if [ ! -f "$RTP_FILE" ]; then
    mkdir -p /openmrs/data
    _db_args="?autoReconnect=true&sessionVariables=default_storage_engine=InnoDB&useUnicode=true&characterEncoding=UTF-8"
    ( umask 077; cat > "$RTP_FILE" <<EOF
#Written by backend-init.sh for a pre-seeded OpenMRS database
connection.driver_class=com.mysql.jdbc.Driver
connection.url=jdbc:mysql://${DB_HOST}:${DB_PORT}/${DB_NAME}${_db_args}
connection.username=${DB_USER}
connection.password=${DB_PASS}
auto_update_database=${OMRS_CONFIG_AUTO_UPDATE_DATABASE:-true}
module.allow_web_admin=${OMRS_CONFIG_MODULE_WEB_ADMIN:-true}
referencedemodata.createDemoPatients=false
EOF
    )
    echo "[backend-init] Wrote $RTP_FILE for ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
  fi
fi

MODEL_DIR="/openmrs/data/chartsearchai"
mkdir -p "$MODEL_DIR"
ONNX_FILE="$MODEL_DIR/model.onnx"
VOCAB_FILE="$MODEL_DIR/vocab.txt"
HF_EMBED="https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main"

if [ ! -s "$ONNX_FILE" ]; then
  echo "[backend-init] Downloading all-MiniLM-L6-v2 ONNX model (~86MB)..."
  curl -fsSL -o "${ONNX_FILE}.tmp" "$HF_EMBED/onnx/model.onnx"
  mv "${ONNX_FILE}.tmp" "$ONNX_FILE"
fi

if [ ! -s "$VOCAB_FILE" ]; then
  echo "[backend-init] Downloading all-MiniLM-L6-v2 vocab..."
  curl -fsSL -o "${VOCAB_FILE}.tmp" "$HF_EMBED/vocab.txt"
  mv "${VOCAB_FILE}.tmp" "$VOCAB_FILE"
fi

exec /openmrs/startup.sh
