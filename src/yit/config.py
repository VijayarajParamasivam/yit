import os
from pathlib import Path

YIT_DIR = Path.home() / ".yit"
YIT_BIN = YIT_DIR / "bin"
RESULTS_FILE = YIT_DIR / "results.json"
HISTORY_FILE = YIT_DIR / "history.json"
FAV_FILE = YIT_DIR / "favorites.json"
UPDATE_FILE = YIT_DIR / "update.json"

IPC_PIPE = str(YIT_DIR / "socket")
if os.name == 'nt':
    IPC_PIPE = r"\\.\pipe\yit_socket"

def ensure_yit_dir():
    if not YIT_DIR.exists():
        YIT_DIR.mkdir()
