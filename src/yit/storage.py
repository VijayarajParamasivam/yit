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
