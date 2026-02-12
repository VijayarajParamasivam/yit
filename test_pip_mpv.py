import os
from pathlib import Path

YIT_LIB = Path.home() / ".yit" / "lib"
if os.name == 'nt':
    os.add_dll_directory(str(YIT_LIB))
    os.environ["PATH"] = str(YIT_LIB) + os.pathsep + os.environ["PATH"]

try:
    import mpv
    print(f"Imported mpv: {mpv}")
    print("Attempting to create player...")
    player = mpv.MPV()
    print("Player created successfully!")
except Exception as e:
    print(f"FAILED: {e}")
except OSError as e:
    print(f"FAILED (OSError): {e}")
