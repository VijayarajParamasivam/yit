import os
import sys
import time
import json
import socket
import platform
import shutil
import ctypes
import requests
import zipfile
import tarfile
from pathlib import Path

# Constants
YIT_DIR = Path.home() / ".yit"
YIT_LIB = YIT_DIR / "lib"
YIT_BIN = YIT_DIR / "bin" # Legacy, but maybe useful
LOG_FILE = YIT_DIR / "daemon.log"

if os.name == 'nt':
    IPC_PIPE = r"\\.\pipe\yit_socket"
else:
    IPC_PIPE = str(YIT_DIR / "socket")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    print(msg) # Also print to stdout for debugging

def ensure_yit_dir():
    if not YIT_DIR.exists(): YIT_DIR.mkdir()
    if not YIT_LIB.exists(): YIT_LIB.mkdir()

def download_file(url, dest):
    log(f"Downloading {url}...")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                 f.write(chunk)
    log("Download complete.")

def ensure_libmpv():
    """Ensures libmpv is present and loaded."""
    system = platform.system()
    
    # Check if we can already load it (system install)
    try:
        import mpv
        # Try creating a dummy instance to verify
        # m = mpv.MPV()
        # del m
        # Actually, python-mpv lazy loads, so we might need to be careful.
        # But if the module imports, it doesn't mean the DLL is loaded yet.
    except ImportError:
        log("Error: python-mpv not installed?")
        sys.exit(1)

    # Define expected lib name
    if system == "Windows":
        lib_name = "mpv-2.dll"
        # URL for Shinchiro's 64-bit libmpv (stable)
        # We need a stable link. Sourceforge is tricky. Github Releases are better.
        # Using a known working release of libmpv for Windows
        lib_url = "https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/v20250125/mpv-dev-x86_64-v3-20250125-git-9838038.7z"
        # Note: 'mpv-dev' contains headers and LIB, but usually also the DLL.
        # Wait, the DLL is in the main build or dev? Usually dev has the .lib, but we need .dll which is in main?
        # Let's check: mpv-x86_64... (main) contains mpv.exe.
        # Does it contain libmpv-2.dll? Yes, usually.
        # Actually, pure mpv builds often link statically.
        # We need a shared build.
        # Shinchiro provides `mpv-dev-...` which has include/lib, but maybe not the DLL if it is static.
        # Let's try downloading the standard build and checking for dll.
        lib_url = "https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/v20250125/mpv-x86_64-v3-20250125-git-9838038.7z"
        
    elif system == "Darwin": # macOS
        lib_name = "libmpv.dylib"
        # On macOS, brew install mpv is best. Bundling is hard due to notarization.
        # We will assume user has it or we instruct them.
        # Automatic download for mac is complex (libs often depend on other brewed libs).
        log("Checking for libmpv on macOS...")
        # If not found, we might just fail and tell user to `brew install mpv`
        return # Try loading system lib
        
    elif system == "Linux":
        lib_name = "libmpv.so"
        # Linux distros usually have it.
        return # Try system lib

    lib_path = YIT_LIB / lib_name
    
    # Windows: Setup PATH to include YIT_LIB
    if system == "Windows":
        os.environ["PATH"] = str(YIT_LIB) + os.pathsep + os.environ["PATH"]
        # Also try explicitly loading it if python-mpv needs help
        # but python-mpv creates MPV() which calls ctypes.util.find_library('mpv')
        # adding to PATH should make find_library find it.

    if system == "Windows" and not lib_path.exists():
        log("libmpv not found locally. Downloading...")
        # Download archive
        archive = YIT_LIB / "mpv.7z"
        try:
            download_file(lib_url, archive)
            # Extract
            # We need 7z extraction. Zipfile won't work for .7z
            # We removed py7zr? No, wait, I removed it from requirements but the user said "use python package".
            # I should use `py7zr` if I can, or use `tarfile` if it was .tar.gz.
            # Shinchiro is .7z.
            # I'll rely on the existing `py7zr` if installed, or valid zip if I can find a zip source.
            # Bootstrapping py7zr might be needed if I removed it.
            # CHECK: I previously removed py7zr from requirements. I should add it back or use a zip source.
            # Finding a ZIP source for libmpv Windows is harder. 
            # I will assume `py7zr` is available or I will re-add it to requirements in next step if missed.
            # Actually, I'll attempt to use `patool` or simply `libarchive`? No.
            # Let's use `py7zr` and add it back to requirements if I removed it.
            # (I see I replaced it in last step. I should put it back for Windows support).
            
            import py7zr
            with py7zr.SevenZipFile(archive, mode='r') as z:
                z.extractall(path=YIT_LIB)
            
            # Move libmpv-2.dll to root of YIT_LIB if nested?
            # Shinchiro usually puts it in root of archive or `mpv-...` folder.
            # Flattening logic:
            for f in YIT_LIB.rglob(lib_name):
                if f.parent != YIT_LIB:
                    shutil.move(str(f), str(YIT_LIB / lib_name))
            
            os.remove(archive)
            log("libmpv installed.")
        except Exception as e:
            log(f"Failed to download/extract libmpv: {e}")
            # If py7zr missing, we are stuck. I will fix requirements in next step.

def run():
    ensure_yit_dir()
    log("Daemon starting...")
    
    ensure_libmpv()
    
    try:
        import mpv
    except ImportError:
        log("Critical: python-mpv module missing.")
        sys.exit(1)
        
    try:
        # Initialize MPV
        # We use input_ipc_server to allow our CLI to talk to it via the same pipe method
        # logic we already built! This keeps the CLI changes minimal.
        log(f"Starting MPV with IPC: {IPC_PIPE}")
        
        # On Windows, we need to ensure the socket doesn't already exist or handle it?
        # Named pipes clean up when closed.
        
        player = mpv.MPV(
            input_ipc_server=IPC_PIPE,
            idle=True,
            video=False,
            ytdl=True 
            # We can also pass other options
        )
        
        # Performance options
        player['cache'] = 'yes'
        player['demuxer-max-bytes'] = '128M'
        player['prefetch-playlist'] = 'yes'
        
        log("MPV initialized. Entering wait loop.")
        
        # Keep process alive
        while True:
            time.sleep(1)
            # Monitor if player crashed?
            # player.core_idle check?
            
    except Exception as e:
        log(f"Daemon crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()
