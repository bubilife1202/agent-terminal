#!/usr/bin/env python3
"""
Agent Terminal - ChatOps Collaboration Edition
Features:
1. Target Routing UI (Visual connection)
2. Persona Injection (Performance boost via System Prompts)
3. Inter-Agent Communication Message Bus
"""

__version__ = "1.6.0"

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Optional
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Import terminal handler
# If src.terminal is missing (usually due to pywinpty not installed), we define minimal handlers
# and display a clear error message to the user.
TERMINAL_IMPORT_ERROR = None
try:
    from src.terminal import handle_terminal_websocket, get_available_agents, get_max_terminals
except ImportError as e:
    TERMINAL_IMPORT_ERROR = str(e)
    print(f"\n{'='*60}")
    print("WARNING: Terminal module failed to load!")
    print(f"Error: {e}")
    print("\nThis usually means 'pywinpty' is not installed.")
    print("Install it with: pip install pywinpty")
    print("Or run: pip install -r requirements.txt")
    print(f"{'='*60}\n")

    # Standalone mock that shows error to user
    async def handle_terminal_websocket(websocket, session_id, work_dir, agent_type, role, resume, already_accepted=False):
        if not already_accepted:
            await websocket.accept()
        # Show error message to user
        error_msg = (
            "\r\n\x1b[31m" + "="*50 + "\x1b[0m\r\n"
            "\x1b[31m  ERROR: Terminal module not available\x1b[0m\r\n"
            "\x1b[31m" + "="*50 + "\x1b[0m\r\n\r\n"
            "\x1b[33m  The 'pywinpty' package is required for PTY support.\x1b[0m\r\n\r\n"
            "\x1b[36m  To fix this, run:\x1b[0m\r\n"
            "    pip install pywinpty\r\n\r\n"
            "\x1b[36m  Or install all requirements:\x1b[0m\r\n"
            "    pip install -r requirements.txt\r\n\r\n"
            f"\x1b[90m  Original error: {TERMINAL_IMPORT_ERROR}\x1b[0m\r\n"
        )
        await websocket.send_json({"type": "terminal_output", "data": error_msg})
        await websocket.send_json({"type": "terminal_closed"})
        try:
            while True:
                data = await websocket.receive_json()
                # Echo back that terminal is not working
                if data.get("type") == "input":
                    await websocket.send_json({
                        "type": "terminal_output",
                        "data": "\r\n\x1b[31m[Terminal unavailable - install pywinpty]\x1b[0m\r\n"
                    })
        except Exception:
            pass
    def get_available_agents(): return []
    def get_max_terminals(): return 6

# Load HTML content from template file
TEMPLATES_DIR = Path(__file__).parent / "templates"
try:
    HTML_CONTENT = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
except FileNotFoundError:
    HTML_CONTENT = """<!DOCTYPE html><html><body>
    <h1>Error: Template not found</h1>
    <p>templates/index.html is missing. Please restore the file.</p>
    </body></html>"""
    print(f"WARNING: templates/index.html not found!")

app = FastAPI(title="Agent Terminal Pro")

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8090", "http://127.0.0.1:8090"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (CSS, JS)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ========== Message Bus (The Brain) ==========
# Stores active sessions to allow routing messages between agents
class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, WebSocket] = {}
        self.agent_info: Dict[str, dict] = {}  # Stores role, type, name
        self._dead_sessions: list = []  # 정리 대기 세션

    def register(self, session_id: str, websocket: WebSocket, info: dict):
        # 기존 세션이 있으면 먼저 정리
        if session_id in self.sessions:
            try:
                old_ws = self.sessions[session_id]
                if old_ws and not old_ws.client_state.DISCONNECTED:
                    asyncio.create_task(old_ws.close())
            except Exception:
                pass
        self.sessions[session_id] = websocket
        self.agent_info[session_id] = info

    def unregister(self, session_id: str):
        self.sessions.pop(session_id, None)
        self.agent_info.pop(session_id, None)

    async def broadcast(self, sender_id: str, message: str):
        # 복사본으로 반복하여 동시성 문제 방지
        sessions_copy = dict(self.sessions)
        dead_sessions = []

        for sid, ws in sessions_copy.items():
            if sid != sender_id:
                try:
                    await ws.send_json({
                        "type": "broadcast_message",
                        "sender": self.agent_info.get(sender_id, {}).get("name", "Unknown"),
                        "message": message
                    })
                except Exception:
                    dead_sessions.append(sid)

        # 죽은 세션 정리
        for sid in dead_sessions:
            self.unregister(sid)

    async def send_direct(self, target_index: int, sender_id: str, message: str, context: str = ""):
        # 복사본으로 검색
        agent_info_copy = dict(self.agent_info)
        target_sid = None
        for sid, info in agent_info_copy.items():
            if info.get("index") == target_index:
                target_sid = sid
                break

        if target_sid and target_sid in self.sessions:
            try:
                sender_name = self.agent_info.get(sender_id, {}).get("name", "Agent")
                sender_role = self.agent_info.get(sender_id, {}).get("role", "User")

                formatted_msg = f"""
\x1b[38;5;75m╭──────────────────────────────────────────────╮
│ 📨 MESSAGE from @{sender_name} ({sender_role})          │
├──────────────────────────────────────────────┤
│ {message}
│
│ \x1b[90m[Context/Output Attached]\x1b[0m
│ {context[:500]}... (truncated)
╰──────────────────────────────────────────────╯\x1b[0m"""
                await self.sessions[target_sid].send_json({
                    "type": "inject_input",
                    "data": formatted_msg
                })
                return True
            except Exception:
                self.unregister(target_sid)
        return False

manager = SessionManager()

# ========== System Prompts (The Intelligence) ==========
PERSONAS = {
    "PM": """
You are an expert Technical Project Manager.
Your Goal: Break down vague requirements into clear, actionable technical tasks.
Rules:
1. Do NOT write code implementation details.
2. Focus on architecture, file structure, and step-by-step planning.
3. Use the '>>' pipe command to delegate tasks to the Developer.
""",
    "Dev": """
You are a Senior Full-Stack Developer.
Your Goal: Write clean, production-ready code based on instructions.
Rules:
1. Focus on implementation. Write filenames and code blocks clearly.
2. If specifications are missing, ask the PM.
3. Keep explanations concise. Code is your language.
""",
    "QA": """
You are a QA Lead and Security Specialist.
Your Goal: Find bugs, security flaws, and logic errors.
Rules:
1. Review code critically.
2. Suggest test cases.
3. Verify if the code meets the PM's requirements.
""",
    "Architect": """
You are a Software Architect (Deep Thinking Mode).
Your Goal: Analyze complex problems with deep reasoning.
Rules:
1. THINK STEP-BY-STEP. Outline your logic before concluding.
2. Consider scalability, edge cases, and security implications.
3. Provide a high-level design or strategy before implementation details.
"""
}

# ========== API Endpoints ==========

@app.get("/api/version")
async def get_version():
    return {"version": __version__}

@app.get("/api/agents")
async def list_agents():
    # Helper to get drives/folders logic same as before...
    return {"agents": get_available_agents(), "max_terminals": get_max_terminals()}

@app.get("/api/folders")
async def list_folders_api(path: str = None):
    # (Reuse existing logic for brevity in this single file update)
    import string
    if not path or path == "drives":
        drives = [{"name": f"{d}:", "path": f"{d}:\\", "is_drive": True}
                  for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        return {"current": "My Computer", "folders": drives, "is_root": True}

    try:
        base = Path(path).resolve()
        # Validate path is a real directory to prevent path traversal attacks
        if not base.exists() or not base.is_dir():
            return {"current": path, "folders": [], "error": "Invalid directory path"}
        folders = []
        for item in base.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                folders.append({"name": item.name, "path": str(item)})
        parent = str(base.parent) if base.parent != base else "drives"
        return {"current": str(base), "parent": parent, "folders": folders[:100]}
    except (OSError, ValueError, PermissionError) as e:
        print(f"[API] Error listing folders for path '{path}': {e}")
        return {"current": path, "folders": []}

@app.get("/api/files")
async def list_files_api(path: str):
    try:
        base = Path(path).resolve()
        # Validate path is a real directory to prevent path traversal attacks
        if not base.exists() or not base.is_dir():
            return {"path": path, "items": [], "error": "Invalid directory path"}
        items = [{"name": i.name, "path": str(i), "is_dir": i.is_dir()}
                 for i in base.iterdir() if not i.name.startswith('.')]
        # Include parent path for navigation
        parent = str(base.parent) if base.parent != base else None
        return {"path": str(base), "parent": parent, "items": sorted(items, key=lambda x: (not x['is_dir'], x['name']))[:200]}
    except (OSError, ValueError, PermissionError) as e:
        print(f"[API] Error listing files for path '{path}': {e}")
        return {"path": path, "items": []}

@app.get("/api/file-content")
async def get_file_content(path: str):
    """Read file content for preview"""
    try:
        file_path = Path(path).resolve()
        
        # Security: check file exists and is a file
        if not file_path.exists():
            return JSONResponse({"error": "File not found"}, status_code=404)
        if not file_path.is_file():
            return JSONResponse({"error": "Not a file"}, status_code=400)
        
        # Check file size (limit to 1MB)
        file_size = file_path.stat().st_size
        if file_size > 1024 * 1024:
            return JSONResponse({
                "error": "File too large",
                "size": file_size,
                "message": "File exceeds 1MB limit"
            }, status_code=400)
        
        # Check if binary file
        BINARY_EXTENSIONS = {'.exe', '.dll', '.so', '.dylib', '.bin', '.obj', '.o',
                           '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp',
                           '.mp3', '.mp4', '.wav', '.avi', '.mov', '.mkv',
                           '.zip', '.tar', '.gz', '.rar', '.7z',
                           '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                           '.pyc', '.pyd', '.whl', '.egg'}
        if file_path.suffix.lower() in BINARY_EXTENSIONS:
            return JSONResponse({
                "error": "Binary file",
                "message": "Cannot preview binary files"
            }, status_code=400)
        
        # Try to read as text
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding='cp949')  # Korean encoding fallback
            except UnicodeDecodeError:
                return JSONResponse({
                    "error": "Binary file",
                    "message": "File appears to be binary or has unknown encoding"
                }, status_code=400)
        
        # Determine file type for syntax highlighting
        ext = file_path.suffix.lower()
        lang_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.jsx': 'javascript', '.tsx': 'typescript', '.json': 'json',
            '.html': 'html', '.css': 'css', '.scss': 'scss', '.less': 'less',
            '.md': 'markdown', '.yaml': 'yaml', '.yml': 'yaml',
            '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash',
            '.sql': 'sql', '.xml': 'xml', '.java': 'java',
            '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.hpp': 'cpp',
            '.go': 'go', '.rs': 'rust', '.rb': 'ruby', '.php': 'php',
            '.swift': 'swift', '.kt': 'kotlin', '.scala': 'scala',
            '.r': 'r', '.R': 'r', '.lua': 'lua', '.pl': 'perl',
            '.toml': 'toml', '.ini': 'ini', '.cfg': 'ini',
            '.dockerfile': 'dockerfile', '.gitignore': 'plaintext',
            '.env': 'plaintext', '.txt': 'plaintext'
        }
        language = lang_map.get(ext, 'plaintext')
        
        return {
            "path": str(file_path),
            "name": file_path.name,
            "content": content,
            "language": language,
            "size": file_size
        }
    except (OSError, ValueError, PermissionError) as e:
        print(f"[API] Error reading file '{path}': {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/restart")
async def restart_server():
    """Restart the server process in a new console window"""
    from src.terminal import cleanup_all_sessions

    async def do_restart():
        # 1. 모든 터미널 세션 정리
        await cleanup_all_sessions()
        await asyncio.sleep(0.3)

        # 2. 새 콘솔에서 재시작하도록 플래그 파일 생성
        flag_file = Path(__file__).parent / ".restart-new-console"
        flag_file.touch()
        print("[Restart] Created restart flag, exiting...")

        # 3. 프로세스 종료 -> start.bat이 플래그 확인 후 새 콘솔 오픈
        os._exit(0)

    asyncio.create_task(do_restart())
    return JSONResponse({"status": "restarting"})

# ========== WebSocket ==========

# Health check WebSocket connections
health_check_clients: set = set()

@app.websocket("/ws/health")
async def health_websocket(websocket: WebSocket):
    """WebSocket endpoint for health check - replaces polling"""
    await websocket.accept()
    health_check_clients.add(websocket)
    try:
        while True:
            # Wait for ping from client or just keep connection alive
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        health_check_clients.discard(websocket)

@app.websocket("/ws/terminal/{session_id}")
async def terminal_websocket(
    websocket: WebSocket,
    session_id: str,
    workdir: str = None,
    agent: str = "claude",
    role: str = "General", # New: Persona
    index: int = 0
):
    await websocket.accept()
    
    # Register session
    manager.register(session_id, websocket, {
        "name": agent.capitalize(),
        "type": agent,
        "role": role,
        "index": index
    })
    
    # Inject Persona (System Prompt)
    if role in PERSONAS:
        prompt = f"\r\n\x1b[33m[System] Injecting {role} Persona...\x1b[0m\r\n"
        await websocket.send_json({"type": "terminal_output", "data": prompt})

    try:
        await handle_terminal_websocket(websocket, session_id, working_dir=workdir, agent_type=agent, role=role, resume=True, already_accepted=True)
    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister(session_id)


# ========== HTML UI (loaded from templates/index.html) ==========
# HTML_CONTENT is now loaded from templates/index.html at module level (see top of file)


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_CONTENT

# ========== Shutdown Handler ==========
@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 모든 터미널 세션 정리"""
    print("[Server] Shutdown event triggered...")
    try:
        from src.terminal import cleanup_all_sessions
        await cleanup_all_sessions()
        print("[Server] All sessions cleaned up on shutdown")
    except Exception as e:
        print(f"[Server] Shutdown cleanup error: {e}")

if __name__ == "__main__":
    print("Agent Terminal Pro with ChatOps & Persona Injection Started...")
    uvicorn.run(app, host="127.0.0.1", port=8090)
