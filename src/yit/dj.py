"""The 'Jarvis' layer: radio, smart DJ queues, likes/dislikes and history import.

Functions here return human-readable strings so both the CLI and the MCP server
can surface them directly.
"""
import html
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from . import ytdlp
from .config import PLAYS_LOG
from .ipc import get_ipc_property, send_ipc_command
from .storage import (append_jsonl, load_dislikes, load_favorites, read_jsonl,
                      remember_tracks, save_dislikes, save_favorites)
from .taste import clean_title, guess_artist, load_events, time_bucket, track_stats
from .utils import extract_video_id

MAX_TRACK_SECONDS = 15 * 60  # skip hour-long compilations in radio/DJ picks


def _player_running():
    r = get_ipc_property("idle-active")
    return bool(r and r.get("error") == "success")


def _current_track():
    path = get_ipc_property("path")
    title = get_ipc_property("media-title")
    url = path.get("data") if path else None
    if not url:
        return None
    return {"url": url, "id": extract_video_id(url),
            "title": (title or {}).get("data") or url}


def _play(tracks, append=False, source=None):
    from .commands import play_tracks  # avoid import cycle
    play_tracks(tracks, append=append, source=source)


def _filter(tracks, stats, exclude=(), allow_heard=True):
    """Drop disliked/blocked, frequently skipped, overlong and duplicate tracks."""
    dis = load_dislikes()
    blocked = {a.lower() for a in dis["artists"]}
    seen_ids, seen_titles, out = set(exclude), set(), []
    for t in tracks:
        vid = t.get("id")
        if not vid or vid in seen_ids or vid in dis["tracks"]:
            continue
        if guess_artist(t.get("title"), t.get("channel")).lower() in blocked:
            continue
        if (t.get("duration") or 0) > MAX_TRACK_SECONDS:
            continue
        s = stats.get(vid)
        if s and (s.get("disliked") or (s["skips"] >= 2 and s["score"] < 0)):
            continue
        if s and not allow_heard:
            continue
        key = clean_title(t.get("title", "")).lower()
        if key in seen_titles:
            continue
        seen_ids.add(vid)
        seen_titles.add(key)
        out.append(t)
    return out


def _weighted_sample(items, weights, k):
    items, weights, out = list(items), [max(w, 0.01) for w in weights], []
    while items and len(out) < k:
        i = random.choices(range(len(items)), weights=weights)[0]
        out.append(items.pop(i))
        weights.pop(i)
    return out


def _as_track(s):
    return {"title": s["title"], "url": f"https://www.youtube.com/watch?v={s['id']}", "id": s["id"]}


def _recent_ids(events, hours):
    cutoff = time.time() - hours * 3600
    return {e["id"] for e in events if e["ts"] >= cutoff}


def _resolve_seed(seed, stats):
    """seed may be a URL/video id, a search query, or None (current track / top track)."""
    if seed:
        vid = extract_video_id(seed) or (seed if re.fullmatch(r"[\w-]{11}", seed) else None)
        if vid:
            return {"id": vid, "title": stats.get(vid, {}).get("title", vid),
                    "url": f"https://www.youtube.com/watch?v={vid}"}
        hits = ytdlp.search(seed, 1)
        return hits[0] if hits else None
    cur = _current_track()
    if cur and cur["id"]:
        return cur
    bucket = time_bucket()
    liked = [s for s in stats.values() if not s.get("disliked") and s["score"] > 0]
    if not liked:
        return None
    best = max(liked, key=lambda s: s["score"] + s["buckets"].get(bucket, 0))
    return _as_track(best)


def radio(seed=None, size=25):
    """Endless-ish queue of songs similar to the seed, via YouTube's own Mix."""
    stats = track_stats()
    playing = _current_track()
    s = _resolve_seed(seed, stats)
    if not s:
        return "No seed: nothing is playing and there's no listening history yet. Give me a song to start from."
    tracks = ytdlp.mix(s["id"], limit=size + 15)
    continuing = not seed and playing and playing.get("id") == s["id"]
    exclude = {s["id"]} if continuing else set()
    picks = _filter(tracks, stats, exclude=exclude)[:size]
    if not picks:
        return f"Couldn't build a radio from '{s['title']}'."
    if continuing:
        send_ipc_command({"command": ["playlist-clear"]})
        _play(picks, append=True, source="radio")
        head = f"Radio from '{clean_title(s['title'])}' queued after the current song"
    else:
        if picks[0]["id"] != s["id"]:
            picks.insert(0, s)
        _play(picks, source="radio")
        head = f"Radio started from '{clean_title(s['title'])}'"
    return head + f" ({len(picks)} tracks):\n" + "\n".join(
        f"{i+1}. {clean_title(t['title'])}" for i, t in enumerate(picks[:10])) + ("\n..." if len(picks) > 10 else "")


def dj(size=20, discovery=0.4):
    """Smart queue from your taste: favourites you haven't heard lately + new similar songs."""
    events = load_events()
    stats = track_stats(events)
    bucket = time_bucket()
    liked = [s for s in stats.values() if not s.get("disliked") and s["score"] > 0]
    if not liked:
        return ("No listening history yet, so I can't DJ for you. Play a few songs (yit learns from what you "
                "finish vs skip), add favorites, or import your YouTube Music history with "
                "`yit import watch-history.json`.")
    rank = lambda s: s["score"] + 0.6 * s["buckets"].get(bucket, 0)  # noqa: E731
    liked.sort(key=rank, reverse=True)
    recent = _recent_ids(events, 3)

    discovery = min(max(discovery, 0.0), 1.0)
    n_new = round(size * discovery)
    pool = [s for s in liked[:60] if s["id"] not in recent]
    familiar = _weighted_sample(pool, [rank(s) for s in pool], size - n_new)
    n_new = size - len(familiar)

    seeds = _weighted_sample(liked[:12], [rank(s) for s in liked[:12]], 3)
    with ThreadPoolExecutor(max_workers=3) as ex:
        mixes = list(ex.map(lambda s: _safe_mix(s["id"]), seeds))
    exclude = {s["id"] for s in familiar} | recent
    fresh_lists = [_filter(m, stats, exclude=exclude, allow_heard=False) for m in mixes]
    fresh, seen = [], set()
    while len(fresh) < n_new and any(fresh_lists):
        for lst in fresh_lists:
            while lst and lst[0]["id"] in seen:
                lst.pop(0)
            if lst and len(fresh) < n_new:
                t = lst.pop(0)
                seen.add(t["id"])
                fresh.append(t)

    fam_tracks = [_as_track(s) for s in familiar]
    queue = []
    # Open with a sure thing, then interleave known favourites with discoveries.
    while fam_tracks or fresh:
        if fam_tracks:
            queue.append(fam_tracks.pop(0))
        if fresh and (not fam_tracks or random.random() < max(discovery, 0.3) * 1.5):
            queue.append(fresh.pop(0))
    if not queue:
        return "Couldn't build a queue right now (YouTube lookups failed?)."
    _play(queue, source="dj")
    n_fresh = sum(1 for t in queue if t["id"] not in stats)
    lines = [f"{'+' if t['id'] not in stats else ' '} {clean_title(t['title'])}" for t in queue[:12]]
    return (f"DJ mix for your {bucket}: {len(queue)} tracks ({n_fresh} new to you, marked +), "
            f"seeded from {', '.join(clean_title(s['title']) for s in seeds)}.\n" + "\n".join(lines)
            + ("\n..." if len(queue) > 12 else ""))


def _safe_mix(vid):
    try:
        return ytdlp.mix(vid, limit=30)
    except Exception:
        return []


def play_mix(songs, replace=True):
    """Resolve a list of 'Artist - Song' queries to top YouTube results and queue them in order."""
    songs = [s.strip() for s in songs if s and s.strip()]
    if not songs:
        return "No songs given."

    def top(q):
        try:
            hits = ytdlp.search(q, 1)
            return hits[0] if hits else None
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=6) as ex:
        found = list(ex.map(top, songs))
    stats = track_stats()
    tracks = _filter([t for t in found if t], stats)
    missing = [q for q, t in zip(songs, found) if not t]
    if not tracks:
        return "Couldn't find any of those songs."
    _play(tracks, append=not replace, source="claude")
    msg = ("Playing" if replace else "Queued") + f" {len(tracks)} tracks:\n" + "\n".join(
        f"{i+1}. {clean_title(t['title'])}" for i, t in enumerate(tracks))
    if missing:
        msg += "\nNot found: " + "; ".join(missing)
    return msg


def like_current():
    cur = _current_track()
    if not cur:
        return "Nothing is playing."
    favs = load_favorites()
    dis = load_dislikes()
    if cur["id"] and cur["id"] in dis["tracks"]:
        dis["tracks"].pop(cur["id"])
        save_dislikes(dis)
    if any(f.get("url") == cur["url"] or extract_video_id(f.get("url", "")) == cur["id"] for f in favs):
        return f"Already a favorite: {cur['title']}"
    favs.append({"title": cur["title"], "url": cur["url"]})
    save_favorites(favs)
    return f"Liked & added to favorites: {cur['title']}"


def dislike_current(block_artist=False, skip=True):
    cur = _current_track()
    if not cur or not cur["id"]:
        return "Nothing is playing."
    dis = load_dislikes()
    dis["tracks"][cur["id"]] = cur["title"]
    msg = f"Got it, won't play '{clean_title(cur['title'])}' again"
    if block_artist:
        cat_channel = None
        try:
            from .storage import load_catalog
            cat_channel = load_catalog().get(cur["id"], {}).get("channel")
        except Exception:
            pass
        artist = guess_artist(cur["title"], cat_channel)
        if artist and artist != "Unknown" and artist not in dis["artists"]:
            dis["artists"].append(artist)
            msg += f" (and blocked artist '{artist}')"
    save_dislikes(dis)
    favs = [f for f in load_favorites() if extract_video_id(f.get("url", "")) != cur["id"]]
    save_favorites(favs)
    if skip:
        r = send_ipc_command({"command": ["playlist-next"]})
        if not r or r.get("error") != "success":
            send_ipc_command({"command": ["stop"]})
        msg += ". Skipped."
    return msg


# --- Google Takeout import ------------------------------------------------------

def _parse_takeout_json(text, include_all):
    out = []
    for e in json.loads(text):
        if not include_all and e.get("header") != "YouTube Music":
            continue
        vid = extract_video_id(e.get("titleUrl", ""))
        if not vid:
            continue
        title = re.sub(r"^Watched\s+", "", e.get("title", ""))
        channel = (e.get("subtitles") or [{}])[0].get("name", "")
        try:
            ts = int(datetime.fromisoformat(e["time"].replace("Z", "+00:00")).timestamp())
        except Exception:
            continue
        out.append({"id": vid, "title": title, "channel": channel, "ts": ts})
    return out


_HTML_CELL = re.compile(
    r'mdl-typography--title">(?P<header>[^<]+)<br>.*?'
    r'href="(?P<url>https://(?:music\.)?(?:www\.)?youtube\.com/watch\?v=[\w-]{11}[^"]*)">(?P<title>[^<]*)</a>'
    r'(?:<br><a href="[^"]*">(?P<channel>[^<]*)</a>)?<br>(?P<date>[^<]+)<br>', re.S)


def _parse_takeout_html(text, include_all):
    out = []
    for m in _HTML_CELL.finditer(text):
        if not include_all and m.group("header").strip() != "YouTube Music":
            continue
        raw = html.unescape(m.group("date")).replace(" ", " ").strip()
        raw = re.sub(r"\s+[A-Z]{2,5}$", "", raw)  # drop tz abbreviation
        ts = None
        for fmt in ("%b %d, %Y, %I:%M:%S %p", "%d %b %Y, %H:%M:%S", "%b %d, %Y, %H:%M:%S"):
            try:
                ts = int(datetime.strptime(raw, fmt).timestamp())
                break
            except ValueError:
                pass
        if ts is None:
            continue
        out.append({"id": extract_video_id(m.group("url")), "title": html.unescape(m.group("title")),
                    "channel": html.unescape(m.group("channel") or ""), "ts": ts})
    return out


def import_takeout(path, include_all=False):
    """Import a Google Takeout 'watch-history' (.json or .html) as listening history."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {p}"
    text = p.read_text(encoding="utf-8", errors="replace")
    try:
        items = _parse_takeout_json(text, include_all) if text.lstrip().startswith("[") \
            else _parse_takeout_html(text, include_all)
    except Exception as e:
        return f"Couldn't parse {p.name}: {e}"
    if not items:
        hint = "" if include_all else " (only 'YouTube Music' entries are imported by default; use --all to include regular YouTube)"
        return f"No watch entries found in {p.name}{hint}."
    existing = {(r.get("id"), r.get("ts")) for r in read_jsonl(PLAYS_LOG) if r.get("reason") == "import"}
    added = 0
    for it in sorted(items, key=lambda x: x["ts"]):
        if (it["id"], it["ts"]) in existing:
            continue
        append_jsonl(PLAYS_LOG, {"ts": it["ts"], "id": it["id"],
                                 "url": f"https://www.youtube.com/watch?v={it['id']}",
                                 "title": it["title"], "channel": it["channel"], "reason": "import"})
        added += 1
    remember_tracks([{"id": i["id"], "title": i["title"], "channel": i["channel"]} for i in items])
    return f"Imported {added} plays ({len(items) - added} already present) from {p.name}."
