#!/bin/zsh
set -eu

LABEL="com.career-intelligence.tunnel"
DOMAIN="gui/$(/usr/bin/id -u)"
SERVICE_TARGET="$DOMAIN/$LABEL"
AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$AGENT_DIR/$LABEL.plist"
SCRIPT_PATH="${0:A}"
TUNNEL_BIN="${CAREER_TUNNEL_CLIENT_BIN:-$HOME/Library/Application Support/Career Intelligence/OpenAI Tunnel/v0.0.11/tunnel-client}"
PROFILE_DIR="${CAREER_TUNNEL_PROFILE_DIR:-$HOME/Library/Application Support/Career Intelligence/OpenAI Tunnel/profiles}"
PROFILE_NAME="${CAREER_TUNNEL_PROFILE_NAME:-career-intelligence-local}"
STDOUT_LOG="$HOME/Library/Logs/Career Intelligence/tunnel.stdout.log"
STDERR_LOG="$HOME/Library/Logs/Career Intelligence/tunnel.stderr.log"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

is_loaded() {
  /bin/launchctl print "$SERVICE_TARGET" >/dev/null 2>&1
}

validate_runtime() {
  [[ -x "$TUNNEL_BIN" ]] || fail "Tunnel client unavailable."
  [[ -f "$PROFILE_DIR/$PROFILE_NAME.yaml" ]] || fail "Career Tunnel profile missing."
}
write_plist() {
  local destination="$1"
  /usr/bin/plutil -create xml1 "$destination"
  /usr/bin/plutil -insert Label -string "$LABEL" "$destination"
  /usr/bin/plutil -insert ProgramArguments -array "$destination"
  /usr/bin/plutil -insert ProgramArguments.0 -string "$TUNNEL_BIN" "$destination"
  /usr/bin/plutil -insert ProgramArguments.1 -string "run" "$destination"
  /usr/bin/plutil -insert ProgramArguments.2 -string "--profile-dir" "$destination"
  /usr/bin/plutil -insert ProgramArguments.3 -string "$PROFILE_DIR" "$destination"
  /usr/bin/plutil -insert ProgramArguments.4 -string "--profile" "$destination"
  /usr/bin/plutil -insert ProgramArguments.5 -string "$PROFILE_NAME" "$destination"
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
  tmp="$(/usr/bin/mktemp "$AGENT_DIR/.career-tunnel.XXXXXX")"
  write_plist "$tmp"
  /bin/chmod 600 "$tmp"
  if is_loaded; then
    /bin/launchctl bootout "$SERVICE_TARGET"
  fi
  /bin/mv -f "$tmp" "$PLIST_PATH"
  /bin/launchctl bootstrap "$DOMAIN" "$PLIST_PATH"
  /bin/sleep 2
  is_loaded || fail "Career Tunnel LaunchAgent failed to load."
  printf 'Career Tunnel LaunchAgent ready: %s\n' "$SERVICE_TARGET"
}

status_service() {
  printf 'Installed: %s\n' "$([[ -f "$PLIST_PATH" ]] && echo yes || echo no)"
  printf 'Loaded: %s\n' "$(is_loaded && echo yes || echo no)"
  if is_loaded; then
    /bin/launchctl print "$SERVICE_TARGET" | /usr/bin/grep -E 'state =|pid =|last exit code' | /usr/bin/head -10
  fi
}
stop_service() {
  if is_loaded; then
    /bin/launchctl bootout "$SERVICE_TARGET"
  fi
  printf '%s\n' "Career Tunnel stopped."
}

restart_service() {
  validate_runtime
  [[ -f "$PLIST_PATH" ]] || fail "Career Tunnel LaunchAgent is not installed."
  if is_loaded; then
    /bin/launchctl bootout "$SERVICE_TARGET"
    /bin/sleep 0.5
  fi
  /bin/launchctl bootstrap "$DOMAIN" "$PLIST_PATH"
  /bin/sleep 2
  is_loaded || fail "Career Tunnel restart failed."
  printf '%s\n' "Career Tunnel restarted."
}

uninstall_service() {
  stop_service
  [[ ! -f "$PLIST_PATH" ]] || /bin/rm -f "$PLIST_PATH"
  printf '%s\n' "Career Tunnel LaunchAgent uninstalled."
}

case "${1:-status}" in
  install) install_service ;;
  status) status_service ;;
  stop) stop_service ;;
  restart) restart_service ;;
  uninstall) uninstall_service ;;
  *) printf 'Usage: %s {install|status|stop|restart|uninstall}\n' "$SCRIPT_PATH"; exit 2 ;;
esac
