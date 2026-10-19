import subprocess
import sys


def open_browser(url: str) -> bool:
    """Open a URL in the default browser without touching our stdio, which carries MCP."""
    match sys.platform:
        case "darwin":
            command = ["open", url]
        case "win32":
            command = ["cmd", "/c", "start", "", url]
        case _:
            command = ["xdg-open", url]
    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True
