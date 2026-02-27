import argparse
import sys
from .utils import check_for_updates, show_update_notice, __version__
from .installer import get_mpv_path
from .commands import (
    cmd_search, cmd_play, cmd_pause, cmd_resume, cmd_toggle,
    cmd_stop, cmd_loop, cmd_unloop, cmd_add, cmd_next, cmd_prev,
    cmd_restart, cmd_clear, cmd_queue, cmd_status, cmd_agent,
    cmd_commands, cmd_fav
)

def main():
    show_update_notice()
    check_for_updates()

    try:
        if len(sys.argv) > 1 and sys.argv[1] in ("-v", "--version"):
            # Don't block version check on mpv install
            pass
        else:
            get_mpv_path()
    except SystemExit:
        return # already printed error

    parser = argparse.ArgumentParser(prog="yit", description="Yit (YouTube in Terminal) - Fire-and-Forget Music Player")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search
    parser_search = subparsers.add_parser("search", help="Search YouTube")
    parser_search.add_argument("query", nargs="+", help="Search query")
    parser_search.add_argument("-p", "--play", action="store_true", help="Auto-play the first result")
    parser_search.set_defaults(func=cmd_search)

    # Play
    parser_play = subparsers.add_parser("play", help="Play a song by number")
    parser_play.add_argument("number", type=int, help="Track number from search results")
    parser_play.set_defaults(func=cmd_play)

    # Controls
    parser_pause = subparsers.add_parser("pause", aliases=["p"], help="Pause playback")
    parser_pause.set_defaults(func=cmd_pause)

    parser_resume = subparsers.add_parser("resume", aliases=["r"], help="Resume playback")
    parser_resume.set_defaults(func=cmd_resume)
    
    parser_toggle = subparsers.add_parser("toggle", help="Toggle pause/resume")
    parser_toggle.set_defaults(func=cmd_toggle)

    parser_stop = subparsers.add_parser("stop", help="Stop playback")
    parser_stop.set_defaults(func=cmd_stop)

    # Add to queue
    parser_add = subparsers.add_parser("add", help="Add song to queue")
    parser_add.add_argument("number", type=int, help="Track number")
    parser_add.set_defaults(func=cmd_add)

    # Queue management
    parser_queue = subparsers.add_parser("queue", help="Show queue")
    parser_queue.set_defaults(func=cmd_queue)

    parser_clear = subparsers.add_parser("clear", help="Clear queue")
    parser_clear.set_defaults(func=cmd_clear)

    # Fast Navigation (Safe Aliases)
    # Next
    parser_next = subparsers.add_parser("next", aliases=["n"], help="Next track")
    parser_next.set_defaults(func=cmd_next)

    # Previous (Back)
    parser_prev = subparsers.add_parser("back", aliases=["b"], help="Previous track")
    parser_prev.set_defaults(func=cmd_prev)

    # Replay/Restart
    parser_restart = subparsers.add_parser("replay", aliases=["0"], help="Replay current track")
    parser_restart.set_defaults(func=cmd_restart)

    parser_status = subparsers.add_parser("status", help="Show status")
    parser_status.set_defaults(func=cmd_status)
    
    # Agent Interface
    parser_agent = subparsers.add_parser("agent", help="JSON output for AI agents")
    parser_agent.set_defaults(func=cmd_agent)

    parser_cmds = subparsers.add_parser("commands", help="JSON command list for AI agents")
    parser_cmds.set_defaults(func=cmd_commands)

    # Favorites
    parser_fav = subparsers.add_parser("fav", help="Manage favorites")
    # Sub-arguments for fav: action (add, list, play, remove) and target (index)
    parser_fav.add_argument("action", nargs="?", default="list", choices=["add", "list", "play", "remove"], help="Action to perform")
    parser_fav.add_argument("target", nargs="?", help="Index (for add/play/remove)")
    parser_fav.set_defaults(func=cmd_fav)

    # Loop
    subparsers.add_parser("loop", help="Loop current track").set_defaults(func=cmd_loop)
    subparsers.add_parser("unloop", help="Stop looping").set_defaults(func=cmd_unloop)

    args = parser.parse_args()
    args.func(args)
