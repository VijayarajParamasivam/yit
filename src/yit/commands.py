import os
import sys
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from .config import RESULTS_FILE, HISTORY_FILE, IPC_PIPE, ensure_yit_dir
from .utils import extract_video_id
from .ipc import send_ipc_command, get_ipc_property
from .storage import save_to_history, load_favorites, save_favorites
from .installer import get_mpv_path

def cmd_search(args):
    """Searches YouTube and stores results."""
    ensure_yit_dir()
    query = " ".join(args.query)
    print(f"Searching for '{query}'...")

    cmd = [
        "yt-dlp",
        "--print", "%(title)s|%(id)s",
        "--flat-playlist",
        f"ytsearch5:{query}"
    ]

    try:
        yt_dlp_path = "yt-dlp"
        
        command = [str(yt_dlp_path), "--print", "%(title)s||||%(webpage_url)s", "--flat-playlist", f"ytsearch5:{query}"]
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
            stdin=subprocess.DEVNULL
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

    except Exception as e:
        print(f"Unexpected error: {e}\nTry running the setup_installer.bat")

    if getattr(args, 'play', False) and results:
        print("\nAuto-playing result #1...")
        cmd_play(SimpleNamespace(number=1))

def play_tracks(tracks):
    """Plays a list of tracks (dicts with 'url' and 'title')."""
    if not tracks: return

    first_track = tracks[0]
    print(f"Playing: {first_track['title']}")
    if len(tracks) > 1:
        print(f"...and {len(tracks)-1} others queued.")

    save_to_history(first_track)
    
    is_running = send_ipc_command({"command": ["get_property", "idle-active"]})
    
    if is_running and is_running.get("error") == "success":
         print("Added to existing player.")
         send_ipc_command({"command": ["loadfile", first_track["url"], "replace"]})
         send_ipc_command({"command": ["set_property", "pause", False]})
         
         for t in tracks[1:]:
             send_ipc_command({"command": ["loadfile", t["url"], "append"]})
    else:
        mpv_exe = get_mpv_path()
        cmd = [
            mpv_exe,
            "--no-video",
            "--idle",
            "--cache=yes",
            "--prefetch-playlist=yes",
            "--demuxer-max-bytes=128M",
            "--demuxer-max-back-bytes=128M",
            f"--input-ipc-server={IPC_PIPE}"
        ]
        
        for t in tracks:
            cmd.append(t["url"])

        env = os.environ.copy()
        yt_dlp_path = Path(sys.executable).parent
        env["PATH"] = str(yt_dlp_path) + os.pathsep + env["PATH"]

        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "env": env,
            "close_fds": True
        }

        if os.name == 'nt':
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        subprocess.Popen(cmd, **kwargs)
        print("Player started in background.")

def cmd_play(args):
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
        play_tracks([track])

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
        
        res = send_ipc_command({"command": ["loadfile", track["url"], "append-play"]})
        
        if not res or res.get("error") != "success":
            print("Player not running (or append failed), starting new queue...")
            cmd_play(args)
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

def cmd_queue(args):
    resp = get_ipc_property("playlist")
    if not resp or resp.get("error") != "success":
        print("Queue is empty (or player not running).")
        return

    playlist = resp.get("data", [])
    if not playlist:
        print("Queue is empty.")
        return
    
    url_map = {}
    id_map = {}
    
    def load_into_maps(items):
        for item in items:
            url = item["url"].strip("| ")
            title = item["title"]
            url_map[url] = title
            vid = extract_video_id(url)
            if vid:
                id_map[vid] = title

    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE, "r") as f:
                load_into_maps(json.load(f))
        except Exception: pass

    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f:
                load_into_maps(json.load(f))
        except Exception: pass

    print("\nCurrent Queue:")
    for i, item in enumerate(playlist):
        prefix = "-> " if item.get("current") else "   "
        
        title = item.get("title")
        
        if not title:
            url = item.get("filename", "")
            
            if url in url_map:
                title = url_map[url]
            else:
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
        
        paused = get_ipc_property("pause")
        looping = get_ipc_property("loop-file")

        status_str = "[Paused]" if paused and paused.get("data") else "[Playing]"
        
        if looping and looping.get("data") in ["inf", "yes"]:
            status_str += " [Looped]"
            
        print(f"{status_str} {title}")
    else:
        if get_ipc_property("idle-active"): 
             print("Queue is empty.")
        else:
             print("Yit is not running.")
            
def cmd_agent(args):
    state = {
        "status": "stopped",
        "track": {},
        "position": 0,
        "duration": 0,
        "volume": 0,
        "loop": False,
        "queue_length": 0
    }

    idle_resp = get_ipc_property("idle-active")
    if not idle_resp:
        print(json.dumps(state, indent=2))
        return

    pause_resp = get_ipc_property("pause")
    title_resp = get_ipc_property("media-title")
    path_resp = get_ipc_property("path")
    time_resp = get_ipc_property("time-pos")
    dur_resp = get_ipc_property("duration")
    vol_resp = get_ipc_property("volume")
    loop_resp = get_ipc_property("loop-file")
    playlist_resp = get_ipc_property("playlist-count")

    if pause_resp and pause_resp.get("data") is True:
        state["status"] = "paused"
    elif pause_resp and pause_resp.get("data") is False:
        state["status"] = "playing"

    if title_resp and title_resp.get("data"):
        state["track"]["title"] = title_resp["data"]
    if path_resp and path_resp.get("data"):
        state["track"]["url"] = path_resp["data"]

    if time_resp and time_resp.get("data"):
        state["position"] = time_resp["data"]
    if dur_resp and dur_resp.get("data"):
        state["duration"] = dur_resp["data"]
    if vol_resp and vol_resp.get("data"):
        state["volume"] = vol_resp["data"]
    
    if loop_resp and loop_resp.get("data") in ["inf", "yes"]:
        state["loop"] = True
    
    if playlist_resp and playlist_resp.get("data"):
        state["queue_length"] = playlist_resp["data"]

    print(json.dumps(state, indent=2))

def cmd_commands(args):
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
        {"cmd": "0", "usage": "yit 0", "desc": "Replay current track."},
        {"cmd": "fav", "usage": "yit fav [add|play|list|remove]", "desc": "Manage favorites."}
    ]
    print(json.dumps(cmds, indent=2))

def cmd_fav(args):
    favs = load_favorites()

    if args.action == "list":
        if not favs:
            print("No favorites yet.")
            return
        print("\nFavorites:")
        for i, track in enumerate(favs):
            print(f"{i+1}. {track['title']}")
    
    elif args.action == "add":
        track_to_add = None
        
        if args.target:
             if not RESULTS_FILE.exists():
                print("No search results found.")
                return
             try:
                 with open(RESULTS_FILE, "r") as f:
                     results = json.load(f)
                 idx = int(args.target) - 1
                 if 0 <= idx < len(results):
                     track_to_add = results[idx]
                 else:
                     print("Invalid index.")
                     return
             except Exception as e:
                 print(f"Error reading results: {e}")
                 return
        
        else:
            path_resp = get_ipc_property("path")
            title_resp = get_ipc_property("media-title")
            
            if path_resp and path_resp.get("data") and title_resp and title_resp.get("data"):
                 track_to_add = {"title": title_resp["data"], "url": path_resp["data"]}
            else:
                print("No track selected or playing. Specify an index from search results or play a song first.")
                return

        if track_to_add:
            if any(f["url"] == track_to_add["url"] for f in favs):
                print(f"Already in favorites: {track_to_add['title']}")
            else:
                favs.append(track_to_add)
                save_favorites(favs)
                print(f"Added to favorites: {track_to_add['title']}")

    elif args.action == "remove":
        if not args.target:
            print("Specify an index to remove (run 'yit fav list').")
            return
        try:
            idx = int(args.target) - 1
            if 0 <= idx < len(favs):
                removed = favs.pop(idx)
                save_favorites(favs)
                print(f"Removed: {removed['title']}")
            else:
                print("Invalid index.")
        except ValueError:
            print("Invalid index found (must be a number).")

    elif args.action == "play":
        if not favs:
            print("No favorites to play.")
            return

        if args.target:
            try:
                idx = int(args.target) - 1
                if 0 <= idx < len(favs):
                    track = favs[idx]
                    play_tracks([track])
                else:
                    print("Invalid index.")
            except ValueError:
                print("Invalid index.")
        
        else:
            print(f"Playing all {len(favs)} favorites...")
            play_tracks(favs)
