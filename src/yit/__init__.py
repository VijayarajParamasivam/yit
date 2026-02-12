import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
import shutil
import zipfile
import tarfile
import requests
from types import SimpleNamespace

# Constants
# Constants
YIT_DIR = Path.home() / ".yit"
YIT_BIN = YIT_DIR / "bin"
RESULTS_FILE = YIT_DIR / "results.json"
HISTORY_FILE = YIT_DIR / "history.json"

if os.name == 'nt':
    IPC_PIPE = r"\\.\pipe\yit_socket"
else:
    IPC_PIPE = str(Path.home() / ".yit" / "socket")

def get_mpv_path():
    """Finds MPV or installs it (Windows only)."""
    # 1. Check local bin (Windows priority for portability)
    if os.name == 'nt':
        local_mpv = YIT_BIN / "mpv.exe"
        if local_mpv.exists():
            return str(local_mpv)

    # 2. Check PATH
    if shutil.which("mpv"):
        return "mpv"

    # 3. Not found.
    system = platform.system()
    if system == "Windows":
        print("MPV not found. Downloading portable MPV for Windows...")
        return download_mpv_windows()
    elif system == "Darwin":
        print("MPV is required. Please run: brew install mpv")
        sys.exit(1)
    else:
        print("MPV is required. Please install it (e.g., sudo apt install mpv).")
        sys.exit(1)

def download_mpv_windows():
    if not YIT_BIN.exists(): YIT_BIN.mkdir(parents=True, exist_ok=True)
    
    try:
        # Fetch latest release
        print("Fetching latest MPV release info...")
        api_url = "https://api.github.com/repos/shinchiro/mpv-winbuild-cmake/releases/latest"
        resp = requests.get(api_url)
        resp.raise_for_status()
        assets = resp.json().get("assets", [])
        
        url = None
        # Prefer main build (mpv-x86_64...) over dev
        for asset in assets:
            if asset["name"].startswith("mpv-x86_64") and asset["name"].endswith(".7z") and "v3" in asset["name"]:
                url = asset["browser_download_url"]
                break
        
        if not url:
            for asset in assets:
                 if asset["name"].startswith("mpv-x86_64") and asset["name"].endswith(".7z"):
                    url = asset["browser_download_url"]
                    break
        
        if not url:
            raise Exception("No suitable MPV build (mpv-x86_64*.7z) found in latest release.")

        print(f"Downloading {url}...")
        archive_path = YIT_BIN / "mpv.7z"
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(archive_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        print("Extracting...")
        print("Extracting (using system tar)...")
        try:
            # Modern Windows (10 build 17063+) has native tar
            subprocess.run(["tar", "-xf", str(archive_path), "-C", str(YIT_BIN)], check=True)
        except Exception as e:
             print(f"Error extracting: {e}")
             print("Please install standard 7-Zip or run 'winget install mpv.mpv'")
             sys.exit(1)
            
        # Flatten: Find mpv.exe and move to YIT_BIN
        found = list(YIT_BIN.rglob("mpv.exe"))
        if not found:
            raise Exception("mpv.exe not found in extracted archive.")
            
        mpv_exe = found[0]
        if mpv_exe.parent != YIT_BIN:
            print(f"Moving {mpv_exe} to {YIT_BIN}...")
            # Move all files from that dir to YIT_BIN to satisfy dependencies? 
            # Usually mpv.exe needs files next to it? No, it's usually portable.
            # But let's verify. Shinchiro builds are usually standalone-ish folders.
            # Let's move the executable.
            shutil.move(str(mpv_exe), str(YIT_BIN / "mpv.exe"))
            
        try:
            os.remove(archive_path)
        except: pass
        
        print("MPV installed successfully.")
        return str(YIT_BIN / "mpv.exe")
        
    except Exception as e:
        print(f"Failed to auto-install MPV: {e}")
        print("Please install it manually via 'winget install mpv.mpv'")
        sys.exit(1)

def ensure_yit_dir():
    if not YIT_DIR.exists():
        YIT_DIR.mkdir()



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

    # Check for duplicates or update
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
    """Sends a JSON-formatted command to the MPV IPC pipe."""
    try:
        with open(IPC_PIPE, "r+b", buffering=0) as f:
            payload = json.dumps(command).encode("utf-8") + b"\n"
            f.write(payload)
            response_line = f.readline().decode("utf-8")
            if response_line:
                return json.loads(response_line)
            return {"error": "no_response"}
    except FileNotFoundError:
        print("Yit is not running.")
        return None
    except Exception as e:
        print(f"Error communicating with player: {e}")
        return None

def get_ipc_property(prop):
    """Gets a property from MPV."""
    try:
        with open(IPC_PIPE, "r+b", buffering=0) as f:
            cmd = {"command": ["get_property", prop]}
            payload = json.dumps(cmd).encode("utf-8") + b"\n"
            f.write(payload)
            
            # Simple read line
            response = f.readline().decode("utf-8")
            return json.loads(response)
    except FileNotFoundError:
        return None
    except Exception:
        return None

def cmd_search(args):
    """Searches YouTube and stores results."""
    ensure_yit_dir()
    query = " ".join(args.query)
    print(f"Searching for '{query}'...")

    # using yt-dlp via subprocess for simplicity and speed
    # ytsearch5: gets 5 results
    cmd = [
        "yt-dlp",
        "--print", "%(title)s|%(id)s",
        "--flat-playlist",
        f"ytsearch5:{query}"
    ]

    try:
        # Use full path to yt-dlp if needed, assuming it's in venv or path
        # In this environment, we should rely on the venv activation or use sys.executable to find it
        # But for now, let's assume 'yt-dlp' is in PATH or we use the one we just installed.
        # Ideally, we should use the library, but subprocess is often more stable for simple "get strings"
        
        # Let's try to use the python library method to be cleaner if possible, 
        # but subprocess is standard for this tool type.
        
        # Use system yt-dlp since we are a package now
        yt_dlp_path = "yt-dlp"
        
        
        command = [str(yt_dlp_path), "--print", "%(title)s||||%(webpage_url)s", "--flat-playlist", f"ytsearch5:{query}"]

        
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
            print(f"Stderr: {result.stderr}")
            return

        if result.stdout is None:
            print("Error: stdout is None")
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

    except subprocess.CalledProcessError as e:
        print(f"Error searching: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}\nTry running the setup_installer.bat")

    if args.play and results:
        print("\nAuto-playing result #1...")
        cmd_play(SimpleNamespace(number=1))

def cmd_play(args):
    """Plays the selected track number."""
    if not RESULTS_FILE.exists():
        print("No search results found. Run 'yit search <query>' first.")
        return

    try:
        with open(RESULTS_FILE, "r") as f:
            results = json.load(f)
        
        idx = args.number - 1
        if idx < 0 or idx >= len(results):
            print("Invalid selection number.")
            return

        track = results[idx]
        print(f"Playing: {track['title']}")
        save_to_history(track)
        
        # Check if running
        is_running = send_ipc_command({"command": ["loadfile", track["url"]]})
        
        if is_running:
             print("Added to existing player.")
             # Ensure it plays immediately even if previously paused
             send_ipc_command({"command": ["set_property", "pause", False]})
        else:
            # Spawn new
            mpv_exe = get_mpv_path()
            cmd = [
                mpv_exe,
                "--no-video",
                "--idle",
                "--cache=yes",
                "--prefetch-playlist=yes",
                "--demuxer-max-bytes=128M",
                "--demuxer-max-back-bytes=128M",
                f"--input-ipc-server={IPC_PIPE}",
                track["url"]
            ]
            # Prepare env with yt-dlp in path
            env = os.environ.copy()
            yt_dlp_path = Path(sys.executable).parent
            env["PATH"] = str(yt_dlp_path) + os.pathsep + env["PATH"]

            # Prepare subprocess args based on OS
            kwargs = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "env": env,
                "close_fds": True
            }

            if os.name == 'nt':
                kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True

            # Detach process
            subprocess.Popen(cmd, **kwargs)
            print("Player started in background.")

    except Exception as e:
        print(f"Error playing: {e}")

def cmd_pause(args):
    send_ipc_command({"command": ["set_property", "pause", True]})
    print("Paused.")

def cmd_resume(args):
    send_ipc_command({"command": ["set_property", "pause", False]})
    print("Resumed.")
    
def cmd_toggle(args):
    send_ipc_command({"command": ["cycle", "pause"]})
    print("Toggled playback.")

def cmd_stop(args):
    send_ipc_command({"command": ["quit"]})
    print("Stopped.")

def cmd_loop(args):
    send_ipc_command({"command": ["set_property", "loop-file", "inf"]})
    print("Looping current track.")

def cmd_unloop(args):
    send_ipc_command({"command": ["set_property", "loop-file", "no"]})
    print("Unlooped. Playback will continue normally.")

def cmd_add(args):
    """Appends the selected track number to the queue."""
    if not RESULTS_FILE.exists():
        print("No search results found. Run 'yit search <query>' first.")
        return

    try:
        with open(RESULTS_FILE, "r") as f:
            results = json.load(f)
        
        idx = args.number - 1
        if idx < 0 or idx >= len(results):
            print("Invalid selection number.")
            return

        track = results[idx]
        print(f"Adding to queue: {track['title']}")
        save_to_history(track)
        
        # Determine if we need to spawn mpv or just append
        # Try to append first
        res = send_ipc_command({"command": ["loadfile", track["url"], "append-play"]})
        
        if not res or res.get("error") != "success":
            # If not running, play normally (which spawns)
            print("Player not running (or append failed), starting new queue...")
            cmd_play(args) # This will spawn it
        else:
            print("Added to queue.")

    except Exception as e:
        print(f"Error adding to queue: {e}")

def cmd_next(args):
    send_ipc_command({"command": ["playlist-next"]})
    print("Skipping to next track...")

def cmd_prev(args):
    send_ipc_command({"command": ["playlist-prev"]})
    print("Going to previous track...")

def cmd_restart(args):
    send_ipc_command({"command": ["seek", 0, "absolute"]})
    send_ipc_command({"command": ["set_property", "pause", False]})
    print("Restarting current track...")

def cmd_clear(args):
    send_ipc_command({"command": ["playlist-clear"]})
    print("Queue cleared.")

def extract_video_id(url):
    """Extracts YouTube Video ID from URL."""
    if not url: return None
    # Standard v= parameter
    if "v=" in url:
        try:
            return url.split("v=")[1].split("&")[0][:11] # ID is 11 chars
        except:
            pass
    # Shortened youtu.be/ID
    if "youtu.be/" in url:
        try:
            return url.split("youtu.be/")[1][:11]
        except:
            pass
    return None

def cmd_queue(args):
    # Get playlist info
    resp = get_ipc_property("playlist")
    if not resp or resp.get("error") != "success":
        print("Queue is empty (or player not running).")
        return

    playlist = resp.get("data", [])
    if not playlist:
        print("Queue is empty.")
        return
    
    # Load local results to resolve titles if missing in MPV
    # Map both full URL and Video ID to title
    url_map = {}
    id_map = {}
    
    # Helper to load a list of items into the maps
    def load_into_maps(items):
        for item in items:
            url = item["url"].strip("| ")
            title = item["title"]
            url_map[url] = title
            vid = extract_video_id(url)
            if vid:
                id_map[vid] = title

    # 1. Load Results (Current Search)
    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE, "r") as f:
                load_into_maps(json.load(f))
        except Exception: pass

    # 2. Load History (Persistent Cache)
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f:
                load_into_maps(json.load(f))
        except Exception: pass

    print("\nCurrent Queue:")
    for i, item in enumerate(playlist):
        prefix = "-> " if item.get("current") else "   "
        
        # Priority: MPV Title -> Local Cache (ID) -> Local Cache (URL) -> Filename -> Unknown
        title = item.get("title")
        
        if not title:
            # MPV 'filename' field holds the URL
            url = item.get("filename", "")
            
            # Try exact match
            if url in url_map:
                title = url_map[url]
            else:
                # Try ID match
                vid = extract_video_id(url)
                if vid and vid in id_map:
                    title = id_map[vid]
                else:
                    title = url or "Unknown"

        print(f"{prefix}{i+1}. {title}")

def cmd_status(args):
    resp = get_ipc_property("media-title")
    if resp and resp.get("error") == "success" and resp.get("data"):
        title = resp.get("data")
        
        # Check pause status
        paused = get_ipc_property("pause")
        looping = get_ipc_property("loop-file")

        status_str = "[Paused]" if paused and paused.get("data") else "[Playing]"
        
        if looping and looping.get("data") in ["inf", "yes"]:
            status_str += " [Looped]"
            
        print(f"{status_str} {title}")
    else:
        # Check if running at least
        if get_ipc_property("idle-active"): 
             print("Queue is empty.")
        else:
             print("Yit is not running.")
            
def cmd_agent(args):
    """Outputs full player state as JSON for AI agents."""
    state = {
        "status": "stopped",
        "track": {},
        "position": 0,
        "duration": 0,
        "volume": 0,
        "loop": False,
        "queue_length": 0
    }

    # Check if running
    idle_resp = get_ipc_property("idle-active")
    if not idle_resp:
        print(json.dumps(state, indent=2))
        return

    # Gather data sequentially
    pause_resp = get_ipc_property("pause")
    title_resp = get_ipc_property("media-title")
    path_resp = get_ipc_property("path") # often URL
    time_resp = get_ipc_property("time-pos")
    dur_resp = get_ipc_property("duration")
    vol_resp = get_ipc_property("volume")
    loop_resp = get_ipc_property("loop-file")
    playlist_resp = get_ipc_property("playlist-count")

    # Process Status
    if pause_resp and pause_resp.get("data") is True:
        state["status"] = "paused"
    elif pause_resp and pause_resp.get("data") is False:
        state["status"] = "playing"

    # Process Track Info
    if title_resp and title_resp.get("data"):
        state["track"]["title"] = title_resp["data"]
    if path_resp and path_resp.get("data"):
        state["track"]["url"] = path_resp["data"]

    # Playback Info
    if time_resp and time_resp.get("data"):
        state["position"] = time_resp["data"]
    if dur_resp and dur_resp.get("data"):
        state["duration"] = dur_resp["data"]
    if vol_resp and vol_resp.get("data"):
        state["volume"] = vol_resp["data"]
    
    # Loop Status
    if loop_resp and loop_resp.get("data") in ["inf", "yes"]:
        state["loop"] = True
    
    # Queue Info
    if playlist_resp and playlist_resp.get("data"):
        state["queue_length"] = playlist_resp["data"]

    print(json.dumps(state, indent=2))

def cmd_commands(args):
    """Outputs available commands as JSON for AI agents."""
    cmds = [
        {"cmd": "search", "usage": "yit search <query> [-p]", "desc": "Search YouTube. -p to auto-play."},
        {"cmd": "play", "usage": "yit play <index>", "desc": "Play a track from results."},
        {"cmd": "add", "usage": "yit add <index>", "desc": "Add a track to queue."},
        {"cmd": "pause", "usage": "yit pause", "desc": "Pause playback."},
        {"cmd": "resume", "usage": "yit resume", "desc": "Resume playback."},
        {"cmd": "stop", "usage": "yit stop", "desc": "Stop playback completely."},
        {"cmd": "next", "usage": "yit next", "desc": "Skip to next track."},
        {"cmd": "back", "usage": "yit back", "desc": "Go to previous track."},
        {"cmd": "loop", "usage": "yit loop", "desc": "Loop current track indefinitely."},
        {"cmd": "unloop", "usage": "yit unloop", "desc": "Stop looping."},
        {"cmd": "queue", "usage": "yit queue", "desc": "Show current queue."},
        {"cmd": "clear", "usage": "yit clear", "desc": "Clear the queue."},
        {"cmd": "status", "usage": "yit status", "desc": "Show playback status (text)."},
        {"cmd": "agent", "usage": "yit agent", "desc": "Get full system state (JSON)."},
        {"cmd": "commands", "usage": "yit commands", "desc": "Get this list (JSON)."},
        {"cmd": "0", "usage": "yit 0", "desc": "Replay current track."}
    ]
    print(json.dumps(cmds, indent=2))

def main():
    # Ensure MPV is available (auto-install on Windows if needed)
    # checking this once here avoids checks later, although get_mpv_path caches fairly well?
    # get_mpv_path checks file existence, which is fast.
    try:
        get_mpv_path()
    except SystemExit:
        return # already printed error

    parser = argparse.ArgumentParser(description="Yit (YouTube in Terminal) - Fire-and-Forget Music Player")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search
    parser_search = subparsers.add_parser("search", help="Search YouTube")
    parser_search.add_argument("query", nargs="+", help="Search query")
    parser_search.add_argument("-p", "--play", action="store_true", help="Auto-play the first result")
    parser_search.set_defaults(func=cmd_search)

    # Play
    parser_play = subparsers.add_parser("play", help="Play a song by number")
    parser_play.add_argument("number", type=int, help="Track number from search results")
    parser_play.set_defaults(func=cmd_play)

    # Controls
    parser_pause = subparsers.add_parser("pause", aliases=["p"], help="Pause playback")
    parser_pause.set_defaults(func=cmd_pause)

    parser_resume = subparsers.add_parser("resume", aliases=["r"], help="Resume playback")
    parser_resume.set_defaults(func=cmd_resume)
    
    parser_toggle = subparsers.add_parser("toggle", help="Toggle pause/resume")
    parser_toggle.set_defaults(func=cmd_toggle)

    parser_stop = subparsers.add_parser("stop", help="Stop playback")
    parser_stop.set_defaults(func=cmd_stop)

    # Add to queue
    parser_add = subparsers.add_parser("add", help="Add song to queue")
    parser_add.add_argument("number", type=int, help="Track number")
    parser_add.set_defaults(func=cmd_add)

    # Queue management
    parser_queue = subparsers.add_parser("queue", help="Show queue")
    parser_queue.set_defaults(func=cmd_queue)

    parser_clear = subparsers.add_parser("clear", help="Clear queue")
    parser_clear.set_defaults(func=cmd_clear)

    # Fast Navigation (Safe Aliases)
    # Next
    parser_next = subparsers.add_parser("next", aliases=["n"], help="Next track")
    parser_next.set_defaults(func=cmd_next)

    # Previous (Back)
    parser_prev = subparsers.add_parser("back", aliases=["b"], help="Previous track")
    parser_prev.set_defaults(func=cmd_prev)

    # Replay/Restart
    parser_restart = subparsers.add_parser("replay", aliases=["0"], help="Replay current track")
    parser_restart.set_defaults(func=cmd_restart)

    parser_status = subparsers.add_parser("status", help="Show status")
    parser_status.set_defaults(func=cmd_status)
    
    # Agent Interface
    parser_agent = subparsers.add_parser("agent", help="JSON output for AI agents")
    parser_agent.set_defaults(func=cmd_agent)

    parser_cmds = subparsers.add_parser("commands", help="JSON command list for AI agents")
    parser_cmds.set_defaults(func=cmd_commands)

    # Loop
    subparsers.add_parser("loop", help="Loop current track").set_defaults(func=cmd_loop)
    subparsers.add_parser("unloop", help="Stop looping").set_defaults(func=cmd_unloop)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
