import os
from pathlib import Path

YIT_DIR = Path.home() / ".yit"
YIT_BIN = YIT_DIR / "bin"
RESULTS_FILE = YIT_DIR / "results.json"
HISTORY_FILE = YIT_DIR / "history.json"
FAV_FILE = YIT_DIR / "favorites.json"
UPDATE_FILE = YIT_DIR / "update.json"

# Taste / "Jarvis" data
TRACKS_FILE = YIT_DIR / "tracks.json"        # catalog: video id -> title/channel/duration
PLAYS_LOG = YIT_DIR / "plays.jsonl"          # one line per finished track (written by mpv tracker)
SEARCH_LOG = YIT_DIR / "searches.jsonl"      # what the user searched for
DISLIKES_FILE = YIT_DIR / "dislikes.json"    # blocked tracks / artists

IPC_PIPE = str(YIT_DIR / "socket")
if os.name == 'nt':
    IPC_PIPE = r"\\.\pipe\yit_socket"

def ensure_yit_dir():
    YIT_DIR.mkdir(parents=True, exist_ok=True)
