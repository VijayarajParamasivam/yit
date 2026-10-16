import json
from .config import HISTORY_FILE, FAV_FILE, ensure_yit_dir

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

def load_favorites():
    if not FAV_FILE.exists():
        return []
    try:
        with open(FAV_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_favorites(favs):
    ensure_yit_dir()
    with open(FAV_FILE, "w") as f:
        json.dump(favs, f, indent=4)


# --- Taste data -------------------------------------------------------------
import os
import time
from .config import TRACKS_FILE, PLAYS_LOG, SEARCH_LOG, DISLIKES_FILE


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, data):
    ensure_yit_dir()
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def append_jsonl(path, record):
    ensure_yit_dir()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path):
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    except FileNotFoundError:
        pass
    return out


def load_catalog():
    return _read_json(TRACKS_FILE, {})


def remember_tracks(tracks, source=None):
    """Store title/channel/duration for tracks so play logs can be enriched later."""
    if not tracks:
        return
    cat = load_catalog()
    from .utils import extract_video_id
    for t in tracks:
        vid = t.get("id") or extract_video_id(t.get("url", ""))
        if not vid:
            continue
        entry = cat.get(vid, {})
        for k in ("title", "channel", "duration"):
            if t.get(k):
                entry[k] = t[k]
        if source:
            entry["source"] = source
            entry["queued_at"] = int(time.time())
        cat[vid] = entry
    try:
        _write_json(TRACKS_FILE, cat)
    except Exception:
        pass


def log_search(query):
    try:
        append_jsonl(SEARCH_LOG, {"ts": int(time.time()), "query": query})
    except Exception:
        pass


def load_dislikes():
    d = _read_json(DISLIKES_FILE, {})
    return {"tracks": d.get("tracks", {}), "artists": d.get("artists", [])}


def save_dislikes(d):
    _write_json(DISLIKES_FILE, d)
