# Yit - Agent Context & Instructions

## Project Overview
**Yit** is a headless, CLI-based music player for Windows, macOS and Linux. It uses `mpv` as the audio engine and `yt-dlp` for media resolution. The architecture separates the client (CLI) from the daemon (background mpv process).

## Agent Interaction Protocol

### 1. Self-Discovery
An agent should first discover what Yit can do:
```bash
yit commands
```
**Output (JSON):**
```json
[
  {"cmd": "search", "usage": "yit search <query> [-p]", "desc": "Search YouTube..."},
  {"cmd": "play", "usage": "yit play <index>", "desc": "Play track..."},
  ...
]
```

### 2. State Retrieval
To get the full system state in a machine-readable format, run:
```bash
yit agent
```
**Output Format (JSON):**
```json
{
  "status": "playing", 
  "track": {
    "title": "Song Title",
    "url": "https://youtube.com/..."
  },
  "position": 125.5,
  "duration": 300.0,
  "volume": 100,
  "loop": false,
  "queue_length": 5
}
```

### 2. Control Commands
Use these commands to manipulate playback. They return exit code `0` on success.

| Command | Action | Notes |
| :--- | :--- | :--- |
| `yit search "<query>" -p` | Search & Auto-Play | Best for "Play X" requests. |
| `yit pause` | Pause playback | Idempotent. |
| `yit resume` | Resume playback | Idempotent. |
| `yit toggle` | Toggle play/pause | |
| `yit stop` | Kill player | Hard stop. |
| `yit next` | Skip track | |
| `yit back` | Previous track | |
| `yit loop` | Loop current | Infinite loop. |
| `yit unloop` | Disable loop | |
| `yit volume <0-100>` | Set volume | *Planned Feature* |

### Taste-aware commands ("Jarvis mode")
Yit learns from real listening (finished vs. skipped, favorites, dislikes, searches, time of day).

| Command | Action | Notes |
| :--- | :--- | :--- |
| `yit profile --json` | Taste profile | Top artists/tracks, time-of-day habits, skips, searches. Read this before picking music for vague requests. |
| `yit dj` | Personal queue | Favourites + new similar songs. `--discovery 0-1`, `--size N`. |
| `yit radio [song]` | Similar-songs radio | Defaults to the current track. |
| `yit mix "A - S1" "B - S2"` | Play a hand-picked list | Use for mood requests; `-a` appends. |
| `yit like` / `yit dislike [--artist]` | Feedback | Dislike skips and blocks future recommendations. |
| `yit import <watch-history.json>` | Import Google Takeout history | Bootstraps taste. |

### 3. File Structure
*   `src/yit/cli.py` / `commands.py`: CLI and playback commands (IPC to mpv).
*   `src/yit/mcp_server.py`: MCP server (`yit-mcp`).
*   `src/yit/tracker.lua`: mpv script that logs each finished track (listen time + end reason).
*   `src/yit/taste.py` / `dj.py`: taste profile, DJ queue, radio, likes/dislikes, Takeout import.
*   `~/.yit/plays.jsonl`: listening log. `~/.yit/tracks.json`: track metadata catalog.
*   `~/.yit/history.json`, `results.json`, `favorites.json`, `dislikes.json`, `searches.jsonl`.

### 4. IPC Mechanism
Yit communicates with `mpv` via a named pipe: `\\.\pipe\yit_socket`.
*   The `send_ipc_command` function in `ipc.py` handles raw JSON IPC messages.
*   If extending functionality, use `input-ipc-server` commands from MPV documentation.

## Critical Rules for Agents
1.  **Use `yit` (or `python -m yit`)** to run commands.
2.  **Check `yit agent` first**: Before deciding to play/pause, check the current state.
3.  **Search is blocking**: `yit search` waits for `yt-dlp`. Playback commands are non-blocking.
