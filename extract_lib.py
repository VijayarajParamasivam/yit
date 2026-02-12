import py7zr
from pathlib import Path
import shutil
import os

YIT_LIB = Path.home() / ".yit" / "lib"
ARCHIVE = YIT_LIB / "mpv.7z"

print(f"Archive: {ARCHIVE}")
print(f"Exists: {ARCHIVE.exists()}")
print(f"Size: {ARCHIVE.stat().st_size}")

if ARCHIVE.exists() and ARCHIVE.stat().st_size > 1000:
    print("Extracting...")
    try:
        with py7zr.SevenZipFile(ARCHIVE, mode='r') as z:
            z.extractall(path=YIT_LIB)
        print("Done.")
    except Exception as e:
        print(f"Extraction failed: {e}")
        
    # Search for dll
    found = list(YIT_LIB.rglob("libmpv-2.dll")) + list(YIT_LIB.rglob("mpv-2.dll")) + list(YIT_LIB.rglob("mpv-1.dll"))
    print(f"Found DLLs: {found}")
    
    if found:
        # Move to root of lib
        dll = found[0]
        dest = YIT_LIB / "mpv-2.dll" # python-mpv looks for mpv-2.dll or mpv-1.dll
        if dll != dest:
            shutil.copy(dll, dest)
            print(f"Copied to {dest}")
        
        # Also ensure mpv-1.dll exists for compat
        dest1 = YIT_LIB / "mpv-1.dll"
        if not dest1.exists():
            shutil.copy(dll, dest1)
            print(f"Copied to {dest1}")
            
else:
    print("Archive missing or too small.")
