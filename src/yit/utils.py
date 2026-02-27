import time
import json
import requests
import threading
from importlib.metadata import version, PackageNotFoundError

from .config import UPDATE_FILE

try:
    __version__ = version("yit-player")
except PackageNotFoundError:
    __version__ = "unknown"

def check_for_updates():
    """Checks PyPI for a newer version once a day in a background thread."""
    def _check():
        try:
            now = time.time()
            # Enforce 24h cache (86400 seconds)
            if UPDATE_FILE.exists():
                try:
                    with open(UPDATE_FILE, "r") as f:
                        data = json.load(f)
                        if now - data.get("last_checked", 0) < 86400:
                            return
                except: pass

            resp = requests.get("https://pypi.org/pypi/yit-player/json", timeout=3)
            resp.raise_for_status()
            latest = resp.json()["info"]["version"]
            
            with open(UPDATE_FILE, "w") as f:
                json.dump({"last_checked": now, "latest_version": latest}, f)
        except Exception:
            pass # Fail silently
            
    t = threading.Thread(target=_check, daemon=True)
    t.start()

def show_update_notice():
    """Prints a non-blocking notice if an update is available."""
    if __version__ == "unknown" or not UPDATE_FILE.exists():
        return
        
    try:
        with open(UPDATE_FILE, "r") as f:
            data = json.load(f)
            latest = data.get("latest_version")
            if latest and _is_newer(latest, __version__):
                print(f"\033[93m[Update Available: yit-player {latest}] Run `pip install --upgrade yit-player`\033[0m")
    except Exception:
        pass

def _is_newer(latest, current):
    """Simple semver comparison."""
    try:
        def pad(v): return [int(x) for x in v.split('.')] + [0,0,0]
        return pad(latest)[:3] > pad(current)[:3]
    except: return False

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
