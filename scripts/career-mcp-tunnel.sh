#!/bin/zsh
set -eu

SCRIPT_PATH="${0:A}"
REPOSITORY_ROOT="${SCRIPT_PATH:h:h}"
TUNNEL_BIN="${CAREER_TUNNEL_CLIENT_BIN:-$HOME/Library/Application Support/Career Intelligence/OpenAI Tunnel/v0.0.11/tunnel-client}"
PROFILE_DIR="${CAREER_TUNNEL_PROFILE_DIR:-$HOME/Library/Application Support/Career Intelligence/OpenAI Tunnel/profiles}"
PROFILE_NAME="${CAREER_TUNNEL_PROFILE_NAME:-career-intelligence-local}"
TUNNEL_ID="${CAREER_TUNNEL_ID:-}"
RUNTIME_KEY_FILE="${CAREER_TUNNEL_RUNTIME_KEY_FILE:-}"
MCP_URL="${CAREER_MCP_LOCAL_URL:-http://127.0.0.1:8797/mcp}"
HEALTH_URL="${CAREER_MCP_HEALTH_URL:-http://127.0.0.1:8797/healthz}"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

check_binary() {
  [[ -x "$TUNNEL_BIN" ]] || fail "Tunnel client unavailable: $TUNNEL_BIN"
}

check_local_mcp() {
  /usr/bin/curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1 ||
    fail "Career MCP is not healthy at $HEALTH_URL"
}

check_tunnel_inputs() {
  [[ -n "$TUNNEL_ID" ]] || fail "CAREER_TUNNEL_ID is required."
  [[ -n "$RUNTIME_KEY_FILE" ]] || fail "CAREER_TUNNEL_RUNTIME_KEY_FILE is required."
  [[ -f "$RUNTIME_KEY_FILE" && ! -L "$RUNTIME_KEY_FILE" ]] ||
    fail "Career Tunnel runtime-key file is unavailable or unsafe."
  local mode
  mode="$(/usr/bin/stat -f '%OLp' "$RUNTIME_KEY_FILE")"
  [[ "$mode" == "600" || "$mode" == "400" ]] ||
    fail "Career Tunnel runtime-key file must be mode 0600 or 0400."
}

preflight() {
  check_binary
  check_local_mcp
  printf 'Career MCP: healthy\n'
  printf 'Tunnel client: %s\n' "$("$TUNNEL_BIN" --version 2>/dev/null)"
  if [[ -z "$TUNNEL_ID" ]]; then
    printf 'Career Tunnel ID: REQUIRED\n'
  else
    printf 'Career Tunnel ID: configured\n'
  fi
  if [[ -z "$RUNTIME_KEY_FILE" ]]; then
    printf 'Career runtime key: REQUIRED\n'
  elif [[ -f "$RUNTIME_KEY_FILE" ]]; then
    printf 'Career runtime key: configured\n'
  else
    printf 'Career runtime key: configured path missing\n'
  fi
  printf 'Workspace tunnel/config mutation: none\n'
}

init_profile() {
  check_binary
  check_local_mcp
  check_tunnel_inputs
  /bin/mkdir -p "$PROFILE_DIR"
  "$TUNNEL_BIN" init     --sample sample_mcp_remote_no_auth     --profile-dir "$PROFILE_DIR"     --profile "$PROFILE_NAME"     --tunnel-id "$TUNNEL_ID"     --mcp-server-url "$MCP_URL"     --health-listen-addr "127.0.0.1:0"     --control-plane-api-key-ref "file:$RUNTIME_KEY_FILE"     --force
  printf 'Career Tunnel profile ready: %s/%s.yaml\n' "$PROFILE_DIR" "$PROFILE_NAME"
}

check_existing_profile() {
  [[ -f "$PROFILE_DIR/$PROFILE_NAME.yaml" ]] || fail "Career Tunnel profile is not initialized."
}

doctor_profile() {
  check_binary
  check_local_mcp
  check_existing_profile
  "$TUNNEL_BIN" doctor     --profile-dir "$PROFILE_DIR"     --profile "$PROFILE_NAME"     --explain
}

run_tunnel() {
  check_binary
  check_local_mcp
  check_existing_profile
  "$TUNNEL_BIN" run     --profile-dir "$PROFILE_DIR"     --profile "$PROFILE_NAME"
}

usage() {
  printf 'Usage: %s {preflight|init|doctor|run}\n' "$SCRIPT_PATH"
}

case "${1:-preflight}" in
  preflight) preflight ;;
  init) init_profile ;;
  doctor) doctor_profile ;;
  run) run_tunnel ;;
  help|-h|--help) usage ;;
  *) usage; exit 2 ;;
esac
