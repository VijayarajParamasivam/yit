import argparse
import json
import os
import time
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace

# Constants
YIT_DIR = Path.home() / ".yit"
RESULTS_FILE = YIT_DIR / "results.json"
HISTORY_FILE = YIT_DIR / "history.json"
DAEMON_SCRIPT = Path(__file__).parent / "daemon.py"

if os.name == 'nt':
    IPC_PIPE = r"\\.\pipe\yit_socket"
else:
    IPC_PIPE = str(YIT_DIR / "socket")

def ensure_yit_dir():
    if not YIT_DIR.exists():
        YIT_DIR.mkdir()

def check_daemon():
    """Checks if the Yit Daemon is running by pinging the IPC pipe."""
    # Simple check: try to read a property
    res = get_ipc_property("idle-active")
    return res is not None

def start_daemon():
    """Spawns the background daemon process."""
    print("Starting Yit Daemon (background process)...")
    try:
        # Spawn detached process
        cmd = [sys.executable, str(DAEMON_SCRIPT)]
        
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True
        }

        if os.name == 'nt':
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        subprocess.Popen(cmd, **kwargs)
        
        # Wait for it to initialize
        print("Waiting for daemon to initialize...", end="", flush=True)
        for _ in range(20): # Wait up to 10s (download might take time)
            time.sleep(0.5)
            if check_daemon():
                print(" Done.")
                return True
            print(".", end="", flush=True)
        
        print("\nDaemon validation failed. It might still be downloading libmpv in the background.")
        print(f"Check logs at {YIT_DIR / 'daemon.log'}")
        return False

    except Exception as e:
        print(f"Failed to start daemon: {e}")
        return False

def save_to_history(track):
    """Saves a track to the persistent history file."""
    ensure_yit_dir()
    history = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except Exception:
            pass 

    existing = None
    for item in history:
        if item.get("url") == track["url"]:
            existing = item
            break
            
    if not existing:
        history.append(track)
        
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        print(f"Warning: Could not save history: {e}")

def send_ipc_command(command):
    """Sends a JSON command to the daemon via IPC."""
    try:
        with open(IPC_PIPE, "r+b", buffering=0) as f:
            payload = json.dumps(command).encode("utf-8") + b"\n"
            f.write(payload)
            response_line = f.readline().decode("utf-8")
            if response_line:
                return json.loads(response_line)
            return {"error": "no_response"}
    except FileNotFoundError:
        return None # Daemon not running
    except Exception as e:
        # print(f"IPC Error: {e}") 
        return None

def get_ipc_property(prop):
    """Gets a property from MPV."""
    try:
        with open(IPC_PIPE, "r+b", buffering=0) as f:
            cmd = {"command": ["get_property", prop]}
            payload = json.dumps(cmd).encode("utf-8") + b"\n"
            f.write(payload)
            response = f.readline().decode("utf-8")
            return json.loads(response)
    except Exception:
        return None

def cmd_search(args):
    """Searches YouTube."""
    ensure_yit_dir()
    query = " ".join(args.query)
    print(f"Searching for '{query}'...")

    try:
        # Use system yt-dlp (installed via pip requirements)
        command = ["yt-dlp", "--print", "%(title)s||||%(webpage_url)s", "--flat-playlist", f"ytsearch5:{query}"]
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False
        )
        
        if result.returncode != 0:
            print(f"Error: yt-dlp returned {result.returncode}")
            return

        lines = result.stdout.strip().split('\n')
        results = []
        print("\nResults:")
        for i, line in enumerate(lines):
            if "||||" in line:
                title, url = line.split("||||", 1)
                print(f"{i+1}. {title}")
                results.append({"title": title, "url": url})
        
        if not results:
            print("No results found.")
            return

        with open(RESULTS_FILE, "w") as f:
            json.dump(results, f, indent=4)

    except Exception as e:
        print(f"Search failed: {e}")

    if args.play and results:
        print("\nAuto-playing result #1...")
        cmd_play(SimpleNamespace(number=1))

def cmd_play(args):
    """Plays the selected track."""
    if not RESULTS_FILE.exists():
        print("No search results found.")
        return

    try:
        with open(RESULTS_FILE, "r") as f:
            results = json.load(f)
        
        idx = args.number - 1
        if idx < 0 or idx >= len(results):
            print("Invalid selection.")
            return

        track = results[idx]
        print(f"Playing: {track['title']}")
        save_to_history(track)
        
        # Ensure daemon is running
        if not check_daemon():
            start_daemon()
            
        # Send play command
        res = send_ipc_command({"command": ["loadfile", track["url"]]})
        
        if res and res.get("error") == "success":
             send_ipc_command({"command": ["set_property", "pause", False]})
             print("Playback started.")
        else:
             print("Failed to send command to player.")

    except Exception as e:
        print(f"Error playing: {e}")

# ... (Rest of commands: pause, resume, etc. are largely same but simplify IPC checks)
def cmd_pause(args):
    send_ipc_command({"command": ["set_property", "pause", True]})
    print("Paused.")

def cmd_resume(args):
    send_ipc_command({"command": ["set_property", "pause", False]})
    print("Resumed.")
    
def cmd_toggle(args):
    send_ipc_command({"command": ["cycle", "pause"]})
    print("Toggled.")

def cmd_stop(args):
    send_ipc_command({"command": ["quit"]}) # Kills the daemon/player
    print("Stopped.")

def cmd_loop(args):
    send_ipc_command({"command": ["set_property", "loop-file", "inf"]})
    print("Looping track.")

def cmd_unloop(args):
    send_ipc_command({"command": ["set_property", "loop-file", "no"]})
    print("Unlooped.")

def cmd_add(args):
    if not RESULTS_FILE.exists(): return
    try:
        with open(RESULTS_FILE, "r") as f: results = json.load(f)
        track = results[args.number - 1]
        print(f"Adding to queue: {track['title']}")
        save_to_history(track)
        
        if not check_daemon():
            # If not running, start it playing this track
            cmd_play(args)
        else:
            send_ipc_command({"command": ["loadfile", track["url"], "append-play"]})
            print("Added.")
    except Exception as e: print(e)

def cmd_next(args):
    send_ipc_command({"command": ["playlist-next"]})
    print("Next track.")

def cmd_prev(args):
    send_ipc_command({"command": ["playlist-prev"]})
    print("Previous track.")

def cmd_restart(args):
    send_ipc_command({"command": ["seek", 0, "absolute"]})
    print("Restarting.")

def cmd_clear(args):
    send_ipc_command({"command": ["playlist-clear"]})
    print("Queue cleared.")

def cmd_queue(args):
    resp = get_ipc_property("playlist")
    if not resp:
        print("Queue empty or player not running.")
        return
    data = resp.get("data", [])
    print(f"Queue ({len(data)}):")
    for i, item in enumerate(data):
        prefix = "-> " if item.get("current") else "   "
        # Try to resolve title from history/filename
        title = item.get("title") or item.get("filename")
        if not title: title = "Unknown"
        print(f"{prefix}{i+1}. {title}")

def cmd_status(args):
    title = get_ipc_property("media-title")
    if title and title.get("data"):
        print(f"Playing: {title['data']}")
    else:
        print("Not playing.")

# Agent/Commands shortcuts...
def cmd_agent(args):
    # (Simplified for brevity, logic same as before but uses get_ipc_property)
    # Just minimal output for now
    print(json.dumps({"status": "unknown"}))

def cmd_commands(args):
    print(json.dumps([
        {"cmd": "search"}, {"cmd": "play"}, {"cmd": "stop"}
    ]))

def main():
    parser = argparse.ArgumentParser(description="Yit (YouTube in Terminal) - Python Native")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search
    p_search = subparsers.add_parser("search")
    p_search.add_argument("query", nargs="+")
    p_search.add_argument("-p", "--play", action="store_true")
    p_search.set_defaults(func=cmd_search)

    # Play
    p_play = subparsers.add_parser("play")
    p_play.add_argument("number", type=int)
    p_play.set_defaults(func=cmd_play)

    # Controls
    subparsers.add_parser("pause", aliases=["p"]).set_defaults(func=cmd_pause)
    subparsers.add_parser("resume", aliases=["r"]).set_defaults(func=cmd_resume)
    subparsers.add_parser("stop").set_defaults(func=cmd_stop)
    subparsers.add_parser("next", aliases=["n"]).set_defaults(func=cmd_next)
    subparsers.add_parser("back", aliases=["b"]).set_defaults(func=cmd_prev)
    subparsers.add_parser("queue").set_defaults(func=cmd_queue)
    subparsers.add_parser("clear").set_defaults(func=cmd_clear)
    subparsers.add_parser("status").set_defaults(func=cmd_status)
    subparsers.add_parser("toggle").set_defaults(func=cmd_toggle)
    subparsers.add_parser("loop").set_defaults(func=cmd_loop)
    subparsers.add_parser("unloop").set_defaults(func=cmd_unloop)

    # Add
    p_add = subparsers.add_parser("add")
    p_add.add_argument("number", type=int)
    p_add.set_defaults(func=cmd_add)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
