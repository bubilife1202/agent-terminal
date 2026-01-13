"""
xterm.js Web Terminal for AI CLI Agents
Windows PTY support using pywinpty

Supported agents: Claude, Gemini, Codex, OpenCode, Shell
"""

import asyncio
import json
import base64
import os
import re
import subprocess
import tempfile
import traceback
import uuid
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


# Role-based system prompts (Persona Injection)
ROLE_PROMPTS = {
    "PM": """You are an expert Technical Project Manager.
Your Goal: Break down vague requirements into clear, actionable technical tasks.
Rules:
1. Do NOT write code implementation details.
2. Focus on architecture, file structure, and step-by-step planning.
3. Delegate implementation tasks to Developers.""",

    "Dev": """You are a Senior Full-Stack Developer.
Your Goal: Write clean, production-ready code based on instructions.
Rules:
1. Focus on implementation. Write filenames and code blocks clearly.
2. If specifications are missing, ask the PM.
3. Keep explanations concise. Code is your language.""",

    "QA": """You are a QA Lead and Security Specialist.
Your Goal: Find bugs, security flaws, and logic errors.
Rules:
1. Review code critically.
2. Suggest test cases.
3. Verify if the code meets requirements.""",

    "General": None  # No special prompt
}

# Agent configurations - easily extensible
# session_cmd: template for session resume (use {session_id} placeholder)
# Each terminal gets a unique UUID for independent sessions
AGENT_CONFIGS = {
    "claude": {
        "name": "Claude",
        "icon": "🔵",
        "command": "claude --dangerously-skip-permissions",
        "session_cmd": "--session-id {session_id}",  # UUID-based session (auto-create/resume)
        "system_prompt_cmd": "--append-system-prompt",  # Inject role-based prompt
        "add_image_cmd": "add {path}",
        "prompt_char": ">",
        "color": "#7aa2f7",
        "supports_image": True,
        "description": "Anthropic Claude Code CLI"
    },
    "gemini": {
        "name": "Gemini",
        "icon": "🟢",
        "command": "gemini --yolo",
        "session_cmd": None,  # No UUID-based session support (only index/latest)
        "add_image_cmd": "add {path}",
        "prompt_char": ">",
        "color": "#9ece6a",
        "supports_image": True,
        "description": "Google Gemini CLI"
    },
    "gemini-thinking": {
        "name": "Gemini (Thinking)",
        "icon": "🧠",
        "command": "gemini --yolo --model gemini-2.0-flash-thinking-exp",
        "session_cmd": None,
        "add_image_cmd": "add {path}",
        "prompt_char": ">",
        "color": "#7dcfff",
        "supports_image": True,
        "description": "Gemini 2.0 Flash Thinking"
    },
    "codex": {
        "name": "Codex",
        "icon": "🟠",
        "command": "codex",
        "session_cmd": None,  # No UUID-based session support (only picker/last)
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
        "session_cmd": None,  # OpenCode uses internal session IDs (ses_xxx format), not UUIDs
        "add_image_cmd": None,
        "prompt_char": ">",
        "color": "#bb9af7",
        "supports_image": False,
        "description": "OpenCode CLI"
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
MAX_TERMINALS = 4

AgentType = Literal["claude", "gemini", "codex", "opencode", "shell"]


class TerminalSession:
    """Single terminal session with PTY"""

    def __init__(self, session_id: str, working_dir: str = None,
                 agent_type: AgentType = "claude", role: str = "General", resume: bool = True):
        self.session_id = session_id
        self.working_dir = working_dir or os.getcwd()
        self.agent_type = agent_type
        self.role = role
        self.resume = resume
        self.pty: Optional[PtyProcess] = None
        self.websocket: Optional[WebSocket] = None
        self._read_task: Optional[asyncio.Task] = None
        self._running = False
        self._temp_files: set[str] = set()  # Track temp files for cleanup (set으로 중복 방지)

        # Get agent config
        self.config = AGENT_CONFIGS.get(agent_type, AGENT_CONFIGS["claude"])

    def _is_valid_uuid(self, s: str) -> bool:
        """Check if string is valid UUID v4"""
        if not s:
            return False
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        return bool(re.match(pattern, s, re.IGNORECASE))

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

            # Only add session ID if it's valid UUID (required by Claude CLI)
            if session_cmd and self.session_id and self._is_valid_uuid(self.session_id):
                cmd = f'{cmd} {session_cmd.format(session_id=self.session_id)}'
            elif session_cmd and self.session_id:
                # Invalid session ID format - skip session option
                print(f"[Terminal] Warning: Invalid session ID format '{self.session_id}', skipping --session-id")

            # Add role-based system prompt (Persona Injection)
            # Note: Only for agents that support it (e.g., Claude with --append-system-prompt)
            system_prompt_cmd = self.config.get("system_prompt_cmd")
            role_prompt = ROLE_PROMPTS.get(self.role)
            if system_prompt_cmd and role_prompt:
                # Validate prompt - reject dangerous characters that could enable command injection
                dangerous_chars = ['`', '$', '|', ';', '&', '>', '<', '\x00']
                if any(char in role_prompt for char in dangerous_chars):
                    print(f"[Terminal] Warning: Role prompt contains dangerous characters, skipping")
                else:
                    # Escape for Windows compatibility
                    escaped_prompt = role_prompt.replace('"', '\\"').replace('\n', ' ').replace('\r', '')
                    cmd = f'{cmd} {system_prompt_cmd} "{escaped_prompt}"'

            print(f"[Terminal] Starting: {cmd}")
            print(f"[Terminal] Working dir: {self.working_dir}")

            # Set environment variables for proper terminal behavior
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            env['COLORTERM'] = 'truecolor'
            env['LANG'] = env.get('LANG', 'en_US.UTF-8')

            self.pty = PtyProcess.spawn(
                cmd,
                cwd=self.working_dir,
                env=env,
                dimensions=(24, 80)
            )
            self._running = True
            print(f"[Terminal] PTY spawned, PID: {self.pty.pid}, alive: {self.pty.isalive()}")

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
            print(f"[Terminal] Failed to start: {e}")
            traceback.print_exc()
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to start {self.config['name']}: {e}"
            })
            return False

    async def _read_pty_output(self):
        """Read PTY output and send to WebSocket"""
        loop = asyncio.get_event_loop()
        read_count = 0

        print(f"[Terminal] Read loop started for {self.session_id[:8]}...")

        while self._running and self.pty:
            try:
                # Check if PTY is still alive before reading
                if not self.pty.isalive():
                    print(f"[Terminal] PTY not alive, exitcode: {self.pty.exitstatus}")
                    break

                data = await loop.run_in_executor(
                    None,
                    lambda: self.pty.read(16384) if self.pty and self.pty.isalive() else ""
                )

                if data:
                    if self.websocket:
                        read_count += 1
                        if read_count <= 3:  # Log first few reads
                            print(f"[Terminal] Read #{read_count}: {len(data)} bytes")
                        await self.websocket.send_json({
                            "type": "terminal_output",
                            "data": data
                        })
                    # Data flow active - small sleep to prevent busy loop while maintaining responsiveness
                    await asyncio.sleep(0.001)
                else:
                    # No data - longer sleep to reduce CPU usage
                    await asyncio.sleep(0.05)

            except Exception as e:
                print(f"[Terminal] Read exception: {type(e).__name__}: {e}")
                break

        # Terminal closed - notify client with exit info
        exit_code = None
        try:
            exit_code = self.pty.exitstatus if self.pty else None
        except Exception:
            pass

        print(f"[Terminal] Read loop ended for {self.session_id[:8]}..., total reads: {read_count}, exit_code: {exit_code}")

        if self.websocket:
            try:
                # Send detailed close message
                await self.websocket.send_json({
                    "type": "terminal_closed",
                    "exit_code": exit_code,
                    "reads": read_count
                })
                # If process exited immediately (0 reads), send error hint
                if read_count == 0:
                    await self.websocket.send_json({
                        "type": "terminal_output",
                        "data": f"\\r\\n\\x1b[31m[프로세스가 즉시 종료됨 (exit: {exit_code})]\\x1b[0m\\r\\n"
                    })
                    await self.websocket.send_json({
                        "type": "terminal_output",
                        "data": "\\x1b[33m터미널에서 직접 명령어를 테스트해보세요:\\x1b[0m\\r\\n"
                    })
                    await self.websocket.send_json({
                        "type": "terminal_output",
                        "data": f"\\x1b[36m  {self.config['command']}\\x1b[0m\\r\\n"
                    })
            except Exception:
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
                # Validate and clamp rows/cols to prevent DoS or invalid values
                rows = max(10, min(200, rows))
                cols = max(20, min(400, cols))
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

            # Check base64 string length before decoding to prevent DoS
            # Base64 is ~33% larger than binary, so 70MB base64 = ~50MB decoded
            MAX_BASE64_SIZE = 70 * 1024 * 1024
            if len(image_data) > MAX_BASE64_SIZE:
                if self.websocket:
                    await self.websocket.send_json({
                        "type": "error",
                        "message": "Image data too large (max ~50MB)"
                    })
                return None

            # Base64 검증
            try:
                image_bytes = base64.b64decode(image_data, validate=True)
            except Exception as e:
                if self.websocket:
                    await self.websocket.send_json({
                        "type": "error",
                        "message": f"Invalid image data: {e}"
                    })
                return None

            # 크기 제한 (50MB)
            if len(image_bytes) > 50 * 1024 * 1024:
                if self.websocket:
                    await self.websocket.send_json({
                        "type": "error",
                        "message": "Image too large (max 50MB)"
                    })
                return None

            # Save to temp file (UUID 추가로 충돌 방지)
            ext = Path(filename).suffix or ".png"
            # 지원 포맷 검증
            allowed_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
            if ext.lower() not in allowed_exts:
                ext = '.png'
            temp_dir = tempfile.gettempdir()
            unique_id = str(uuid.uuid4())[:8]
            temp_path = os.path.join(temp_dir, f"ai_image_{self.session_id[:8]}_{unique_id}{ext}")

            with open(temp_path, "wb") as f:
                f.write(image_bytes)

            # Track temp file for cleanup (set이므로 중복 자동 무시)
            self._temp_files.add(temp_path)

            # Send file path using agent's add command (no Enter - let user press it)
            cmd = add_cmd.format(path=temp_path) + " "
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
                # Force kill on Windows
                if self.pty.isalive():
                    pid = self.pty.pid
                    self.pty.terminate(force=True)
                    # Extra: kill process tree on Windows
                    if os.name == 'nt':
                        try:
                            subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                                          capture_output=True, timeout=5)
                        except subprocess.TimeoutExpired:
                            print(f"[Terminal] taskkill timeout for PID {pid}")
                        except Exception as e:
                            print(f"[Terminal] taskkill error: {e}")
            except Exception as e:
                print(f"[Terminal] Stop error: {e}")
            self.pty = None

        # Cleanup temp files (복사본으로 iteration하여 thread-safety 보장)
        temp_files_copy = list(self._temp_files)
        self._temp_files = set()  # 먼저 clear하여 race condition 방지
        for temp_path in temp_files_copy:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    print(f"[Terminal] Cleaned up temp file: {temp_path}")
            except Exception as e:
                print(f"[Terminal] Failed to cleanup temp file {temp_path}: {e}")


# Active terminal sessions
terminal_sessions: dict[str, TerminalSession] = {}


async def cleanup_all_sessions():
    """Stop all terminal sessions before server shutdown"""
    print(f"[Terminal] Cleaning up {len(terminal_sessions)} sessions...")
    for session_id, session in list(terminal_sessions.items()):
        try:
            await session.stop()
            print(f"[Terminal] Stopped session: {session_id[:8]}...")
        except Exception as e:
            print(f"[Terminal] Error stopping {session_id[:8]}: {e}")
    terminal_sessions.clear()
    print("[Terminal] All sessions cleaned up")


async def handle_terminal_websocket(
    websocket: WebSocket,
    session_id: str,
    working_dir: str = None,
    agent_type: str = "claude",
    role: str = "General",
    resume: bool = True,
    already_accepted: bool = False
):
    """Handle WebSocket connection for terminal"""
    if not already_accepted:
        await websocket.accept()

    # Validate agent type
    if agent_type not in AGENT_CONFIGS:
        agent_type = "claude"

    # Validate role
    if role not in ROLE_PROMPTS:
        role = "General"

    # Create or get session
    if session_id in terminal_sessions:
        session = terminal_sessions[session_id]
        await session.stop()

    session = TerminalSession(session_id, working_dir, agent_type=agent_type, role=role, resume=resume)
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
