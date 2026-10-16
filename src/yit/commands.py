import os
import sys
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from .config import RESULTS_FILE, HISTORY_FILE, IPC_PIPE, PLAYS_LOG, YIT_DIR, ensure_yit_dir
from .utils import extract_video_id
from .ipc import send_ipc_command, get_ipc_property
from .storage import save_to_history, load_favorites, save_favorites, remember_tracks, log_search
from . import ytdlp

TRACKER_SCRIPT = Path(__file__).with_name("tracker.lua")
from .installer import get_mpv_path

def cmd_search(args):
    """Searches YouTube and stores results."""
    ensure_yit_dir()
    query = " ".join(args.query)
    print(f"Searching for '{query}'...")
    log_search(query)

    results = []
    try:
        results = ytdlp.search(query, 5)
    except Exception as e:
        print(f"Search failed: {e}")
        return

    if not results:
        print("No results found.")
        return

    print("\nResults:")
    for i, t in enumerate(results):
        extra = f"  [{t['channel']}]" if t.get("channel") else ""
        print(f"{i+1}. {t['title']}{extra}")

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    if getattr(args, 'play', False):
        print("\nAuto-playing result #1...")
        cmd_play(SimpleNamespace(number=1))

def _mpv_command(tracks):
    cmd = [
        get_mpv_path(),
        "--no-video",
        "--idle",
        "--cache=yes",
        "--prefetch-playlist=yes",
        "--demuxer-max-bytes=128M",
        "--demuxer-max-back-bytes=128M",
        "--ytdl-format=bestaudio/best",
        f"--log-file={YIT_DIR / 'mpv.log'}",
        f"--input-ipc-server={IPC_PIPE}",
    ]
    opts = [f"yit_tracker-log={PLAYS_LOG}"]
    ytdl = ytdlp.ytdlp_executable()
    if ytdl:
        opts.append(f"ytdl_hook-ytdl_path={ytdl}")
    if TRACKER_SCRIPT.exists():
        cmd.append(f"--script={TRACKER_SCRIPT}")
    cmd.append("--script-opts=" + ",".join(opts))
    cmd += [t["url"] for t in tracks]
    return cmd


def play_tracks(tracks, append=False, source=None):
    """Plays a list of tracks (dicts with 'url' and 'title').
    append=True adds them after the current queue instead of replacing it."""
    if not tracks: return

    remember_tracks(tracks, source=source)
    first_track = tracks[0]
    if append:
        print(f"Queueing {len(tracks)} track(s), starting with: {first_track['title']}")
    else:
        print(f"Playing: {first_track['title']}")
        if len(tracks) > 1:
            print(f"...and {len(tracks)-1} others queued.")

    save_to_history(first_track)

    is_running = send_ipc_command({"command": ["get_property", "idle-active"]})

    if is_running and is_running.get("error") == "success":
        if append:
            for t in tracks:
                send_ipc_command({"command": ["loadfile", t["url"], "append-play"]})
            print("Added to queue.")
            return
        print("Added to existing player.")
        send_ipc_command({"command": ["loadfile", first_track["url"], "replace"]})
        send_ipc_command({"command": ["set_property", "pause", False]})
        for t in tracks[1:]:
            send_ipc_command({"command": ["loadfile", t["url"], "append"]})
    else:
        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "env": ytdlp.player_env(),
            "close_fds": True
        }

        if os.name == 'nt':
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        subprocess.Popen(_mpv_command(tracks), **kwargs)
        print("Player started in background.")

def cmd_play(args):
    if not RESULTS_FILE.exists():
        print("No search results found. Run 'yit search <query>' first.")
        return

    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
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
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
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
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                load_into_maps(json.load(f))
        except Exception: pass

    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                load_into_maps(json.load(f))
        except Exception: pass

    try:
        from .storage import load_catalog
        for vid, meta in load_catalog().items():
            if meta.get("title"):
                id_map.setdefault(vid, meta["title"])
    except Exception:
        pass

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
        {"cmd": "fav", "usage": "yit fav [add|play|list|remove]", "desc": "Manage favorites."},
        {"cmd": "dj", "usage": "yit dj [--size N] [--discovery 0-1]", "desc": "Smart queue from your taste: favourites + new similar songs."},
        {"cmd": "radio", "usage": "yit radio [song or url]", "desc": "Songs similar to the current track (or a given song)."},
        {"cmd": "mix", "usage": "yit mix \"Artist - Song\" ...", "desc": "Queue a list of specific songs."},
        {"cmd": "like", "usage": "yit like", "desc": "Like the current song (adds to favorites, boosts it)."},
        {"cmd": "dislike", "usage": "yit dislike [--artist] [--keep]", "desc": "Never play this song (or artist) again; skips it."},
        {"cmd": "profile", "usage": "yit profile [--json]", "desc": "What yit has learned about your taste."},
        {"cmd": "import", "usage": "yit import <watch-history.json|html> [--all]", "desc": "Import Google Takeout YouTube Music history."}
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
                 with open(RESULTS_FILE, "r", encoding="utf-8") as f:
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


# --- Jarvis / taste commands --------------------------------------------------

def cmd_dj(args):
    from .dj import dj
    print(dj(size=args.size, discovery=args.discovery))

def cmd_radio(args):
    from .dj import radio
    print(radio(" ".join(args.seed) if args.seed else None))

def cmd_mix(args):
    from .dj import play_mix
    print(play_mix(args.songs, replace=not args.append))

def cmd_like(args):
    from .dj import like_current
    print(like_current())

def cmd_dislike(args):
    from .dj import dislike_current
    print(dislike_current(block_artist=args.artist, skip=not args.keep))

def cmd_import(args):
    from .dj import import_takeout
    print(import_takeout(args.file, include_all=args.all))

def cmd_profile(args):
    from .taste import build_profile
    p = build_profile()
    if args.json:
        print(json.dumps(p, indent=2, ensure_ascii=False))
        return
    s = p["summary"]
    print(f"Listening profile  ({p['now']['local_time']}, {p['now']['time_of_day']})")
    print(f"  {s['tracked_plays']} plays, {s['unique_tracks']} tracks, {s['hours_listened']}h tracked, "
          f"{s['skips']} skips, {s['favorites']} favorites" + (f", since {s['since']}" if s['since'] else ""))
    if p["top_artists"]:
        print("\nTop artists:   " + ", ".join(a["artist"] for a in p["top_artists"][:8]))
    if p["this_time_of_day"]["top_artists"]:
        print(f"Your {p['now']['time_of_day']}s:   " + ", ".join(p["this_time_of_day"]["top_artists"]))
    if p["top_tracks"]:
        print("\nTop tracks:")
        for i, t in enumerate(p["top_tracks"][:10]):
            print(f"  {i+1}. {t['title']}" + ("  <3" if t.get("favorite") else ""))
    if p["often_skipped"]:
        print("\nOften skipped: " + "; ".join(t["title"] for t in p["often_skipped"][:5]))
    if p.get("note"):
        print("\n" + p["note"])
