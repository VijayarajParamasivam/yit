"""Taste model: turns raw listening logs into a profile of what the user likes.

Signals (all local, in ~/.yit):
  plays.jsonl    finished tracks with real listen time + end reason (mpv tracker),
                 plus anything imported from a Google Takeout watch history
  history.json   legacy "played once" list (backfilled at low weight)
  favorites.json explicit likes
  dislikes.json  explicit dislikes (tracks / artists)
  searches.jsonl what the user asked for
"""
import math
import re
import time
from collections import defaultdict
from datetime import datetime

from .config import HISTORY_FILE, PLAYS_LOG, SEARCH_LOG
from .storage import (load_catalog, load_dislikes, load_favorites, read_jsonl,
                      _read_json)
from .utils import extract_video_id

HALF_LIFE_DAYS = 45
SKIP_SECONDS = 30

_BUCKETS = [(5, "morning"), (12, "afternoon"), (17, "evening"), (22, "night")]


def time_bucket(ts=None):
    h = datetime.fromtimestamp(ts or time.time()).hour
    name = "night"
    for start, label in _BUCKETS:
        if h >= start:
            name = label
    return name


_NOISE = re.compile(r"\s*[\(\[][^\)\]]*(official|lyric|video|audio|visualizer|hd|4k|remaster)[^\)\]]*[\)\]]", re.I)


def clean_title(title):
    return _NOISE.sub("", title or "").strip()


def guess_artist(title, channel):
    channel = (channel or "").strip()
    if channel.endswith(" - Topic"):
        return channel[:-8].strip()
    t = clean_title(title)
    if " - " in t:
        left = t.split(" - ", 1)[0].strip()
        if 0 < len(left) <= 60:
            return re.split(r"\s*(?:,|&| x | ft\.?| feat\.?)\s*", left, maxsplit=1, flags=re.I)[0]
    channel = re.sub(r"(VEVO|Official|\s+Music)$", "", channel, flags=re.I).strip()
    return channel or "Unknown"


def classify(rec):
    """Returns (kind, weight): kind in play/complete/partial/skip/neutral."""
    reason = rec.get("reason")
    if reason == "import":
        return "play", 0.7
    if reason == "history":
        return "play", 0.5
    listened = rec.get("listened") or 0
    dur = rec.get("duration") or 0
    ratio = listened / dur if dur else None
    if reason == "eof" and (ratio is None or ratio > 0.6):
        return "complete", 1.0
    if listened < SKIP_SECONDS and (ratio is None or ratio < 0.4):
        if reason in ("stop", "replaced"):
            return "skip", -1.0
        return "neutral", 0.0
    if (ratio is not None and ratio >= 0.5) or listened >= 120:
        return "play", 0.8
    return "partial", 0.3


def _decay(ts, now):
    age_days = max(0.0, (now - ts) / 86400.0)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def load_events():
    """All listening events, enriched with id/title/artist, oldest first."""
    cat = load_catalog()
    events = []
    for rec in read_jsonl(PLAYS_LOG):
        vid = rec.get("id") or extract_video_id(rec.get("url", ""))
        if not vid:
            continue
        meta = cat.get(vid, {})
        title = meta.get("title") or rec.get("title") or vid
        channel = meta.get("channel") or rec.get("channel") or ""
        if not rec.get("duration") and meta.get("duration"):
            rec["duration"] = meta["duration"]
        kind, w = classify(rec)
        events.append({
            "id": vid, "title": title, "artist": guess_artist(title, channel),
            "ts": rec.get("ts") or 0, "kind": kind, "weight": w,
            "listened": rec.get("listened") or 0, "source": meta.get("source"),
        })
    # Backfill legacy history (pre-tracker plays) so existing users aren't cold-started.
    logged = {e["id"] for e in events}
    hist = _read_json(HISTORY_FILE, [])
    try:
        mtime = HISTORY_FILE.stat().st_mtime
    except Exception:
        mtime = time.time()
    for h in hist if isinstance(hist, list) else []:
        vid = extract_video_id(h.get("url", ""))
        if vid and vid not in logged:
            meta = cat.get(vid, {})
            title = meta.get("title") or h.get("title") or vid
            events.append({"id": vid, "title": title,
                           "artist": guess_artist(title, meta.get("channel")),
                           "ts": mtime - 30 * 86400, "kind": "play", "weight": 0.5,
                           "listened": 0, "source": "history"})
    events.sort(key=lambda e: e["ts"])
    return events


def track_stats(events=None, now=None):
    """Per-track aggregate: score, plays, skips, last played, buckets."""
    now = now or time.time()
    events = load_events() if events is None else events
    favs = load_favorites()
    dis = load_dislikes()
    stats = {}
    for e in events:
        s = stats.setdefault(e["id"], {"id": e["id"], "title": e["title"], "artist": e["artist"],
                                       "score": 0.0, "plays": 0, "skips": 0, "last": 0,
                                       "seconds": 0, "buckets": defaultdict(float)})
        d = _decay(e["ts"], now)
        s["score"] += e["weight"] * d
        if e["kind"] in ("play", "complete", "partial"):
            s["plays"] += 1
            s["buckets"][time_bucket(e["ts"])] += d
        elif e["kind"] == "skip":
            s["skips"] += 1
        s["seconds"] += e["listened"]
        s["last"] = max(s["last"], e["ts"])
    for f in favs:
        vid = extract_video_id(f.get("url", ""))
        if not vid:
            continue
        s = stats.setdefault(vid, {"id": vid, "title": f.get("title", vid),
                                   "artist": guess_artist(f.get("title"), None), "score": 0.0,
                                   "plays": 0, "skips": 0, "last": 0, "seconds": 0,
                                   "buckets": defaultdict(float)})
        s["score"] += 3.0
        s["favorite"] = True
    for vid in dis["tracks"]:
        if vid in stats:
            stats[vid]["disliked"] = True
    blocked = {a.lower() for a in dis["artists"]}
    for s in stats.values():
        if s["artist"].lower() in blocked:
            s["disliked"] = True
    return stats


def _fmt_track(s):
    return {"title": clean_title(s["title"]), "artist": s["artist"],
            "url": f"https://www.youtube.com/watch?v={s['id']}",
            "plays": s["plays"], "skips": s["skips"], "score": round(s["score"], 2),
            **({"favorite": True} if s.get("favorite") else {})}


def _ago(ts, now):
    m = int((now - ts) / 60)
    if m < 60:
        return f"{m}m ago"
    if m < 1440:
        return f"{m // 60}h ago"
    return f"{m // 1440}d ago"


def build_profile(limit=10):
    now = time.time()
    events = load_events()
    stats = track_stats(events, now)
    liked = [s for s in stats.values() if not s.get("disliked") and s["score"] > 0]
    bucket = time_bucket(now)

    artists = defaultdict(lambda: {"score": 0.0, "plays": 0, "bucket": 0.0})
    for s in liked:
        a = artists[s["artist"]]
        a["score"] += s["score"]
        a["plays"] += s["plays"]
        a["bucket"] += s["buckets"].get(bucket, 0.0)
    top_artists = sorted(artists.items(), key=lambda kv: kv[1]["score"], reverse=True)
    now_artists = sorted([kv for kv in artists.items() if kv[1]["bucket"] > 0],
                         key=lambda kv: kv[1]["bucket"], reverse=True)

    played = [e for e in events if e["kind"] in ("play", "complete", "partial")]
    seconds = sum(e["listened"] for e in events)
    searches, seen = [], set()
    for r in reversed(read_jsonl(SEARCH_LOG)):
        q = (r.get("query") or "").strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            searches.append(q)
        if len(searches) >= 15:
            break

    dis = load_dislikes()
    profile = {
        "now": {"local_time": datetime.now().strftime("%a %H:%M"), "time_of_day": bucket},
        "summary": {
            "tracked_plays": len(played),
            "unique_tracks": len(stats),
            "hours_listened": round(seconds / 3600, 1),
            "skips": sum(1 for e in events if e["kind"] == "skip"),
            "favorites": sum(1 for s in stats.values() if s.get("favorite")),
            "since": datetime.fromtimestamp(events[0]["ts"]).strftime("%Y-%m-%d") if events else None,
        },
        "top_artists": [{"artist": a, "plays": v["plays"], "score": round(v["score"], 2)}
                        for a, v in top_artists[:limit]],
        "top_tracks": [_fmt_track(s) for s in sorted(liked, key=lambda s: s["score"], reverse=True)[:limit]],
        "this_time_of_day": {
            "bucket": bucket,
            "top_artists": [a for a, _ in now_artists[:6]],
            "top_tracks": [clean_title(s["title"]) for s in
                           sorted(liked, key=lambda s: s["buckets"].get(bucket, 0), reverse=True)[:6]
                           if s["buckets"].get(bucket, 0) > 0],
        },
        "recently_played": [{"title": clean_title(e["title"]), "artist": e["artist"],
                             "when": _ago(e["ts"], now), "how": e["kind"]}
                            for e in reversed(events[-15:])],
        "often_skipped": [_fmt_track(s) for s in sorted(stats.values(), key=lambda s: s["skips"], reverse=True)
                          if s["skips"] >= 2][:8],
        "recent_searches": searches,
        "disliked": {"tracks": list(dis["tracks"].values())[:20], "artists": dis["artists"]},
    }
    if len(played) < 10:
        profile["note"] = ("Not much listening history yet. Lean on recent searches/favorites, ask the user "
                           "about their taste, or suggest `yit import <watch-history.json>` from Google Takeout.")
    return profile
