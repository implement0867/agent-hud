#!/bin/sh
# Start the board server on its port unless this version of it already answers there.
# Messages go to stderr, which Claude Code shows the user when the hook exits 1.

port="${AGENT_HUD_PORT:-7676}"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/agent-hud"
log="$state_dir/server.log"
pid_file="$state_dir/server.pid"
server_dir="${CLAUDE_PLUGIN_ROOT}/server"
url="http://127.0.0.1:$port/health"

fail() {
  echo "agent-hud: $*" >&2
  exit 1
}

probe() {
  # What answers on the port: "agent-hud <version>", "other" for another program, or nothing.
  case $(curl -s -o /dev/null --max-time 2 -w '%{http_code}' "$url") in
    000) ;;
    200) curl -s --max-time 2 "$url" | sed -n 's/.*"app": *"agent-hud".*"version": *"\([^"]*\)".*/agent-hud \1/p' | grep . || echo other ;;
    *) echo other ;;
  esac
}

stop() {
  # Stop the server that the pid file names, and wait for the port to free.
  pid=$(cat "$pid_file" 2>/dev/null) && kill "$pid" 2>/dev/null ||
    fail "an older agent-hud answers on port $port and $pid_file names no process to stop"
  n=0
  while [ -n "$(probe)" ]; do
    [ "$n" -lt 20 ] || fail "agent-hud (pid $pid) still answers on port $port 10 s after it was told to stop"
    sleep 0.5
    n=$((n + 1))
  done
}

start() {
  cd "$server_dir" || fail "no server directory at $server_dir"
  [ -d .venv ] || echo "agent-hud: starting, the first run installs its dependencies" >&2
  nohup uv run --no-dev --frozen --quiet uvicorn agent_hud.web:create_app --factory --port "$port" >>"$log" 2>&1 &
  pid=$!
  echo "$pid" >"$pid_file"
  n=0
  while [ "$n" -lt 30 ]; do
    case $(probe) in
      "agent-hud $version") exit 0 ;;
    esac
    kill -0 "$pid" 2>/dev/null || fail "the server stopped at once, see $log"
    sleep 0.5
    n=$((n + 1))
  done
  fail "the server does not answer on port $port after 15 s, see $log"
}

command -v uv >/dev/null || fail "uv is not installed, see https://docs.astral.sh/uv/"
version=$(sed -n 's/^version = "\(.*\)"$/\1/p' "$server_dir/pyproject.toml")
[ -n "$version" ] || fail "no version in $server_dir/pyproject.toml"
mkdir -p "$state_dir" || fail "cannot create $state_dir"

case $(probe) in
  "agent-hud $version") exit 0 ;;
  "agent-hud "*) stop ;;
  other) fail "another program answers on port $port; set AGENT_HUD_PORT to a free port" ;;
esac
start
