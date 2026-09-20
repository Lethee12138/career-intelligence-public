#!/bin/zsh
set -eu

LABEL="com.career-intelligence.mcp"
DOMAIN="gui/$(/usr/bin/id -u)"
SERVICE_TARGET="$DOMAIN/$LABEL"
AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$AGENT_DIR/$LABEL.plist"
SCRIPT_PATH="${0:A}"
REPOSITORY_ROOT="${SCRIPT_PATH:h:h}"
NODE_BIN="${CAREER_MCP_NODE_BIN:-/usr/local/bin/node}"
SERVER_PATH="$REPOSITORY_ROOT/mcp/career-mcp-http-server.mjs"
HEALTH_URL="${CAREER_MCP_HEALTH_URL:-http://127.0.0.1:8797/healthz}"
STDOUT_LOG="$HOME/Library/Logs/Career Intelligence/mcp.stdout.log"
STDERR_LOG="$HOME/Library/Logs/Career Intelligence/mcp.stderr.log"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

is_loaded() {
  /bin/launchctl print "$SERVICE_TARGET" >/dev/null 2>&1
}

healthy() {
  /usr/bin/curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1
}
wait_healthy() {
  local attempt
  for attempt in {1..50}; do
    healthy && return 0
    /bin/sleep 0.2
  done
  return 1
}

validate_runtime() {
  [[ -x "$NODE_BIN" ]] || fail "Node unavailable: $NODE_BIN"
  [[ -f "$SERVER_PATH" ]] || fail "Career MCP server missing: $SERVER_PATH"
}

write_plist() {
  local destination="$1"
  /usr/bin/plutil -create xml1 "$destination"
  /usr/bin/plutil -insert Label -string "$LABEL" "$destination"
  /usr/bin/plutil -insert ProgramArguments -array "$destination"
  /usr/bin/plutil -insert ProgramArguments.0 -string "$NODE_BIN" "$destination"
  /usr/bin/plutil -insert ProgramArguments.1 -string "$SERVER_PATH" "$destination"
  /usr/bin/plutil -insert WorkingDirectory -string "$REPOSITORY_ROOT" "$destination"
  /usr/bin/plutil -insert RunAtLoad -bool true "$destination"
  /usr/bin/plutil -insert KeepAlive -bool true "$destination"
  /usr/bin/plutil -insert ProcessType -string Background "$destination"
  /usr/bin/plutil -insert StandardOutPath -string "$STDOUT_LOG" "$destination"
  /usr/bin/plutil -insert StandardErrorPath -string "$STDERR_LOG" "$destination"
  /usr/bin/plutil -lint "$destination" >/dev/null
}
install_service() {
  validate_runtime
  /bin/mkdir -p "$AGENT_DIR" "${STDOUT_LOG:h}"
  local tmp
  tmp="$(/usr/bin/mktemp "$AGENT_DIR/.career-mcp.XXXXXX")"
  write_plist "$tmp"
  /bin/chmod 600 "$tmp"
  if is_loaded; then
    /bin/launchctl bootout "$SERVICE_TARGET"
  fi
  /bin/mv -f "$tmp" "$PLIST_PATH"
  /bin/launchctl bootstrap "$DOMAIN" "$PLIST_PATH"
  wait_healthy || fail "Career MCP LaunchAgent started but health check failed."
  printf 'Career MCP LaunchAgent ready: %s\n' "$SERVICE_TARGET"
}

start_service() {
  validate_runtime
  [[ -f "$PLIST_PATH" ]] || fail "Career MCP LaunchAgent is not installed."
  if is_loaded; then
    healthy && { printf '%s\n' "Career MCP already healthy."; return 0; }
    /bin/launchctl kickstart -k "$SERVICE_TARGET"
  else
    /bin/launchctl bootstrap "$DOMAIN" "$PLIST_PATH"
  fi
  wait_healthy || fail "Career MCP failed health check."
  printf '%s\n' "Career MCP ready."
}
stop_service() {
  if is_loaded; then
    /bin/launchctl bootout "$SERVICE_TARGET"
  fi
  printf '%s\n' "Career MCP stopped."
}

restart_service() {
  validate_runtime
  [[ -f "$PLIST_PATH" ]] || fail "Career MCP LaunchAgent is not installed."
  if is_loaded; then
    /bin/launchctl bootout "$SERVICE_TARGET"
    /bin/sleep 0.5
  fi
  /bin/launchctl bootstrap "$DOMAIN" "$PLIST_PATH"
  wait_healthy || fail "Career MCP restart failed health check."
  printf '%s\n' "Career MCP restarted."
}

status_service() {
  printf 'Installed: %s\n' "$([[ -f "$PLIST_PATH" ]] && echo yes || echo no)"
  printf 'Loaded: %s\n' "$(is_loaded && echo yes || echo no)"
  printf 'Healthy: %s\n' "$(healthy && echo yes || echo no)"
  printf 'MCP URL: http://127.0.0.1:8797/mcp\n'
  printf 'Health URL: %s\n' "$HEALTH_URL"
}

uninstall_service() {
  stop_service
  [[ ! -f "$PLIST_PATH" ]] || /bin/rm -f "$PLIST_PATH"
  printf '%s\n' "Career MCP LaunchAgent uninstalled."
}

case "${1:-status}" in
  install) install_service ;;
  start) start_service ;;
  stop) stop_service ;;
  restart) restart_service ;;
  status) status_service ;;
  uninstall) uninstall_service ;;
  *) printf 'Usage: %s {install|start|stop|restart|status|uninstall}\n' "$SCRIPT_PATH"; exit 2 ;;
esac
