import json
from mcp.server.fastmcp import FastMCP
from types import SimpleNamespace

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

# Create the FastMCP Server
mcp = FastMCP("yit-player")

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

def main():
    mcp.run()

if __name__ == "__main__":
    main()
