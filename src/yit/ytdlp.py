"""yt-dlp helpers.

Always runs yt-dlp through the current interpreter (``python -m yt_dlp``) so it
works even when pip put the ``yt-dlp`` script in a folder that isn't on PATH
(the default for per-user installs on Windows).
"""
import json
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

from .storage import remember_tracks


def _scripts_dirs():
    """Every Scripts/bin dir pip may have installed console scripts into."""
    dirs = []
    schemes = [None]
    for name in ("nt_user", "posix_user", "osx_framework_user"):
        if name in sysconfig.get_scheme_names():
            schemes.append(name)
    for scheme in schemes:
        try:
            d = sysconfig.get_path("scripts", scheme) if scheme else sysconfig.get_path("scripts")
        except Exception:
            continue
        if d and d not in dirs:
            dirs.append(d)
    exe_dir = str(Path(sys.executable).parent)
    if exe_dir not in dirs:
        dirs.append(exe_dir)
    return dirs


def ytdlp_executable():
    """Path to a yt-dlp executable for mpv's ytdl_hook, or None."""
    found = shutil.which("yt-dlp")
    if found:
        return found
    names = ["yt-dlp.exe", "yt-dlp"] if os.name == "nt" else ["yt-dlp"]
    for d in _scripts_dirs():
        for n in names:
            p = Path(d) / n
            if p.exists():
                return str(p)
    return None


def player_env():
    """Environment with every pip scripts dir on PATH, so mpv finds yt-dlp and
    yt-dlp finds the `deno` JS runtime it needs to unlock YouTube streams."""
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(_scripts_dirs() + [env.get("PATH", "")])
    return env


def _run_json(target, extra=None, timeout=60):
    cmd = [sys.executable, "-m", "yt_dlp", "-J", "--flat-playlist", "--no-warnings"]
    cmd += extra or []
    cmd.append(target)
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", stdin=subprocess.DEVNULL, timeout=timeout,
                         env=player_env())
    if res.returncode != 0:
        raise RuntimeError((res.stderr or "yt-dlp failed").strip().splitlines()[-1])
    return json.loads(res.stdout)


def _entry_to_track(e):
    vid = e.get("id")
    if not vid or len(vid) != 11:
        return None
    return {
        "title": e.get("title") or vid,
        "url": f"https://www.youtube.com/watch?v={vid}",
        "id": vid,
        "channel": e.get("channel") or e.get("uploader") or "",
        "duration": e.get("duration") or 0,
    }


def search(query, n=5):
    """Search YouTube; returns list of track dicts (title, url, id, channel, duration)."""
    data = _run_json(f"ytsearch{n}:{query}")
    tracks = [t for t in (_entry_to_track(e) for e in data.get("entries") or []) if t]
    remember_tracks(tracks)
    return tracks


def mix(video_id, limit=40):
    """YouTube's own auto-generated 'Mix' (radio) for a video: similar songs."""
    url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
    data = _run_json(url, ["--playlist-end", str(limit)])
    tracks = [t for t in (_entry_to_track(e) for e in data.get("entries") or []) if t]
    remember_tracks(tracks)
    return tracks
