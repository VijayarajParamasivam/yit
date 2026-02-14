# Yit - Agent Context & Instructions

## Project Overview
**Yit** is a headless, CLI-based music player for Windows. It uses `mpv` as the audio engine and `yt-dlp` for media resolution. The architecture separates the client (CLI) from the daemon (background mpv process).

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

### 3. File Structure
*   `yit.py`: Main entry point. Handles CLI args and IPC communication.
*   `yit.bat`: Windows wrapper. Ensures `venv` usage.
*   `install_yit.ps1`: Self-healing installer. Creates `venv` if missing.
*   `.yit/history.json`: Persistent history of played tracks.
*   `.yit/results.json`: Last search results.

### 4. IPC Mechanism
Yit communicates with `mpv` via a named pipe: `\\.\pipe\yit_socket`.
*   The `send_ipc_command` function in `yit.py` handles raw JSON IPC messages.
*   If extending functionality, use `input-ipc-server` commands from MPV documentation.

## Critical Rules for Agents
1.  **Always use `yit.bat` or `yit`**: Never call `python yit.py` directly; it bypasses the venv check.
2.  **Check `yit agent` first**: Before deciding to play/pause, check the current state.
3.  **Search is blocking**: `yit search` waits for `yt-dlp`. Playback commands are non-blocking.
