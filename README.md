# Agent Terminal Pro

Multi-agent ChatOps collaboration platform with PTY terminal support.

## Features

- **Multi-Agent Support**: Run multiple AI agents (Claude, Gemini, Codex, OpenCode, Shell) simultaneously
- **Multi-Project Workspace**: Work on up to 5 projects in parallel with independent terminals
- **Inter-Agent Routing**: Route output between agents for collaborative workflows
- **Persona Injection**: Assign roles (PM, Dev, QA) for specialized behavior
- **Session Persistence**: Terminals and layouts restore on page reload
- **Image Paste Support**: Paste images directly from clipboard (Ctrl+V)
- **Real-time WebSocket**: Low-latency terminal communication

## Requirements

- Python 3.8+
- Windows OS (pywinpty required)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd agent-terminal

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pywinpty` - Windows PTY support (required for terminal functionality)
- `websockets` - WebSocket support

## Quick Start

```bash
# Start the server
python server.py

# Open in browser
# http://localhost:8090
```

## Usage

### Terminal Controls

| Button | Description |
|--------|-------------|
| + Terminal | Add new terminal (max 4 per project) |
| Layout buttons | Switch between 1/2/4 column layouts |
| Server Restart | Restart server with state preservation |
| Reset | Clear all sessions and start fresh |

### Agent Types

| Agent | Icon | Multi-Instance | Description |
|-------|------|----------------|-------------|
| Claude | Blue | Yes | Anthropic Claude CLI |
| Gemini | Green | No | Google Gemini |
| Codex | Orange | No | OpenAI Codex |
| OpenCode | Purple | Yes | Custom agent |
| Shell | White | Yes | Standard shell |

### Roles (Persona)

- **General**: Default mode
- **PM**: Project Manager - task breakdown and planning
- **Dev**: Developer - code implementation focus
- **QA**: Quality Assurance - testing and review

### Keyboard Shortcuts

- `Ctrl+V` - Paste text or image from clipboard
- Terminal supports standard xterm keybindings

## Project Structure

```
agent-terminal/
├── server.py           # FastAPI server with static file serving
├── templates/
│   └── index.html      # HTML structure only (201 lines)
├── static/
│   ├── css/
│   │   └── style.css   # All CSS styles (722 lines)
│   └── js/
│       ├── state.js    # Configuration & state management
│       ├── terminal.js # Terminal creation & WebSocket
│       ├── ui.js       # UI rendering & modals
│       ├── websocket.js# Health check & server communication
│       └── main.js     # Application entry point
├── src/
│   └── terminal.py     # PTY terminal handler
├── requirements.txt    # Python dependencies
└── CHANGELOG.md        # Version history
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main UI |
| `/api/version` | GET | Server version |
| `/api/agents` | GET | Available agents |
| `/api/folders` | GET | Folder browser |
| `/api/files` | GET | File listing |
| `/api/restart` | POST | Restart server |
| `/ws/terminal/{session_id}` | WS | Terminal WebSocket |

## Troubleshooting

### "Terminal module not available" error

This means `pywinpty` is not installed:

```bash
pip install pywinpty
```

### Session conflict issues

If you see "세션 충돌 감지" repeatedly:
1. Click "Reset" to clear all sessions
2. Refresh the browser

### Server restart opens new window

Fixed in v1.3.0 - server now restarts silently in background.

## Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

Current version: **1.5.0**

## License

MIT License
