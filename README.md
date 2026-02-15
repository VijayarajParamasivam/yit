# Yit (No Tabs. Just Tunes.) Player 🎵

[![PyPI version](https://badge.fury.io/py/yit-player.svg)](https://badge.fury.io/py/yit-player)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

**The Fire-and-Forget Music Player for Developers.**

Yit is a lightweight, headless, terminal-based audio player designed for flow states. It allows you to search, queue, and control music directly from your CLI without ever touching a browser or a heavy GUI.

It runs in the background (daemonized), meaning you can close your terminal, switch tabs, or keep coding while the music plays.

---

## 🚀 Features

*   **Daemon Architecture**: The player runs as a detached background process. Your terminal is never blocked.
*   **Instant Search**: Uses `yt-dlp` to fetch metadata in milliseconds.
*   **Smart Queue**: Manage your playlist (`add`, `next`, `back`, `Loop`) with simple commands.
*   **Cross-Platform**: Works natively on **Windows**, **macOS**, and **Linux**.
*   **Agent-Native**: Built from the ground up to be controlled by AI Agents (Vibe Coding).

---

## 📦 Installation

```bash
pip install yit-player
```

### Requirements
*   **None!** Yit automatically manages the `mpv` audio engine internally. 
*   **Windows**: Auto-downloads a portable `mpv.exe` if missing.
*   **Mac/Linux**: Uses system MPV (install via `brew` or `apt` if needed).

### Troubleshooting: "Command/Path not found"
If you run `yit` and get an error, your Python scripts folder is not in your system PATH.
**Solution:** Run it like this instead (works 100% of the time):
```bash
python -m yit search "slava funk" -p
```

---

## ⚡ Quick Start

### 1. Search & Play
```bash
# Search for a song
yit search "funk sigilo"

# Auto-play the first result immediately
yit search "funk infernal" -p
```

### 2. Control Playback
```bash
yit pause    # (or 'p')
yit resume   # (or 'r')
yit toggle   # Toggle play/pause
yit stop     # Kill the player
```

### 3. Queue Management
```bash
yit add 1    # Add result #1 from your last search to the queue (use 1 - 5 to choose from search results)
yit queue    # Show the current queue
yit next     # Skip track (or 'n')
yit back     # Previous track (or 'b')
yit clear    # Wipe the queue
```

### 4. Looping
```bash
yit loop     # Loop the current track indefinitely
yit unloop   # Return to normal playback
```

### 5. Status
```bash
yit status   # Check if currently Playing/Paused and Looped
```
---

## 🤖 For AI Agents & Vibe Coding

Yit is designed to be **self-documenting** for AI context.
If you are building an AI agent or using an LLM in your IDE:

1.  **Read context**: Point your agent to [AI_INSTRUCTIONS.md](AI_INSTRUCTIONS.md) (included in the repo).
2.  **Discovery**: Run `yit commands` to get a JSON list of all capabilities.
3.  **State**: Run `yit agent` to get the full player state (Track, Time, Queue) in pure JSON.

**Example Agent Output (`yit agent`):**
```json
{
  "status": "playing",
  "track": {
    "title": "Never Gonna Give You Up",
    "url": "https://..."
  },
  "position": 45.2,
  "duration": 212.0,
  "queue_length": 5
}
```

---

## 🛠️ Architecture

*   **Client**: Python CLI (`yit`) handles argument parsing and user signals.
*   **Daemon**: A detached `mpv` process handles audio decoding and network streaming.
*   **Communication**: IPC (Inter-Process Communication) via Named Pipes (Windows) or Unix Sockets (Linux/Mac).
*   **Persistence**: `~/.yit/history.json` stores your playback history and queue metadata.

---

## ⚠️ Disclaimer and Legal Notice

**1. Educational Purpose Only**
This software (`Yit`) is a proof-of-concept project designed strictly for **educational and research purposes**. Its primary goal is to demonstrate:
* Advanced Python subprocess management and Daemon architecture.
* Inter-Process Communication (IPC) using sockets and named pipes.
* Memory-efficient resource management in CLI environments.

**2. Third-Party Content**
This tool acts as a command-line interface (CLI) wrapper for open-source media engines (`mpv`) and network libraries (`yt-dlp`).
* **No Content Hosting:** This application does not host, store, distribute, or decrypt any copyrighted media content.
* **Streaming Only:** It is designed for transient streaming of publicly available content. It does not include features to permanently download or "rip" media to the disk.

**3. Terms of Service**
Users are responsible for ensuring their use of this tool complies with the Terms of Service of any third-party platforms they interact with. The developer of this tool assumes no liability for misuse, account suspensions, or legal consequences arising from the use of this software.

**4. No Monetization**
This project is **free and open-source**. It is not monetized in any way, nor does it generate revenue from the content it accesses.

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3). This ensures the software remains free and open-source. Commercial distribution of this software as a closed-source product is strictly prohibited.

## Contact

For any questions, please contact [vijayaraj.devworks@gmail.com](mailto:vijayaraj.devworks@gmail.com).