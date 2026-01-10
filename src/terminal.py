"""
xterm.js Web Terminal for AI CLI Agents
Windows PTY support using pywinpty

Supported agents: Claude, Gemini, Codex, OpenCode, Shell
"""

import asyncio
import json
import base64
import os
import tempfile
from pathlib import Path
from typing import Optional, Literal
from fastapi import WebSocket, WebSocketDisconnect

# Windows PTY
try:
    from winpty import PtyProcess
    WINPTY_AVAILABLE = True
except ImportError:
    WINPTY_AVAILABLE = False
    print("[WARN] pywinpty not available - terminal disabled")


# Agent configurations - easily extensible
# session_cmd: template for session resume (use {session_id} placeholder)
AGENT_CONFIGS = {
    "claude": {
        "name": "Claude",
        "icon": "🔵",
        "command": "claude --dangerously-skip-permissions",
        "session_cmd": "--resume {session_id}",
        "add_image_cmd": "add {path}",
        "prompt_char": ">",
        "color": "#7aa2f7",
        "supports_image": True,
        "description": "Anthropic Claude Code CLI"
    },
    "gemini": {
        "name": "Gemini",
        "icon": "🟢",
        "command": "gemini",
        "session_cmd": None,  # Gemini doesn't support session resume
        "add_image_cmd": "add {path}",
        "prompt_char": ">",
        "color": "#9ece6a",
        "supports_image": True,
        "description": "Google Gemini CLI"
    },
    "codex": {
        "name": "Codex",
        "icon": "🟠",
        "command": "codex",
        "session_cmd": None,
        "add_image_cmd": None,
        "prompt_char": ">",
        "color": "#ff9e64",
        "supports_image": False,
        "description": "OpenAI Codex CLI"
    },
    "opencode": {
        "name": "OpenCode",
        "icon": "🟣",
        "command": "opencode",
        "session_cmd": "--session {session_id}",
        "add_image_cmd": None,  # Image support unclear
        "prompt_char": ">",
        "color": "#bb9af7",
        "supports_image": False,
        "description": "OpenCode CLI with oh-my-opencode"
    },
    "shell": {
        "name": "Shell",
        "icon": "⚪",
        "command": "cmd.exe" if os.name == 'nt' else "/bin/bash",
        "session_cmd": None,
        "add_image_cmd": None,
        "prompt_char": ">",
        "color": "#a9b1d6",
        "supports_image": False,
        "description": "System Shell"
    }
}

# Maximum number of concurrent terminals
MAX_TERMINALS = 6

AgentType = Literal["claude", "gemini", "codex", "opencode", "shell"]


class TerminalSession:
    """Single terminal session with PTY"""

    def __init__(self, session_id: str, working_dir: str = None,
                 agent_type: AgentType = "claude", resume: bool = True):
        self.session_id = session_id
        self.working_dir = working_dir or os.getcwd()
        self.agent_type = agent_type
        self.resume = resume
        self.pty: Optional[PtyProcess] = None
        self.websocket: Optional[WebSocket] = None
        self._read_task: Optional[asyncio.Task] = None
        self._running = False

        # Get agent config
        self.config = AGENT_CONFIGS.get(agent_type, AGENT_CONFIGS["claude"])

    async def start(self, websocket: WebSocket):
        """Start terminal with AI CLI"""
        if not WINPTY_AVAILABLE:
            await websocket.send_json({
                "type": "error",
                "message": "Terminal not available (pywinpty not installed)"
            })
            return False

        self.websocket = websocket

        try:
            # Build command with session support
            cmd = self.config["command"]
            session_cmd = self.config.get("session_cmd")
            if session_cmd and self.session_id:
                cmd = f'{cmd} {session_cmd.format(session_id=self.session_id)}'

            self.pty = PtyProcess.spawn(
                cmd,
                cwd=self.working_dir,
                dimensions=(24, 80)
            )
            self._running = True

            # Start reading PTY output
            self._read_task = asyncio.create_task(self._read_pty_output())

            await websocket.send_json({
                "type": "terminal_started",
                "session_id": self.session_id,
                "agent_type": self.agent_type,
                "agent_name": self.config["name"],
                "cwd": self.working_dir
            })
            return True

        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to start {self.config['name']}: {e}"
            })
            return False

    async def _read_pty_output(self):
        """Read PTY output and send to WebSocket"""
        loop = asyncio.get_event_loop()

        while self._running and self.pty and self.pty.isalive():
            try:
                data = await loop.run_in_executor(
                    None,
                    lambda: self.pty.read(4096) if self.pty.isalive() else ""
                )

                if data and self.websocket:
                    await self.websocket.send_json({
                        "type": "terminal_output",
                        "data": data
                    })

                await asyncio.sleep(0.01)

            except Exception as e:
                if self._running:
                    print(f"[Terminal] Read error: {e}")
                break

        # Terminal closed
        if self._running and self.websocket:
            try:
                await self.websocket.send_json({
                    "type": "terminal_closed"
                })
            except:
                pass

    async def write(self, data: str):
        """Write input to PTY"""
        if self.pty and self.pty.isalive():
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.pty.write(data))

    async def resize(self, rows: int, cols: int):
        """Resize PTY"""
        if self.pty and self.pty.isalive():
            try:
                self.pty.setwinsize(rows, cols)
            except Exception as e:
                print(f"[Terminal] Resize error: {e}")

    async def send_image(self, image_data: str, filename: str):
        """Save image and send path to AI CLI"""
        add_cmd = self.config.get("add_image_cmd")
        if not add_cmd:
            if self.websocket:
                await self.websocket.send_json({
                    "type": "error",
                    "message": f"{self.config['name']} does not support images"
                })
            return None

        try:
            # Decode base64 image
            if "," in image_data:
                image_data = image_data.split(",")[1]

            image_bytes = base64.b64decode(image_data)

            # Save to temp file
            ext = Path(filename).suffix or ".png"
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"ai_image_{self.session_id[:8]}{ext}")

            with open(temp_path, "wb") as f:
                f.write(image_bytes)

            # Send file path using agent's add command
            cmd = add_cmd.format(path=temp_path) + "\n"
            await self.write(cmd)

            if self.websocket:
                await self.websocket.send_json({
                    "type": "image_added",
                    "path": temp_path,
                    "filename": filename,
                    "agent_type": self.agent_type
                })

            return temp_path

        except Exception as e:
            if self.websocket:
                await self.websocket.send_json({
                    "type": "error",
                    "message": f"Failed to add image: {e}"
                })
            return None

    async def stop(self):
        """Stop terminal session"""
        self._running = False

        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self.pty:
            try:
                self.pty.terminate()
            except:
                pass
            self.pty = None


# Active terminal sessions
terminal_sessions: dict[str, TerminalSession] = {}


async def handle_terminal_websocket(
    websocket: WebSocket,
    session_id: str,
    working_dir: str = None,
    agent_type: str = "claude",
    resume: bool = True,
    already_accepted: bool = False
):
    """Handle WebSocket connection for terminal"""
    if not already_accepted:
        await websocket.accept()

    # Validate agent type
    if agent_type not in AGENT_CONFIGS:
        agent_type = "claude"

    # Create or get session
    if session_id in terminal_sessions:
        session = terminal_sessions[session_id]
        await session.stop()

    session = TerminalSession(session_id, working_dir, agent_type=agent_type, resume=resume)
    terminal_sessions[session_id] = session

    # Start terminal
    if not await session.start(websocket):
        return

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "input":
                await session.write(msg.get("data", ""))

            elif msg_type == "resize":
                await session.resize(
                    msg.get("rows", 24),
                    msg.get("cols", 80)
                )

            elif msg_type == "image":
                await session.send_image(
                    msg.get("data", ""),
                    msg.get("filename", "image.png")
                )

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[Terminal] WebSocket error: {e}")
    finally:
        await session.stop()
        if session_id in terminal_sessions:
            del terminal_sessions[session_id]


def get_available_agents():
    """Return list of available agent types with full config"""
    return [
        {
            "id": k,
            "name": v["name"],
            "icon": v.get("icon", "⚪"),
            "color": v["color"],
            "supports_image": v.get("supports_image", False),
            "description": v.get("description", "")
        }
        for k, v in AGENT_CONFIGS.items()
    ]


def get_max_terminals():
    """Return maximum number of terminals allowed"""
    return MAX_TERMINALS
