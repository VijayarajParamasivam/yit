import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

# Constants
YIT_DIR = Path.home() / ".yit"
RESULTS_FILE = YIT_DIR / "results.json"
HISTORY_FILE = YIT_DIR / "history.json"
IPC_PIPE = r"\\.\pipe\yit_socket"

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
        
        # Adjusting to use 'yt-dlp' command. 
        # Since we are running this script FROM the venv python, `yt-dlp` might not be in the global path,
        # but it should be in the venv Scripts.
        yt_dlp_path = Path(sys.executable).parent / "yt-dlp.exe"
        if not yt_dlp_path.exists():
             # Try without extension (linux/mac)
             yt_dlp_path = Path(sys.executable).parent / "yt-dlp"
        
        if not yt_dlp_path.exists():
             yt_dlp_path = "yt-dlp" # hope for PATH
        
        
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
            cmd = [
                "mpv",
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

            # Detach process
            subprocess.Popen(
                cmd,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
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
        if get_ipc_property("idle-active"): # Just checking communication
             print("Queue is empty.")
        else:
             print("Yit is not running.")

def main():
    parser = argparse.ArgumentParser(description="Yit - Fire-and-Forget Terminal Music Player")
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

    # Loop
    subparsers.add_parser("loop", help="Loop current track").set_defaults(func=cmd_loop)
    subparsers.add_parser("unloop", help="Stop looping").set_defaults(func=cmd_unloop)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
