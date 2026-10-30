# shellcheck shell=bash
# Sourced by bin/admin and bin/agent. Defines `compose`, which runs this repo's Compose project
# with whichever tool is available:
#   1. $COMPOSE, if set (e.g. COMPOSE=docker-compose)
#   2. docker compose
#   3. podman compose (which delegates to docker-compose or podman-compose)
#   4. docker-compose
# The project is always this repo, regardless of the current directory.

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -n "${COMPOSE:-}" ]; then
  compose_cmd="$COMPOSE"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  compose_cmd="docker compose"
elif command -v podman >/dev/null 2>&1; then
  compose_cmd="podman compose"
  # Silences the "Executing external compose provider" banner podman prints on every run.
  export PODMAN_COMPOSE_WARNING_LOGS=false
elif command -v docker-compose >/dev/null 2>&1; then
  compose_cmd="docker-compose"
else
  echo "error: no Compose tool found (docker compose, podman compose, or docker-compose)" >&2
  exit 1
fi

compose() {
  # shellcheck disable=SC2086 # compose_cmd may be two words ("docker compose")
  $compose_cmd --project-directory "$root" -f "$root/compose.yml" "$@"
}

# Compose allocates a TTY by default; -T is needed when input or output is redirected, so piped
# stdin reaches the command and stdout stays separate from stderr.
tty_flag() {
  if [ -t 0 ] && [ -t 1 ]; then :; else echo "-T"; fi
}
