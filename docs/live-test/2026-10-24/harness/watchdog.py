"""A second monitor on the board: logs each turn, and when the agent session shows no activity after a turn, continues it with the turn."""
import asyncio, json, os, subprocess, sys, time, pathlib
from websockets.asyncio.client import connect

LIVE = pathlib.Path(__file__).parent
URL = "ws://127.0.0.1:7677/agent?board=project-a2c3d0&token=live-token"
LOG = LIVE / "agent_run.jsonl"
ENV = {**os.environ, "AGENT_HUD_PORT": "7677", "AGENT_HUD_TOKEN": "live-token", "XDG_STATE_HOME": str(LIVE / "xdg")}

def agent_activity() -> float:
    return LOG.stat().st_mtime if LOG.exists() else 0.0

def log(msg: str) -> None:
    with open(LIVE / "watchdog.log", "a") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")

async def main() -> None:
    restarts = 0
    started = time.time()
    while time.time() - started < 3600:
        try:
            async with connect(URL, proxy=None) as monitor:
                log("monitor open")
                async for line in monitor:
                    with open(LIVE / "turns.log", "a") as f:
                        f.write(line + "\n")
                    log(f"turn: {line[:120]}")
                    before = agent_activity()
                    await asyncio.sleep(90)
                    # keep_alive lines also touch the log, so look for an assistant event after the turn instead
                    recent = [l for l in LOG.read_text().splitlines()[-40:] if '"type":"assistant"' in l or '"type": "assistant"' in l]
                    if agent_activity() > before and recent:
                        log("agent active; nothing to do")
                        continue
                    if restarts >= 3:
                        log("agent idle after the turn, and the restart limit is spent; giving up")
                        return
                    restarts += 1
                    log(f"agent idle after the turn; continuing its session with the turn (restart {restarts} of 3)")
                    subprocess.run(["pkill", "-f", "[c]laude --plugin-dir /home/user/agent-hud"], check=False)
                    prompt = (
                        "Your monitor had ended, so this turn of the user reached you here instead. Handle it per your brief: "
                        "act on every action, say what you changed, then call listen and open the Monitor again (description board) "
                        "and wait for the next turn. The turn: " + line
                    )
                    with open(LIVE / "agent_run.jsonl", "a") as out, open(LIVE / "agent_run.err", "a") as err:
                        subprocess.Popen(
                            ["claude", "--plugin-dir", "/home/user/agent-hud", "-c", "-p", prompt, "--max-turns", "120",
                             "--allowedTools", "mcp__plugin_agent-hud_board__listen,mcp__plugin_agent-hud_board__read,mcp__plugin_agent-hud_board__write,Monitor,Write,Read,Skill",
                             "--output-format", "stream-json", "--verbose"],
                            cwd=LIVE / "project", env=ENV, stdout=out, stderr=err,
                        )
        except Exception as e:
            log(f"monitor error: {e!r}")
            await asyncio.sleep(3)
    log("lifetime over; stopping")

asyncio.run(main())
