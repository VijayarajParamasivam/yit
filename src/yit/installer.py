import os
import shutil
import platform
import subprocess
import requests
import sys

from .config import YIT_BIN

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
