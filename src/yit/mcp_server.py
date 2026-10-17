import json
from types import SimpleNamespace

try:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
except ImportError:  # mcp 2.x renamed FastMCP -> MCPServer
    from mcp.server.mcpserver import MCPServer as _Server

# Import functions from Yit's internal modules
from .commands import (
    cmd_search, cmd_play, cmd_pause, cmd_resume, 
    cmd_stop, cmd_next, cmd_prev, cmd_add, 
    cmd_queue, cmd_clear, cmd_loop, cmd_unloop,
    cmd_status
)
from .storage import load_favorites, save_favorites
from .config import RESULTS_FILE, HISTORY_FILE, FAV_FILE
from .ipc import get_ipc_property
from .utils import extract_video_id

INSTRUCTIONS = """\
You are the user's personal music DJ ("Jarvis" mode) controlling Yit, a background YouTube music player.
Yit learns from real listening: what they finish, what they skip, favorites, dislikes, searches, time of day.

How to behave:
- Vague requests ("play something", "music", "I'm bored", "vibe check"): call get_listening_profile first,
  then either dj_play_for_me (taste-based queue, fastest) or hand-pick songs with play_songs.
- Mood/activity requests ("focus music", "gym", "rainy night", "something like X but sadder"): call
  get_listening_profile, then pick 10-15 specific "Artist - Song" titles that fit the mood, blending artists
  they already love (top_artists, this_time_of_day) with similar artists they likely haven't heard, and call
  play_songs. Respect language/region preferences visible in their history. Avoid anything in disliked.
- "More like this" / "keep this vibe going": start_radio with no seed (uses the current song).
- Specific song or artist: search_music_on_youtube.
- When they react ("love this", "this is trash", "never play this again", "not this artist"), call
  like_current_song / dislike_current_song so Yit learns.
- Keep replies short: what's playing and why it fits them, in one or two lines. No track-by-track essays.
"""

mcp = _Server("yit-player", instructions=INSTRUCTIONS)

# Helper to capture printed output from commands (since Yit mostly prints its output)
import io
import sys
from contextlib import contextmanager

@contextmanager
def capture_output():
    new_out, new_err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err

# --- PLAYBACK CONTROLS ---

@mcp.tool()
def search_music_on_youtube(query: str, play_first_result: bool = True) -> str:
    """Searches YouTube for music or songs based on a natural language query. 
    If play_first_result is true, it immediately starts playing the best match."""
    args = SimpleNamespace(query=query.split(), play=play_first_result)
    with capture_output() as (out, _):
        cmd_search(args)
    return out.getvalue()

@mcp.tool()
def play_search_result(number: int) -> str:
    """Plays a specific track number from the most recent search results. Only call this AFTER a successful search."""
    args = SimpleNamespace(number=number)
    with capture_output() as (out, _):
        cmd_play(args)
    return out.getvalue()

@mcp.tool()
def pause_music() -> str:
    """Pauses the currently playing track."""
    args = SimpleNamespace()
    with capture_output() as (out, _):
        cmd_pause(args)
    return out.getvalue()

@mcp.tool()
def resume_music() -> str:
    """Resumes playing the currently paused track."""
    args = SimpleNamespace()
    with capture_output() as (out, _):
        cmd_resume(args)
    return out.getvalue()

@mcp.tool()
def stop_music() -> str:
    """Stops music playback entirely and closes the player."""
    args = SimpleNamespace()
    with capture_output() as (out, _):
        cmd_stop(args)
    return out.getvalue()

@mcp.tool()
def skip_to_next_track() -> str:
    """Skips to the next track in the queue."""
    args = SimpleNamespace()
    with capture_output() as (out, _):
        cmd_next(args)
    return out.getvalue()

@mcp.tool()
def play_previous_track() -> str:
    """Goes back to the previously played track."""
    args = SimpleNamespace()
    with capture_output() as (out, _):
        cmd_prev(args)
    return out.getvalue()

@mcp.tool()
def loop_current_track() -> str:
    """Locks the player to loop the current track indefinitely."""
    args = SimpleNamespace()
    with capture_output() as (out, _):
        cmd_loop(args)
    return out.getvalue()

@mcp.tool()
def stop_looping() -> str:
    """Stops looping the current track so playback proceeds normally."""
    args = SimpleNamespace()
    with capture_output() as (out, _):
        cmd_unloop(args)
    return out.getvalue()

@mcp.tool()
def get_player_status() -> str:
    """Gets the current playback status (Playing/Paused/Stopped) and the name of the current track."""
    args = SimpleNamespace()
    with capture_output() as (out, _):
        cmd_status(args)
    return out.getvalue()


# --- QUEUE MANAGEMENT ---

@mcp.tool()
def get_current_queue() -> str:
    """Returns the list of tracks currently in the playback queue."""
    args = SimpleNamespace()
    with capture_output() as (out, _):
        cmd_queue(args)
    return out.getvalue()

@mcp.tool()
def add_to_queue(number: int) -> str:
    """Appends a track number from the latest search results directly to the end of the queue."""
    args = SimpleNamespace(number=number)
    with capture_output() as (out, _):
        cmd_add(args)
    return out.getvalue()

@mcp.tool()
def clear_queue() -> str:
    """Clears all upcoming tracks from the queue except the one currently playing."""
    args = SimpleNamespace()
    with capture_output() as (out, _):
        cmd_clear(args)
    return out.getvalue()


# --- FAVORITES MANAGEMENT ---

@mcp.tool()
def list_favorites() -> str:
    """Lists all the user's saved favorite tracks."""
    args = SimpleNamespace(action="list", target=None)
    with capture_output() as (out, _):
        from .commands import cmd_fav
        cmd_fav(args)
    return out.getvalue()

@mcp.tool()
def play_favorites(index_to_play: int = None) -> str:
    """Plays the user's favorite tracks. If index_to_play is not provided, plays all favorites. If an index is provided, plays only that specific favorite."""
    args = SimpleNamespace(
        action="play", 
        target=str(index_to_play) if index_to_play else None
    )
    with capture_output() as (out, _):
        from .commands import cmd_fav
        cmd_fav(args)
    return out.getvalue()

@mcp.tool()
def add_currently_playing_to_favorites() -> str:
    """Adds the currently playing music track to the user's favorites list."""
    args = SimpleNamespace(action="add", target=None)
    with capture_output() as (out, _):
        from .commands import cmd_fav
        cmd_fav(args)
    return out.getvalue()

@mcp.tool()
def add_search_result_to_favorites(number: int) -> str:
    """Adds a specific track number from the recent search results to favorites."""
    args = SimpleNamespace(action="add", target=str(number))
    with capture_output() as (out, _):
        from .commands import cmd_fav
        cmd_fav(args)
    return out.getvalue()

@mcp.tool()
def remove_favorite(index: int) -> str:
    """Removes a track from favorites using its index number from the favorites list."""
    args = SimpleNamespace(action="remove", target=str(index))
    with capture_output() as (out, _):
        from .commands import cmd_fav
        cmd_fav(args)
    return out.getvalue()

# --- JARVIS: TASTE-AWARE TOOLS ---

@mcp.tool()
def get_listening_profile() -> str:
    """Returns what Yit has learned about the user's music taste as JSON: top artists and tracks (recency-weighted,
    from songs they actually finished), what they play at this time of day, recently played, often skipped,
    recent searches, favorites and dislikes. Call this before choosing music for vague or mood-based requests."""
    from .taste import build_profile
    return json.dumps(build_profile(), indent=1, ensure_ascii=False)

@mcp.tool()
def dj_play_for_me(size: int = 20, discovery: float = 0.4) -> str:
    """Builds and plays a personal queue from the user's taste: favourites they haven't heard recently, mixed with
    new songs similar to what they love (via YouTube Mix). discovery = share of new-to-them songs (0 to 1)."""
    from .dj import dj
    with capture_output() as (out, _):
        msg = dj(size=size, discovery=discovery)
    return msg

@mcp.tool()
def play_songs(songs: list[str], replace_queue: bool = True) -> str:
    """Plays a hand-picked list of specific songs in order. Each item should be a precise search like
    "Artist - Song Title". Set replace_queue=false to append after the current queue instead."""
    from .dj import play_mix
    with capture_output() as (out, _):
        msg = play_mix(songs, replace=replace_queue)
    return msg

@mcp.tool()
def start_radio(seed: str = "") -> str:
    """Plays an endless-style radio of songs similar to a seed (song name or YouTube URL). With no seed it continues
    from the currently playing song, or from the user's top track if nothing is playing."""
    from .dj import radio
    with capture_output() as (out, _):
        msg = radio(seed or None)
    return msg

@mcp.tool()
def like_current_song() -> str:
    """Marks the currently playing song as liked (adds to favorites and boosts it in future recommendations)."""
    from .dj import like_current
    return like_current()

@mcp.tool()
def dislike_current_song(block_artist: bool = False, skip: bool = True) -> str:
    """Marks the current song as disliked so it's never recommended again, and skips it. block_artist=true also
    excludes that artist from all future recommendations."""
    from .dj import dislike_current
    with capture_output() as (out, _):
        msg = dislike_current(block_artist=block_artist, skip=skip)
    return msg

@mcp.tool()
def import_youtube_music_history(file_path: str, include_regular_youtube: bool = False) -> str:
    """Imports the user's Google Takeout YouTube watch history (watch-history.json or .html) so Yit knows their taste
    from day one. By default only YouTube Music entries are imported."""
    from .dj import import_takeout
    return import_takeout(file_path, include_all=include_regular_youtube)


def main():
    mcp.run()

if __name__ == "__main__":
    main()
