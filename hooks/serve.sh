#!/bin/sh
# Start the board server on its port unless this build of it already answers there.
# Messages go to stderr, which Claude Code shows the user when the hook exits 1.
# With --build, print the fingerprint of the server's sources instead.

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
  # What answers on the port: "agent-hud <version> <build>" from this app's /health, "old" for an agent-hud from
  # before /health, which serves the board page at /, "other" for another program, or nothing.
  case $(curl -s -o /dev/null --max-time 2 -w '%{http_code}' "$url") in
    000) ;;
    200) curl -s --max-time 2 "$url" | sed -n 's/.*"app": *"agent-hud".*"version": *"\([^"]*\)".*"build": *"\([^"]*\)".*/agent-hud \1 \2/p' | grep . || echo other ;;
    404) curl -s --max-time 2 "http://127.0.0.1:$port/" | grep -q '<title>agent-hud</title>' && echo old || echo other ;;
    *) echo other ;;
  esac
}

fingerprint() {
  # A checksum of the server's sources, so that a server from older sources is restarted even at the same version.
  find "$server_dir/src" "$server_dir/pyproject.toml" "$server_dir/uv.lock" -type f | LC_ALL=C sort | xargs cat | cksum | cut -d' ' -f1
}

holder() {
  # The pid of the process that listens on the port, found by lsof; nothing without lsof or a listener.
  command -v lsof >/dev/null && lsof -t -i "tcp:$port" -s TCP:LISTEN 2>/dev/null | head -n 1
}

stop() {
  # Stop the agent-hud server on the port: the process that the pid file names, else the one that holds the port
  # when it runs agent-hud's server; then wait for the port to free.
  pid=$(cat "$pid_file" 2>/dev/null)
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    pid=$(holder)
    [ -n "$pid" ] || fail "an older agent-hud answers on port $port; $pid_file names no process to stop, and lsof finds none: stop it or set AGENT_HUD_PORT to a free port"
    args=$(ps -o args= -p "$pid" 2>/dev/null)
    case $args in
      *agent_hud.web*) ;;
      *) fail "an older agent-hud answers on port $port, but pid $pid holds the port and is not agent-hud's server: $args; stop it or set AGENT_HUD_PORT to a free port" ;;
    esac
  fi
  kill "$pid" 2>/dev/null || fail "an older agent-hud answers on port $port and pid $pid cannot be stopped"
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
  export AGENT_HUD_STATE_DIR="$state_dir"
  export AGENT_HUD_BUILD="$build"
  nohup uv run --no-dev --frozen --quiet uvicorn agent_hud.web:app_factory --factory --port "$port" >>"$log" 2>&1 &
  pid=$!
  echo "$pid" >"$pid_file"
  n=0
  while [ "$n" -lt 30 ]; do
    case $(probe) in
      "agent-hud $version $build") exit 0 ;;
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
build=$(fingerprint)
[ -n "$build" ] || fail "no sources in $server_dir"
if [ "$1" = "--build" ]; then
  echo "$build"
  exit 0
fi
mkdir -p "$state_dir" || fail "cannot create $state_dir"

case $(probe) in
  "agent-hud $version $build") exit 0 ;;
  "agent-hud "* | old) stop ;;
  other) fail "another program answers on port $port, without agent-hud's /health or page; stop it or set AGENT_HUD_PORT to a free port" ;;
esac
start
