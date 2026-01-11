#!/usr/bin/env python3
"""
Agent Terminal - ChatOps Collaboration Edition
Features:
1. Target Routing UI (Visual connection)
2. Persona Injection (Performance boost via System Prompts)
3. Inter-Agent Communication Message Bus
"""

__version__ = "1.2.3"

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Optional
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Import terminal handler
# If src.terminal is missing, we define minimal handlers here to ensure it works standalone.
try:
    from src.terminal import handle_terminal_websocket, get_available_agents, get_max_terminals
except ImportError:
    # Standalone mock for robustness
    async def handle_terminal_websocket(websocket, session_id, work_dir, agent_type, role, resume, already_accepted=False):
        if not already_accepted:
            await websocket.accept()
        # Mock terminal behavior
        await websocket.send_json({"type": "terminal_started", "data": "Terminal Started"})
        try:
            while True:
                data = await websocket.receive_json()
        except:
            pass
    def get_available_agents(): return []
    def get_max_terminals(): return 6

app = FastAPI(title="Agent Terminal Pro")

# ========== Message Bus (The Brain) ==========
# Stores active sessions to allow routing messages between agents
class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, WebSocket] = {}
        self.agent_info: Dict[str, dict] = {} # Stores role, type, name

    def register(self, session_id: str, websocket: WebSocket, info: dict):
        self.sessions[session_id] = websocket
        self.agent_info[session_id] = info

    def unregister(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.agent_info:
            del self.agent_info[session_id]

    async def broadcast(self, sender_id: str, message: str):
        # Broadcast to all except sender
        for sid, ws in self.sessions.items():
            if sid != sender_id:
                try:
                    await ws.send_json({
                        "type": "broadcast_message",
                        "sender": self.agent_info.get(sender_id, {}).get("name", "Unknown"),
                        "message": message
                    })
                except:
                    pass

    async def send_direct(self, target_index: int, sender_id: str, message: str, context: str = ""):
        # Find target by index (0, 1, 2...)
        target_sid = None
        for sid, info in self.agent_info.items():
            if info.get("index") == target_index:
                target_sid = sid
                break
        
        if target_sid and target_sid in self.sessions:
            sender_name = self.agent_info.get(sender_id, {}).get("name", "Agent")
            sender_role = self.agent_info.get(sender_id, {}).get("role", "User")
            
            # Format the message as a structured report
            formatted_msg = f"""
\x1b[38;5;75m╭──────────────────────────────────────────────╮
│ 📨 MESSAGE from @{sender_name} ({sender_role})          │
├──────────────────────────────────────────────┤
│ {message}
│ 
│ \x1b[90m[Context/Output Attached]\x1b[0m
│ {context[:500]}... (truncated)
╰──────────────────────────────────────────────╯\x1b[0m"""
            # In a real PTY, we write to the input, but here we send via WS to be handled
            await self.sessions[target_sid].send_json({
                "type": "inject_input",
                "data": formatted_msg
            })
            return True
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
        drives = [{"name": f"💾 {d}:", "path": f"{d}:\\", "is_drive": True} 
                  for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        return {"current": "My Computer", "folders": drives, "is_root": True}
    
    try:
        base = Path(path)
        folders = []
        for item in base.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                folders.append({"name": item.name, "path": str(item)})
        parent = str(base.parent) if base.parent != base else "drives"
        return {"current": str(base), "parent": parent, "folders": folders[:100]}
    except:
        return {"current": path, "folders": []}

@app.get("/api/files")
async def list_files_api(path: str):
    try:
        base = Path(path)
        items = [{"name": i.name, "path": str(i), "is_dir": i.is_dir()}
                 for i in base.iterdir() if not i.name.startswith('.')]
        return {"path": str(base), "items": sorted(items, key=lambda x: (not x['is_dir'], x['name']))[:200]}
    except:
        return {"path": path, "items": []}

@app.post("/api/restart")
async def restart_server():
    """Restart the server process"""
    import subprocess
    from src.terminal import cleanup_all_sessions

    async def do_restart():
        # 1. 모든 터미널 세션 정리 (PTY 프로세스 종료)
        await cleanup_all_sessions()
        await asyncio.sleep(0.5)

        # 2. 새 서버 시작 후 현재 프로세스 종료
        if os.name == 'nt':  # Windows
            subprocess.Popen(
                [sys.executable] + sys.argv,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            os._exit(0)
        else:  # Unix
            os.execv(sys.executable, [sys.executable] + sys.argv)

    asyncio.create_task(do_restart())
    return JSONResponse({"status": "restarting"})

# ========== WebSocket ==========

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
        await handle_terminal_websocket(websocket, session_id, workdir, agent, role=role, resume=True, already_accepted=True)
    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister(session_id)


# ========== HTML UI ==========

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>Agent Terminal Pro</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css">
    <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-web-links@0.9.0/lib/xterm-addon-web-links.js"></script>
    <style>
        :root { --bg: #0f1117; --panel: #1a1c23; --border: #2f333d; --accent: #5e81ac; --text: #e6e6e6; }
        * { box-sizing: border-box; }
        body { margin: 0; background: var(--bg); color: var(--text); font-family: 'Consolas', monospace; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

        /* Header */
        .header { height: 44px; background: var(--panel); border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 12px; justify-content: space-between; gap: 12px; }

        /* Server Status Indicator */
        .server-status { display: flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; background: #2c3039; border: 1px solid var(--border); }
        .server-status .dot { width: 8px; height: 8px; border-radius: 50%; }
        .server-status.connected .dot { background: #98c379; box-shadow: 0 0 6px #98c379; }
        .server-status.reconnecting .dot { background: #e0af68; animation: blink 0.5s infinite; }
        .server-status.disconnected .dot { background: #e06c75; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .header-left { display: flex; align-items: center; gap: 8px; }
        .header-right { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }

        /* Layout */
        .main { flex: 1; display: flex; overflow: hidden; }
        .sidebar { width: 240px; background: var(--panel); border-right: 1px solid var(--border); display: flex; flex-direction: column; transition: width 0.2s; }
        .sidebar.hidden { width: 0; overflow: hidden; padding: 0; }
        .terminal-area { flex: 1; display: flex; flex-direction: column; padding: 4px; gap: 4px; background: #000; min-width: 0; }

        /* Grid Layouts */
        .grid { display: grid; flex: 1; gap: 4px; min-height: 0; }
        .grid.cols-1 { grid-template-columns: 1fr; }
        .grid.cols-2 { grid-template-columns: 1fr 1fr; }
        .grid.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
        .grid.cols-4 { grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }
        .grid.cols-6 { grid-template-columns: 1fr 1fr 1fr; grid-template-rows: 1fr 1fr; }

        /* Components */
        .btn { background: #2c3039; border: 1px solid var(--border); color: var(--text); padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; white-space: nowrap; transition: all 0.15s; }
        .btn:hover { border-color: var(--accent); background: #363d49; }
        .btn.primary { background: var(--accent); border-color: var(--accent); color: white; }
        .btn.primary:hover { background: #6d96c7; }
        .btn.active { background: var(--accent); border-color: var(--accent); }

        select { background: #2c3039; border: 1px solid var(--border); color: var(--text); font-family: inherit; font-size: 11px; padding: 4px 6px; border-radius: 4px; outline: none; cursor: pointer; }
        select:hover { border-color: var(--accent); }

        /* Layout Buttons */
        .layout-btn { background: #2c3039; border: 1px solid var(--border); color: #666; padding: 4px 6px; border-radius: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s; }
        .layout-btn:hover { border-color: var(--accent); color: #999; }
        .layout-btn.active { background: var(--accent); border-color: var(--accent); color: white; }

        /* Terminal Cell */
        .cell { display: flex; flex-direction: column; background: var(--panel); border: 2px solid var(--border); border-radius: 6px; overflow: hidden; min-height: 0; }
        .cell.active { border-color: var(--accent); box-shadow: 0 0 10px rgba(94, 129, 172, 0.3); }

        .cell-toolbar { height: 34px; background: #21252b; display: flex; align-items: center; padding: 0 8px; gap: 6px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
        .agent-icon { font-size: 16px; }
        .agent-name { font-size: 11px; font-weight: bold; color: #abb2bf; }
        .role-tag { font-size: 9px; padding: 2px 6px; border-radius: 10px; background: #3e4451; color: #abb2bf; text-transform: uppercase; font-weight: bold; }
        .role-tag.PM { background: #98c379; color: #1e2518; }
        .role-tag.Dev { background: #61afef; color: #162433; }
        .role-tag.QA { background: #e06c75; color: #2e1618; }

        .role-select { font-size: 10px; padding: 2px 4px; border-radius: 4px; background: #3e4451; border: 1px solid var(--border); color: var(--text); cursor: pointer; }
        .role-select:hover { border-color: var(--accent); }
        .role-select:focus { outline: none; border-color: var(--accent); }

        .cell-actions { display: flex; align-items: center; gap: 4px; margin-left: auto; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #5c6370; }
        .status-dot.live { background: #98c379; box-shadow: 0 0 6px #98c379; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }

        .cell-btn { background: transparent; border: none; color: #666; cursor: pointer; padding: 2px 6px; font-size: 14px; border-radius: 3px; }
        .cell-btn:hover { background: #3e4451; color: var(--text); }

        .term-container { flex: 1; position: relative; overflow: hidden; padding: 2px; min-height: 0; }

        /* Maximized terminal */
        .cell.maximized { position: fixed; inset: 0; z-index: 999; border-radius: 0; border: none; }
        .cell.maximized .cell-toolbar { border-radius: 0; }
        .maximize-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 998; }
        .maximize-overlay.show { display: block; }

        /* Modal */
        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 1000; opacity: 0; visibility: hidden; transition: all 0.2s; }
        .modal-overlay.show { opacity: 1; visibility: visible; }
        .modal { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; width: 500px; max-width: 90vw; max-height: 80vh; display: flex; flex-direction: column; transform: scale(0.95); transition: transform 0.2s; }
        .modal-overlay.show .modal { transform: scale(1); }
        .modal-header { padding: 12px 16px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .modal-header h3 { margin: 0; font-size: 14px; }
        .modal-body { flex: 1; overflow-y: auto; padding: 12px; }
        .modal-footer { padding: 12px 16px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 8px; }

        /* Folder Browser */
        .folder-path { background: #000; padding: 8px 12px; border-radius: 4px; margin-bottom: 12px; font-size: 12px; color: #61afef; display: flex; align-items: center; gap: 8px; }
        .folder-path button { background: #2c3039; border: 1px solid var(--border); color: var(--text); padding: 2px 8px; border-radius: 3px; cursor: pointer; font-size: 11px; }
        .folder-list { display: flex; flex-direction: column; gap: 2px; }
        .folder-item { padding: 8px 12px; border-radius: 4px; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 12px; transition: background 0.1s; }
        .folder-item:hover { background: #2c3039; }
        .folder-item.selected { background: var(--accent); color: white; }
        .folder-item .icon { font-size: 16px; }

        /* Toast */
        .toast-container { position: fixed; bottom: 20px; right: 20px; z-index: 2000; display: flex; flex-direction: column; gap: 8px; }
        .toast { background: var(--panel); border: 1px solid var(--border); padding: 10px 16px; border-radius: 6px; font-size: 12px; animation: slideIn 0.2s; }
        .toast.success { border-color: #98c379; }
        .toast.error { border-color: #e06c75; }
        .toast.warning { border-color: #e0af68; }
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

        /* Agent Select Grid */
        .agent-select-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
        .agent-select-item { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 16px 8px; background: #2c3039; border: 2px solid var(--border); border-radius: 8px; cursor: pointer; transition: all 0.15s; }
        .agent-select-item:hover { border-color: var(--accent); background: #363d49; }
        .agent-select-item.selected { border-color: var(--accent); background: var(--accent); }
        .agent-select-item .icon { font-size: 28px; }
        .agent-select-item .name { font-size: 11px; font-weight: bold; color: var(--text); }

        /* Project List Sidebar */
        .sidebar-section { border-bottom: 1px solid var(--border); }
        .sidebar-section-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; font-size: 11px; font-weight: bold; color: #abb2bf; cursor: pointer; user-select: none; }
        .sidebar-section-header:hover { background: #2c3039; }
        .sidebar-section-header .toggle { font-size: 10px; color: #5c6370; }
        .sidebar-section-content { max-height: 200px; overflow-y: auto; }
        .sidebar-section-content.collapsed { display: none; }

        .project-item { display: flex; align-items: center; gap: 6px; padding: 6px 10px; font-size: 11px; cursor: pointer; color: #abb2bf; transition: background 0.1s; border-left: 2px solid transparent; }
        .project-item:hover { background: #2c3039; border-left-color: var(--accent); }
        .project-item.active { background: var(--accent); color: white; border-left-color: white; }
        .project-item .icon { font-size: 14px; flex-shrink: 0; }
        .project-item .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .project-item .actions { display: none; gap: 2px; }
        .project-item:hover .actions { display: flex; }
        .project-item .action-btn { background: none; border: none; color: #5c6370; cursor: pointer; padding: 2px; font-size: 12px; border-radius: 3px; }
        .project-item .action-btn:hover { background: #3e4451; color: var(--text); }

        /* File Explorer - 다른 스타일 */
        .file-item { display: flex; align-items: center; gap: 6px; padding: 4px 8px; font-size: 11px; cursor: pointer; color: #8b949e; border-radius: 3px; }
        .file-item:hover { background: #2c3039; color: #c9d1d9; }
        .file-item.dir { color: #58a6ff; }
        .file-item .file-icon { font-size: 12px; flex-shrink: 0; opacity: 0.8; }
        .file-item .file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .file-item .file-actions { display: none; gap: 2px; }
        .file-item:hover .file-actions { display: flex; }

        /* Project Tabs Bar - 멀티 프로젝트 지원 */
        .project-tabs-bar { height: 28px; background: var(--bg); border-bottom: 1px solid var(--border); display: flex; align-items: stretch; padding: 0 4px; gap: 2px; overflow-x: auto; flex-shrink: 0; }
        .project-tabs-bar::-webkit-scrollbar { display: none; }
        .project-tabs-bar:empty { display: none; }
        .project-tab { display: flex; align-items: center; gap: 6px; padding: 0 10px; margin-top: 4px; background: #1a1d24; color: #888; border: 1px solid var(--border); border-bottom: none; border-radius: 6px 6px 0 0; cursor: pointer; font-size: 11px; white-space: nowrap; max-width: 180px; transition: all 0.15s; }
        .project-tab:hover { background: #252a35; color: #bbb; }
        .project-tab.active { background: #000; color: var(--text); border-color: var(--accent); border-bottom: 1px solid #000; margin-bottom: -1px; z-index: 1; }
        .project-tab .tab-name { overflow: hidden; text-overflow: ellipsis; flex: 1; }
        .project-tab .tab-count { background: var(--accent); color: white; font-size: 9px; padding: 1px 5px; border-radius: 8px; font-weight: bold; }
        .project-tab .tab-close { background: none; border: none; color: #666; cursor: pointer; padding: 0 2px; font-size: 14px; line-height: 1; opacity: 0; transition: opacity 0.15s; }
        .project-tab:hover .tab-close { opacity: 0.7; }
        .project-tab .tab-close:hover { opacity: 1; color: #e06c75; }
        .add-project-btn { background: transparent; border: 1px dashed #444; color: #666; width: 24px; margin: 4px 0; border-radius: 4px; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center; }
        .add-project-btn:hover { border-color: var(--accent); color: var(--accent); }

        /* Project Grid visibility */
        .project-grid { display: none; width: 100%; height: 100%; }
        .project-grid.active { display: grid; }
    </style>
</head>
<body>
    <header class="header">
        <div class="header-left">
            <span style="font-size: 18px;">🤖</span>
            <span style="font-weight: bold; font-size: 14px;">Agent Terminal</span>
            <span id="versionDisplay" style="font-size: 10px; color: #5c6370; margin-left: -4px;">v...</span>
            <div class="server-status disconnected" id="serverStatus">
                <span class="dot"></span>
                <span class="status-text">연결 중...</span>
            </div>
            <button class="btn" onclick="openFolderModal()">📁 폴더 선택</button>
            <button class="btn" onclick="toggleSidebar()">📂 파일 탐색</button>
        </div>
        <div class="header-right">
            <div class="layout-buttons" style="display:flex; gap:3px;">
                <button class="layout-btn active" data-layout="1" onclick="setLayout(1)" title="1개">
                    <svg width="18" height="14" viewBox="0 0 18 14"><rect x="1" y="1" width="16" height="12" rx="1" fill="currentColor"/></svg>
                </button>
                <button class="layout-btn" data-layout="2" onclick="setLayout(2)" title="2개 (가로)">
                    <svg width="18" height="14" viewBox="0 0 18 14"><rect x="1" y="1" width="7" height="12" rx="1" fill="currentColor"/><rect x="10" y="1" width="7" height="12" rx="1" fill="currentColor"/></svg>
                </button>
                <button class="layout-btn" data-layout="4" onclick="setLayout(4)" title="4개 (2x2)">
                    <svg width="18" height="14" viewBox="0 0 18 14"><rect x="1" y="1" width="7" height="5" rx="1" fill="currentColor"/><rect x="10" y="1" width="7" height="5" rx="1" fill="currentColor"/><rect x="1" y="8" width="7" height="5" rx="1" fill="currentColor"/><rect x="10" y="8" width="7" height="5" rx="1" fill="currentColor"/></svg>
                </button>
            </div>
            <select id="newAgentType" title="에이전트 타입">
                <option value="claude">🔵 Claude</option>
                <option value="gemini">🟢 Gemini</option>
                <option value="codex">🟠 Codex</option>
                <option value="opencode">🟣 OpenCode</option>
                <option value="shell">⚪ Shell</option>
            </select>
            <button class="btn primary" onclick="addAgent()">+ 터미널 추가</button>
            <button class="btn" onclick="restartServer()" title="서버 재시작" style="background:#e06c75;border-color:#e06c75;color:white;">🔄 서버 재시작</button>
            <button class="btn" onclick="clearAllSessions()" title="모든 세션 초기화">🗑️ 초기화</button>
        </div>
    </header>

    <div class="main">
        <aside class="sidebar" id="sidebar">
            <!-- 즐겨찾기 -->
            <div class="sidebar-section">
                <div class="sidebar-section-header" onclick="toggleSection('favorites')">
                    <span>⭐ 즐겨찾기</span>
                    <span class="toggle" id="favoritesToggle">▼</span>
                </div>
                <div class="sidebar-section-content" id="favoritesContent">
                    <div id="favoritesList"></div>
                </div>
            </div>

            <!-- 최근 프로젝트 -->
            <div class="sidebar-section">
                <div class="sidebar-section-header" onclick="toggleSection('recent')">
                    <span>🕐 최근 프로젝트</span>
                    <span class="toggle" id="recentToggle">▼</span>
                </div>
                <div class="sidebar-section-content" id="recentContent">
                    <div id="recentList"></div>
                </div>
            </div>

            <!-- 현재 폴더 / 파일 탐색기 -->
            <div class="sidebar-section" style="flex:1; display:flex; flex-direction:column; border-bottom:none;">
                <div class="sidebar-section-header" style="cursor:default; background: #252830;">
                    <span>📂 파일 탐색기</span>
                    <div style="display:flex; gap:4px;">
                        <button class="action-btn" onclick="goUpDirectory()" title="상위 폴더" style="font-size:12px;">⬆️</button>
                        <button class="action-btn" onclick="openFolderModal()" title="폴더 변경" style="font-size:12px;">📁</button>
                    </div>
                </div>
                <div style="padding: 6px 10px; font-size: 10px; background: #1e2127; border-bottom: 1px solid var(--border);">
                    <span id="workDirDisplay" style="color: #61afef; cursor: pointer; word-break: break-all;" onclick="openFolderModal()">폴더를 선택하세요...</span>
                </div>
                <div id="fileTree" style="flex:1; overflow-y: auto; padding: 4px;"></div>
            </div>
        </aside>

        <div class="terminal-area">
            <div class="project-tabs-bar" id="projectTabsBar">
                <!-- 동적으로 프로젝트 탭 생성 -->
                <button class="add-project-btn" onclick="openFolderModal()" title="새 프로젝트 추가">+</button>
            </div>
            <div id="gridsContainer" style="flex:1; display:flex; min-height:0;">
                <!-- 프로젝트별 grid가 여기에 동적 생성됨 -->
            </div>
        </div>
    </div>

    <!-- Folder Modal -->
    <div class="modal-overlay" id="folderModal">
        <div class="modal">
            <div class="modal-header">
                <h3>📁 작업 폴더 선택</h3>
                <button class="cell-btn" onclick="closeFolderModal()">✕</button>
            </div>
            <div class="modal-body">
                <div class="folder-path">
                    <button onclick="goToParent()">⬆️ 상위</button>
                    <span id="currentPath">My Computer</span>
                </div>
                <div class="folder-list" id="folderList"></div>
            </div>
            <div class="modal-footer">
                <button class="btn" onclick="closeFolderModal()">취소</button>
                <button class="btn primary" onclick="confirmFolder()">이 폴더 선택</button>
            </div>
        </div>
    </div>

    <!-- Agent Select Modal -->
    <div class="modal-overlay" id="agentSelectModal">
        <div class="modal" style="width: 400px;">
            <div class="modal-header">
                <h3>🤖 에이전트 선택</h3>
                <button class="cell-btn" onclick="closeAgentSelectModal()">✕</button>
            </div>
            <div class="modal-body">
                <p style="color:#abb2bf;font-size:12px;margin-bottom:12px;">첫 번째로 실행할 에이전트를 선택하세요:</p>
                <div class="agent-select-grid" id="agentSelectGrid"></div>
                <div style="margin-top:16px;">
                    <label style="font-size:11px;color:#abb2bf;">역할:</label>
                    <select id="agentSelectRole" style="width:100%;margin-top:4px;padding:8px;">
                        <option value="General">General - 범용</option>
                        <option value="PM">👑 PM - 프로젝트 매니저</option>
                        <option value="Dev">💻 Dev - 개발자</option>
                        <option value="QA">🛡️ QA - 품질 관리</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn" onclick="closeAgentSelectModal()">취소</button>
                <button class="btn primary" onclick="confirmAgentSelect()">시작</button>
            </div>
        </div>
    </div>

    <!-- Toast Container -->
    <div class="toast-container" id="toastContainer"></div>

    <!-- Maximize Overlay -->
    <div class="maximize-overlay" id="maximizeOverlay"></div>

    <script>
        // ========== Constants ==========
        const PROJECTS_KEY = 'agent-terminal-projects';
        const AGENT_CONFIG = {
            claude:   { icon: '🔵', name: 'Claude',   color: '#7aa2f7', multiInstance: true },
            gemini:   { icon: '🟢', name: 'Gemini',   color: '#9ece6a', multiInstance: false },  // No UUID session support
            codex:    { icon: '🟠', name: 'Codex',    color: '#ff9e64', multiInstance: false },  // No UUID session support
            opencode: { icon: '🟣', name: 'OpenCode', color: '#bb9af7', multiInstance: true },
            shell:    { icon: '⚪', name: 'Shell',    color: '#a9b1d6', multiInstance: true }
        };

        // ========== State (Multi-Project) ==========
        // 멀티 프로젝트 지원: 프로젝트별 터미널 분리
        const MAX_OPEN_PROJECTS = 5;
        let projects = {};  // { hash: { path, terminals[], layoutCols, gridEl } }
        let activeProjectHash = null;  // 현재 보이는 프로젝트

        // 하위 호환성을 위한 getter
        function getActiveTerminals() {
            if (!activeProjectHash || !projects[activeProjectHash]) return [];
            return projects[activeProjectHash].terminals;
        }
        function getWorkDir() {
            if (!activeProjectHash || !projects[activeProjectHash]) return null;
            return projects[activeProjectHash].path;
        }
        function getAllTerminals() {
            return Object.values(projects).flatMap(p => p.terminals);
        }

        // 기타 상태
        let browsingPath = 'drives';
        let parentPath = null;
        let serverStatus = 'disconnected';
        let healthCheckInterval = null;

        // 프로젝트 리스트 (즐겨찾기/최근)
        let favorites = [];
        let recentProjects = [];

        // ========== Project Hash & Storage ==========
        function hashPath(path) {
            // Simple hash function for project path
            let hash = 0;
            for (let i = 0; i < path.length; i++) {
                const char = path.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash; // Convert to 32bit integer
            }
            return Math.abs(hash).toString(36);
        }

        function getSessionKey(projectHash) {
            return projectHash ? `agent-terminal-state-${projectHash}` : 'agent-terminal-state-default';
        }

        function updateUrlWithProject(projectHash) {
            const url = new URL(window.location);
            if (projectHash) {
                url.searchParams.set('project', projectHash);
                // 마지막 프로젝트로 저장
                localStorage.setItem('agent-terminal-last-project', projectHash);
            } else {
                url.searchParams.delete('project');
            }
            window.history.replaceState({}, '', url);
        }

        function getLastProject() {
            return localStorage.getItem('agent-terminal-last-project');
        }

        function getProjectFromUrl() {
            const url = new URL(window.location);
            return url.searchParams.get('project');
        }

        // ========== Server Status Management ==========
        function updateServerStatus(status, text) {
            serverStatus = status;
            const el = document.getElementById('serverStatus');
            if (!el) return;
            el.className = 'server-status ' + status;
            el.querySelector('.status-text').textContent = text;
        }

        async function checkServerHealth() {
            try {
                const res = await fetch('/api/agents', { method: 'GET', signal: AbortSignal.timeout(3000) });
                if (res.ok) {
                    if (serverStatus !== 'connected') {
                        updateServerStatus('connected', '연결됨');
                        // 서버 재연결 시 모든 프로젝트의 터미널 재연결
                        const allTerminals = getAllTerminals();
                        if (allTerminals.length > 0) {
                            allTerminals.forEach(t => {
                                if (!t.ws || t.ws.readyState === WebSocket.CLOSED) {
                                    console.log(`[HealthCheck] Reconnecting terminal ${t.id}`);
                                    t.connect();
                                }
                            });
                        }
                    }
                    return true;
                }
            } catch (e) {
                if (serverStatus === 'connected') {
                    updateServerStatus('reconnecting', '재연결 중...');
                }
            }
            return false;
        }

        function startHealthCheck() {
            if (healthCheckInterval) clearInterval(healthCheckInterval);
            healthCheckInterval = setInterval(checkServerHealth, 2000);
            checkServerHealth(); // 즉시 실행
        }

        // 버전 정보 가져오기
        async function fetchVersion() {
            try {
                const res = await fetch('/api/version');
                if (res.ok) {
                    const data = await res.json();
                    document.getElementById('versionDisplay').textContent = 'v' + data.version;
                }
            } catch (e) {
                document.getElementById('versionDisplay').textContent = 'v?.?.?';
            }
        }

        // ========== Project List Management ==========
        function loadProjects() {
            try {
                const data = JSON.parse(localStorage.getItem(PROJECTS_KEY) || '{}');
                favorites = data.favorites || [];
                recentProjects = data.recent || [];
                console.log('[Projects] 로드됨:', { favorites: favorites.length, recent: recentProjects.length });
            } catch (e) {
                console.error('[Projects] 로드 오류:', e);
                favorites = [];
                recentProjects = [];
            }
            renderProjectLists();
        }

        function saveProjects() {
            const data = { favorites, recent: recentProjects };
            localStorage.setItem(PROJECTS_KEY, JSON.stringify(data));
            console.log('[Projects] 저장됨');
        }

        function addToRecent(path) {
            if (!path) return;
            // 이미 있으면 제거 후 맨 앞에 추가
            recentProjects = recentProjects.filter(p => p !== path);
            recentProjects.unshift(path);
            // 최대 10개 유지
            if (recentProjects.length > 10) recentProjects = recentProjects.slice(0, 10);
            saveProjects();
            renderProjectLists();
        }

        function toggleFavorite(path) {
            const idx = favorites.indexOf(path);
            if (idx >= 0) {
                favorites.splice(idx, 1);
                showToast('즐겨찾기에서 제거됨', 'info');
            } else {
                favorites.push(path);
                showToast('즐겨찾기에 추가됨', 'success');
            }
            saveProjects();
            renderProjectLists();
        }

        function removeFromRecent(path) {
            recentProjects = recentProjects.filter(p => p !== path);
            saveProjects();
            renderProjectLists();
        }

        function isFavorite(path) {
            return favorites.includes(path);
        }

        function getProjectName(path) {
            // 경로에서 폴더명만 추출
            return path.split(/[\\\\/]/).filter(Boolean).pop() || path;
        }

        function renderProjectLists() {
            const currentPath = getWorkDir();
            // 즐겨찾기 렌더링
            const favList = document.getElementById('favoritesList');
            if (favList) {
                if (favorites.length === 0) {
                    favList.innerHTML = '<div style="padding:8px 10px;color:#5c6370;font-size:10px;">즐겨찾기가 없습니다</div>';
                } else {
                    favList.innerHTML = favorites.map(path => {
                        const hash = hashPath(path);
                        const isOpen = !!projects[hash];
                        const isActive = path === currentPath;
                        return `
                        <div class="project-item ${isActive ? 'active' : ''}" onclick="openProject('${path.replace(/\\\\/g, '\\\\\\\\')}')">
                            <span class="icon">${isOpen ? '📂' : '⭐'}</span>
                            <span class="name" title="${path}">${getProjectName(path)}</span>
                            <div class="actions">
                                <button class="action-btn" onclick="event.stopPropagation();toggleFavorite('${path.replace(/\\\\/g, '\\\\\\\\')}')" title="즐겨찾기 해제">✕</button>
                            </div>
                        </div>
                    `}).join('');
                }
            }

            // 최근 프로젝트 렌더링
            const recentList = document.getElementById('recentList');
            if (recentList) {
                if (recentProjects.length === 0) {
                    recentList.innerHTML = '<div style="padding:8px 10px;color:#5c6370;font-size:10px;">최근 프로젝트가 없습니다</div>';
                } else {
                    recentList.innerHTML = recentProjects.map(path => {
                        const hash = hashPath(path);
                        const isOpen = !!projects[hash];
                        const isActive = path === currentPath;
                        return `
                        <div class="project-item ${isActive ? 'active' : ''}" onclick="openProject('${path.replace(/\\\\/g, '\\\\\\\\')}')">
                            <span class="icon">${isOpen ? '📂' : (isFavorite(path) ? '⭐' : '📁')}</span>
                            <span class="name" title="${path}">${getProjectName(path)}</span>
                            <div class="actions">
                                <button class="action-btn" onclick="event.stopPropagation();toggleFavorite('${path.replace(/\\\\/g, '\\\\\\\\')}')" title="${isFavorite(path) ? '즐겨찾기 해제' : '즐겨찾기 추가'}">${isFavorite(path) ? '★' : '☆'}</button>
                                <button class="action-btn" onclick="event.stopPropagation();removeFromRecent('${path.replace(/\\\\/g, '\\\\\\\\')}')" title="목록에서 제거">✕</button>
                            </div>
                        </div>
                    `}).join('');
                }
            }
        }

        // ========== Project Tab UI ==========
        function renderProjectTabs() {
            const tabsBar = document.getElementById('projectTabsBar');
            const addBtn = tabsBar.querySelector('.add-project-btn');

            // 기존 탭 제거 (+ 버튼 제외)
            tabsBar.querySelectorAll('.project-tab').forEach(t => t.remove());

            // 프로젝트 탭 생성
            Object.values(projects).forEach(project => {
                const tab = document.createElement('div');
                tab.className = `project-tab ${project.hash === activeProjectHash ? 'active' : ''}`;
                tab.dataset.projectHash = project.hash;
                tab.onclick = () => switchProject(project.hash);
                tab.innerHTML = `
                    <span class="tab-name" title="${project.path}">${getProjectName(project.path)}</span>
                    <span class="tab-count">${project.terminals.length}</span>
                    <button class="tab-close" onclick="event.stopPropagation();closeProject('${project.hash}')">&times;</button>
                `;
                tabsBar.insertBefore(tab, addBtn);
            });
        }

        function createProjectGrid(projectHash, layoutCols = 1) {
            const container = document.getElementById('gridsContainer');
            const grid = document.createElement('div');
            grid.id = `grid-${projectHash}`;
            grid.className = `grid cols-${layoutCols} project-grid`;
            grid.dataset.projectHash = projectHash;
            container.appendChild(grid);
            return grid;
        }

        // ========== Multi-Project Functions ==========
        function openProject(path, skipRestore = false) {
            const projectHash = hashPath(path);
            console.log(`[OpenProject] ${path} -> hash: ${projectHash}`);

            // 이미 열린 프로젝트면 전환만
            if (projects[projectHash]) {
                switchProject(projectHash);
                return;
            }

            // 최대 프로젝트 수 체크
            if (Object.keys(projects).length >= MAX_OPEN_PROJECTS) {
                showToast(`최대 ${MAX_OPEN_PROJECTS}개 프로젝트만 동시에 열 수 있습니다`, 'warning');
                return;
            }

            // 새 프로젝트 생성
            const gridEl = createProjectGrid(projectHash);
            projects[projectHash] = {
                hash: projectHash,
                path: path,
                terminals: [],
                layoutCols: 1,
                gridEl: gridEl
            };

            // 탭 렌더링 및 전환
            renderProjectTabs();
            switchProject(projectHash);
            addToRecent(path);

            // 저장된 상태 복원 시도
            if (!skipRestore) {
                const restored = restoreProjectSession(projectHash);
                if (restored) {
                    showToast(`프로젝트 복원됨: ${getProjectName(path)}`, 'success');
                    return;
                }
            }

            // 복원 실패면 에이전트 선택
            openAgentSelectModal();
            showToast(`프로젝트 열림: ${getProjectName(path)}`, 'success');
        }

        function switchProject(projectHash) {
            if (!projects[projectHash]) return;

            // 현재 프로젝트 숨기기
            if (activeProjectHash && projects[activeProjectHash]) {
                const oldGrid = projects[activeProjectHash].gridEl;
                if (oldGrid) oldGrid.classList.remove('active');
            }

            // 새 프로젝트 표시
            activeProjectHash = projectHash;
            const project = projects[projectHash];
            project.gridEl.classList.add('active');

            // UI 업데이트
            document.getElementById('workDirDisplay').textContent = project.path;
            loadFileTree(project.path);
            updateUrlWithProject(projectHash);
            updateLayoutButtons(project.layoutCols);

            // 탭 상태 업데이트
            document.querySelectorAll('.project-tab').forEach(tab => {
                tab.classList.toggle('active', tab.dataset.projectHash === projectHash);
            });

            // 터미널 fit
            setTimeout(() => {
                project.terminals.forEach(t => t.fitAddon?.fit());
            }, 100);

            renderProjectLists();
            console.log(`[SwitchProject] -> ${getProjectName(project.path)}`);
        }

        function closeProject(projectHash) {
            const project = projects[projectHash];
            if (!project) return;

            // 터미널 dispose
            project.terminals.forEach(t => t.dispose());

            // Grid 제거
            project.gridEl.remove();

            // localStorage에서 제거
            localStorage.removeItem(getSessionKey(projectHash));

            // 프로젝트 목록에서 제거
            delete projects[projectHash];

            console.log(`[CloseProject] ${getProjectName(project.path)}`);

            // 다른 프로젝트로 전환 또는 폴더 선택 모달
            const remaining = Object.keys(projects);
            if (remaining.length > 0) {
                switchProject(remaining[0]);
            } else {
                activeProjectHash = null;
                document.getElementById('workDirDisplay').textContent = '폴더를 선택하세요...';
                document.getElementById('fileTree').innerHTML = '';
                setTimeout(openFolderModal, 300);
            }

            renderProjectTabs();
            renderProjectLists();
            saveOpenProjectsList();
        }

        function updateLayoutButtons(cols) {
            document.querySelectorAll('.layout-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.layout == cols);
            });
        }

        function toggleSection(section) {
            const content = document.getElementById(section + 'Content');
            const toggle = document.getElementById(section + 'Toggle');
            if (content && toggle) {
                content.classList.toggle('collapsed');
                toggle.textContent = content.classList.contains('collapsed') ? '▶' : '▼';
            }
        }

        // ========== Unique ID ==========
        function generateId() {
            return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
        }

        function generateUUID() {
            // Generate valid UUID v4 for CLI session IDs
            return crypto.randomUUID();
        }

        // 기존 세션 ID가 UUID 형식인지 확인
        function isValidUUID(str) {
            if (!str) return false;
            const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
            return uuidRegex.test(str);
        }

        // 세션 ID 마이그레이션 - 유효한 UUID면 유지 (세션 연속성)
        // 충돌 시 session conflict detection이 새 UUID 생성
        function migrateSessionId(oldId) {
            if (isValidUUID(oldId)) {
                console.log(`[Session] 기존 UUID 복원: ${oldId}`);
                return oldId;  // 기존 UUID 유지 → 세션 연속성
            }
            // 유효하지 않은 ID면 새 UUID 생성
            const newId = generateUUID();
            console.log(`[Session] 새 UUID 생성: ${newId} (이전: ${oldId || 'none'})`);
            return newId;
        }

        // ========== Toast ==========
        function showToast(msg, type = 'info') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = msg;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }

        // ========== Session Persistence (Multi-Project) ==========
        function saveState() {
            if (!activeProjectHash || !projects[activeProjectHash]) return;
            const project = projects[activeProjectHash];
            const state = {
                workDir: project.path,
                layoutCols: project.layoutCols,
                terminals: project.terminals.map(t => ({
                    id: t.id,
                    type: t.type,
                    role: t.role,
                    sessionId: t.sessionId,
                    targetId: t.targetId || null
                }))
            };
            const key = getSessionKey(activeProjectHash);
            localStorage.setItem(key, JSON.stringify(state));
            console.log(`[SaveState] 저장됨 (${key})`);
            saveOpenProjectsList();
        }

        function saveOpenProjectsList() {
            const openList = Object.values(projects).map(p => ({
                hash: p.hash,
                path: p.path
            }));
            localStorage.setItem('agent-terminal-open-projects', JSON.stringify({
                projects: openList,
                activeHash: activeProjectHash
            }));
        }

        function loadOpenProjectsList() {
            try {
                const raw = localStorage.getItem('agent-terminal-open-projects');
                if (!raw) return null;
                return JSON.parse(raw);
            } catch(e) {
                return null;
            }
        }

        function loadState(projectHash) {
            try {
                const key = getSessionKey(projectHash);
                const raw = localStorage.getItem(key);
                if (!raw) return null;
                const state = JSON.parse(raw);
                console.log(`[LoadState] 로드됨 (${key})`);
                return state;
            } catch(e) {
                console.error('[LoadState] 오류:', e);
                return null;
            }
        }

        function restoreProjectSession(projectHash) {
            console.log(`[RestoreProjectSession] 시작 (project: ${projectHash})`);
            const state = loadState(projectHash);
            const project = projects[projectHash];

            if (!state || !project) {
                console.log('[RestoreProjectSession] 저장된 상태 없음');
                return false;
            }

            // 레이아웃 복원
            project.layoutCols = state.layoutCols || 1;
            const isActive = projectHash === activeProjectHash;
            project.gridEl.className = `grid cols-${project.layoutCols} project-grid${isActive ? ' active' : ''}`;
            if (isActive) {
                updateLayoutButtons(project.layoutCols);
            }

            // 터미널 복원 (명시적으로 projectHash 전달)
            if (state.terminals && state.terminals.length > 0) {
                console.log(`[RestoreProjectSession] ${state.terminals.length}개 터미널 복원 (project: ${projectHash})`);
                state.terminals.forEach((saved, idx) => {
                    const migratedSessionId = migrateSessionId(saved.sessionId);
                    createTerminal(saved.type, saved.role, saved.id, migratedSessionId, saved.targetId, projectHash);
                });

                // 라우팅 복원
                setTimeout(() => {
                    refreshRouterOptions();
                    state.terminals.forEach(saved => {
                        if (saved.targetId) {
                            const t = project.terminals.find(x => x.id === saved.id);
                            if (t) {
                                t.targetId = saved.targetId;
                                const select = t.el.querySelector(`[data-router-for="${t.id}"]`);
                                if (select) select.value = saved.targetId;
                            }
                        }
                    });
                }, 100);

                renderProjectTabs();

                // 터미널 개수에 맞춰 레이아웃 자동 조정
                const terminalCount = project.terminals.length;
                let correctLayout;
                if (terminalCount === 1) {
                    correctLayout = 1;
                } else if (terminalCount === 2) {
                    correctLayout = 2;
                } else {
                    correctLayout = 4;  // 3-4개: 2x2 그리드
                }
                project.layoutCols = correctLayout;
                project.gridEl.className = `grid cols-${correctLayout} project-grid${isActive ? ' active' : ''}`;

                if (isActive) {
                    updateLayoutButtons(correctLayout);
                    setTimeout(fitAll, 100);
                }

                return true;
            }
            return false;
        }

        // ========== Agent Select Modal ==========
        let selectedAgentType = 'claude';

        function openAgentSelectModal() {
            const modal = document.getElementById('agentSelectModal');
            const grid = document.getElementById('agentSelectGrid');

            // 에이전트 그리드 생성
            grid.innerHTML = Object.entries(AGENT_CONFIG).map(([key, cfg]) => `
                <div class="agent-select-item ${key === selectedAgentType ? 'selected' : ''}"
                     onclick="selectAgentType('${key}')" data-agent="${key}">
                    <span class="icon">${cfg.icon}</span>
                    <span class="name">${cfg.name}</span>
                </div>
            `).join('');

            modal.classList.add('show');
        }

        function closeAgentSelectModal() {
            document.getElementById('agentSelectModal').classList.remove('show');
        }

        function selectAgentType(type) {
            selectedAgentType = type;
            document.querySelectorAll('.agent-select-item').forEach(el => {
                el.classList.toggle('selected', el.dataset.agent === type);
            });
        }

        function confirmAgentSelect() {
            const role = document.getElementById('agentSelectRole').value;
            const cfg = AGENT_CONFIG[selectedAgentType];
            const terminals = getActiveTerminals();

            // 단일 인스턴스 에이전트 중복 체크
            if (!cfg.multiInstance) {
                const existing = terminals.find(t => t.type === selectedAgentType);
                if (existing) {
                    showToast(`${cfg.icon} ${cfg.name}은(는) 하나만 실행 가능합니다`, 'warning');
                    return;
                }
            }

            closeAgentSelectModal();
            createTerminal(selectedAgentType, role);
            saveState();
            showToast(`${cfg.icon} ${cfg.name} 터미널 시작`, 'success');
        }

        // ========== Folder Modal ==========
        function openFolderModal() {
            document.getElementById('folderModal').classList.add('show');
            browsingPath = 'drives';
            loadFolderList('drives');
        }

        function closeFolderModal() {
            document.getElementById('folderModal').classList.remove('show');
        }

        async function loadFolderList(path) {
            try {
                const res = await fetch(`/api/folders?path=${encodeURIComponent(path)}`);
                const data = await res.json();

                browsingPath = data.current || path;
                parentPath = data.parent || null;
                document.getElementById('currentPath').textContent = data.current || 'My Computer';

                const list = document.getElementById('folderList');
                list.innerHTML = data.folders.map(f => `
                    <div class="folder-item" onclick="loadFolderList('${f.path.replace(/\\\\/g, '\\\\\\\\')}')">
                        <span class="icon">${f.is_drive ? '💾' : '📁'}</span>
                        <span>${f.name}</span>
                    </div>
                `).join('') || '<div style="color:#666;padding:20px;text-align:center;">No folders</div>';
            } catch (e) {
                showToast('Failed to load folders', 'error');
            }
        }

        function goToParent() {
            if (parentPath) loadFolderList(parentPath);
        }

        function confirmFolder() {
            if (browsingPath === 'drives') {
                showToast('폴더를 선택해주세요', 'warning');
                return;
            }
            closeFolderModal();
            openProject(browsingPath);
        }

        // ========== UI Helpers ==========
        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('hidden');
            setTimeout(fitAll, 200);
        }

        async function loadFileTree(path) {
            try {
                const res = await fetch(`/api/files?path=${encodeURIComponent(path)}`);
                const data = await res.json();
                currentFileTreePath = data.path;  // 현재 경로 저장
                document.getElementById('workDirDisplay').textContent = data.path;
                const tree = document.getElementById('fileTree');
                tree.innerHTML = data.items.map(i => `
                    <div class="file-item ${i.is_dir ? 'dir' : ''}"
                         onclick="${i.is_dir
                             ? `loadFileTree('${i.path.replace(/\\\\/g, '\\\\\\\\')}')`
                             : `sendFileToTerminal('${i.path.replace(/\\\\/g, '\\\\\\\\')}')`}">
                        <span class="file-icon">${i.is_dir ? '📂' : getFileIcon(i.name)}</span>
                        <span class="file-name">${i.name}</span>
                        <div class="file-actions">
                            ${!i.is_dir ? `<button class="action-btn" onclick="event.stopPropagation();copyFilePath('${i.path.replace(/\\\\/g, '\\\\\\\\')}')" title="경로 복사">📋</button>` : ''}
                        </div>
                    </div>
                `).join('');
            } catch (e) {}
        }

        function getFileIcon(filename) {
            const ext = filename.split('.').pop().toLowerCase();
            const icons = {
                'py': '🐍', 'js': '📜', 'ts': '📘', 'json': '📋', 'md': '📝',
                'html': '🌐', 'css': '🎨', 'txt': '📄', 'yml': '⚙️', 'yaml': '⚙️',
                'sh': '⚡', 'bat': '⚡', 'exe': '⚙️', 'png': '🖼️', 'jpg': '🖼️',
                'gif': '🖼️', 'svg': '🖼️', 'pdf': '📕', 'zip': '📦', 'gz': '📦'
            };
            return icons[ext] || '📄';
        }

        let currentFileTreePath = null;

        function goUpDirectory() {
            if (!currentFileTreePath) return;
            // Get parent directory
            const parts = currentFileTreePath.replace(/\\\\/g, '/').split('/').filter(Boolean);
            if (parts.length <= 1) {
                // At root (e.g., "D:")
                showToast('최상위 폴더입니다', 'info');
                return;
            }
            parts.pop();
            const parentPath = parts.join('/').replace(/\\//g, '\\\\');
            // Handle Windows drive letters
            const newPath = parts.length === 1 && parts[0].includes(':')
                ? parts[0] + '\\\\'
                : parentPath;
            loadFileTree(newPath);
        }

        function sendFileToTerminal(filePath) {
            // 활성 터미널에 파일 경로 전달
            const terminals = getActiveTerminals();
            const activeTerminal = terminals.find(t => t.ws?.readyState === WebSocket.OPEN);
            if (activeTerminal) {
                const fileName = filePath.split(/[\\\\/]/).pop();
                activeTerminal.ws.send(JSON.stringify({
                    type: 'input',
                    data: filePath
                }));
                showToast(`파일 경로 전송: ${fileName}`, 'success');
            } else {
                showToast('연결된 터미널이 없습니다', 'warning');
            }
        }

        function copyFilePath(filePath) {
            navigator.clipboard.writeText(filePath).then(() => {
                showToast('경로가 복사되었습니다', 'success');
            }).catch(() => {
                showToast('복사 실패', 'error');
            });
        }

        function setLayout(n) {
            if (!activeProjectHash || !projects[activeProjectHash]) return;
            const project = projects[activeProjectHash];
            project.layoutCols = parseInt(n);
            project.gridEl.className = `grid cols-${n} project-grid active`;
            updateLayoutButtons(n);
            setTimeout(fitAll, 100);
            saveState();
        }

        // 터미널 개수에 따른 레이아웃 & 버튼 자동 동기화
        function autoUpdateLayout() {
            if (!activeProjectHash || !projects[activeProjectHash]) return;
            const n = projects[activeProjectHash].terminals.length;
            let layout;
            if (n === 1) {
                layout = 1;  // 전체 화면
            } else if (n === 2) {
                layout = 2;  // 가로 2분할
            } else {
                layout = 4;  // 3-4개: 2x2 그리드 (최대)
            }
            setLayout(layout);
        }

        // ========== Terminal Class ==========
        class AgentTerminal {
            constructor(type, role, id, sessionId, projectHash = null) {
                this.id = id || generateId();
                this.type = type;
                this.role = role;
                // 명시적으로 전달된 projectHash 사용, 없으면 activeProjectHash 폴백
                this.projectHash = projectHash || activeProjectHash;
                this.sessionId = sessionId || generateUUID();
                this.ws = null;
                this.term = null;
                this.fitAddon = null;
                this.resizeObserver = null;  // ResizeObserver 인스턴스 저장
                // 메시지 배칭용 (성능 최적화)
                this.messageQueue = [];
                this.rafId = null;

                this.el = document.createElement('div');
                this.el.className = 'cell';
                this.el.dataset.terminalId = this.id;
                this.render();

                // 프로젝트 grid에 추가 (명시적 projectHash 사용)
                const project = projects[this.projectHash];
                if (project && project.gridEl) {
                    project.gridEl.appendChild(this.el);
                }
                this.initXterm();
            }

            render() {
                const cfg = AGENT_CONFIG[this.type] || AGENT_CONFIG.shell;
                const terminals = getActiveTerminals();
                const termNum = terminals.indexOf(this) + 1 || terminals.length + 1;
                this.el.innerHTML = `
                    <div class="cell-toolbar" style="border-left: 3px solid ${cfg.color};">
                        <span class="term-number" style="color: ${cfg.color}; font-weight: bold; margin-right: 4px;">#${termNum}</span>
                        <span class="agent-icon">${cfg.icon}</span>
                        <span class="agent-name">${cfg.name}</span>
                        <select class="role-select" data-role-for="${this.id}" title="역할 변경">
                            <option value="General" ${this.role === 'General' ? 'selected' : ''}>General</option>
                            <option value="PM" ${this.role === 'PM' ? 'selected' : ''}>👑 PM</option>
                            <option value="Dev" ${this.role === 'Dev' ? 'selected' : ''}>💻 Dev</option>
                            <option value="QA" ${this.role === 'QA' ? 'selected' : ''}>🛡️ QA</option>
                        </select>
                        <div class="cell-actions">
                            <select data-router-for="${this.id}" title="출력 라우팅 대상">
                                <option value="">📡 라우팅 없음</option>
                            </select>
                            <div class="status-dot" data-dot-for="${this.id}" title="연결 상태"></div>
                            <button class="cell-btn" data-maximize-btn onclick="toggleMaximize('${this.id}')" title="최대화">⤢</button>
                            <button class="cell-btn" onclick="restartTerminal('${this.id}')" title="터미널 재연결">↻</button>
                            <button class="cell-btn" onclick="removeAgent('${this.id}')" title="터미널 닫기">✕</button>
                        </div>
                    </div>
                    <div class="term-container" data-container-for="${this.id}"></div>
                `;

                // Role change binding
                const roleSelect = this.el.querySelector(`[data-role-for="${this.id}"]`);
                roleSelect.onchange = () => {
                    this.role = roleSelect.value;
                    this.term?.write(`\\r\\n\\x1b[33m[역할 변경: ${this.role}]\\x1b[0m\\r\\n`);
                    saveState();
                };

                // Router binding
                const routerSelect = this.el.querySelector(`[data-router-for="${this.id}"]`);
                routerSelect.onchange = () => this.routeTo(routerSelect.value);
            }

            initXterm() {
                const container = this.el.querySelector(`[data-container-for="${this.id}"]`);
                const cfg = AGENT_CONFIG[this.type] || AGENT_CONFIG.shell;

                this.term = new Terminal({
                    fontFamily: 'Consolas, Monaco, monospace',
                    fontSize: 13,
                    cursorBlink: false,
                    theme: {
                        background: '#1a1b26',
                        foreground: '#c0caf5',
                        cursor: cfg.color,
                        selection: 'rgba(122, 162, 247, 0.3)'
                    }
                });

                this.fitAddon = new FitAddon.FitAddon();
                this.term.loadAddon(this.fitAddon);
                this.term.loadAddon(new WebLinksAddon.WebLinksAddon());
                this.term.open(container);
                this.fitAddon.fit();

                // Input handler
                this.term.onData(data => {
                    if (this.ws?.readyState === WebSocket.OPEN) {
                        this.ws.send(JSON.stringify({ type: 'input', data }));
                    }
                });

                // Clipboard paste (Ctrl+V) - images and text
                this.term.attachCustomKeyEventHandler((e) => {
                    if (e.type === 'keydown' && (e.ctrlKey || e.metaKey) && e.key === 'v') {
                        this.handlePaste();
                        return false;
                    }
                    return true;
                });

                // Resize observer with debounce (저장하여 dispose 시 해제)
                let resizeTimeout = null;
                let fitTimeout = null;
                this.resizeObserver = new ResizeObserver(() => {
                    // Debounce fit() calls too
                    if (fitTimeout) clearTimeout(fitTimeout);
                    fitTimeout = setTimeout(() => this.fitAddon?.fit(), 50);
                    // Debounce resize events to prevent duplicate Claude UI renders
                    if (resizeTimeout) clearTimeout(resizeTimeout);
                    resizeTimeout = setTimeout(() => {
                        if (this.ws?.readyState === WebSocket.OPEN && this.term) {
                            this.ws.send(JSON.stringify({
                                type: 'resize',
                                rows: this.term.rows,
                                cols: this.term.cols
                            }));
                        }
                    }, 500);
                });
                this.resizeObserver.observe(container);

                if (getWorkDir()) this.connect();
            }

            async handlePaste() {
                try {
                    const items = await navigator.clipboard.read();
                    for (const item of items) {
                        // Check for image first
                        for (const type of item.types) {
                            if (type.startsWith('image/')) {
                                const blob = await item.getType(type);
                                const reader = new FileReader();
                                reader.onload = () => {
                                    if (this.ws?.readyState === WebSocket.OPEN) {
                                        this.ws.send(JSON.stringify({
                                            type: 'image',
                                            data: reader.result,
                                            filename: `clipboard-${Date.now()}.png`
                                        }));
                                        this.term.write('\\r\\n\\x1b[36m[Image pasted]\\x1b[0m\\r\\n');
                                    }
                                };
                                reader.readAsDataURL(blob);
                                return;
                            }
                        }
                    }
                    // No image - try text
                    const text = await navigator.clipboard.readText();
                    if (text) this.term.paste(text);
                } catch {
                    // Fallback to text only
                    try {
                        const text = await navigator.clipboard.readText();
                        if (text) this.term.paste(text);
                    } catch {}
                }
            }

            connect() {
                // 이미 연결 중이거나 열려있으면 무시
                if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
                    console.log(`[Terminal ${this.id}] Already connected/connecting, skip`);
                    return;
                }
                if (this.ws) this.ws.close();

                // 터미널이 속한 프로젝트의 workDir 사용
                const project = projects[this.projectHash];
                const workDir = project ? project.path : getWorkDir();
                if (!workDir) return;

                const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
                const terminals = project ? project.terminals : getActiveTerminals();
                const idx = terminals.indexOf(this);
                const cfg = AGENT_CONFIG[this.type] || AGENT_CONFIG.shell;

                this.ws = new WebSocket(
                    `${protocol}//${location.host}/ws/terminal/${this.sessionId}?workdir=${encodeURIComponent(workDir)}&agent=${this.type}&role=${this.role}&index=${idx}`
                );

                this.ws.onopen = () => {
                    const dot = this.el.querySelector(`[data-dot-for="${this.id}"]`);
                    if (dot) dot.classList.add('live');

                    // Only reset reconnect attempts after connection is stable (5 seconds)
                    this.stableConnectionTimer = setTimeout(() => {
                        if (this.ws?.readyState === WebSocket.OPEN) {
                            this.reconnectAttempts = 0;
                            console.log(`[Terminal ${this.id}] Connection stable, reset retry counter`);
                        }
                    }, 5000);

                    // Initial resize handled by ResizeObserver with debounce
                };

                this.ws.onmessage = (e) => {
                    // dispose 후 메시지 무시
                    if (this.disposed) return;
                    const msg = JSON.parse(e.data);
                    switch (msg.type) {
                        case 'terminal_output':
                            // Append to buffer for split message detection
                            if (!this.outputBuffer) this.outputBuffer = '';
                            this.outputBuffer += msg.data;
                            // Keep buffer size reasonable (last 2000 chars)
                            if (this.outputBuffer.length > 2000) {
                                this.outputBuffer = this.outputBuffer.slice(-1000);
                            }

                            // Optimization: Only run expensive conflict check on small packets
                            if (msg.data.length < 4096) {
                                // Check for "Session ID already in use" error (Claude CLI specific)
                                // Use comprehensive ANSI stripping (all escape sequences, not just colors)
                                const stripAnsi = (s) => s.replace(/\\x1b\\[[^a-zA-Z]*[a-zA-Z]/g, '')
                                                           .replace(/\\x1b\\][^\\x07]*\\x07/g, '')
                                                           .replace(/[\\x00-\\x1f]/g, ' ');
                                const plainText = stripAnsi(msg.data);
                                const bufferText = stripAnsi(this.outputBuffer);

                                // Debug: log incoming data for session conflict troubleshooting
                                if (msg.data.toLowerCase().includes('session') || msg.data.toLowerCase().includes('error')) {
                                    console.log('[Terminal] Checking msg:', JSON.stringify(msg.data.slice(0, 200)));
                                    console.log('[Terminal] Plain text:', plainText.slice(0, 200));
                                }

                                // Use case-insensitive regex for robust detection
                                const conflictPattern = /already\\s+in\\s+use/i;
                                if (conflictPattern.test(plainText) || conflictPattern.test(bufferText) ||
                                    conflictPattern.test(msg.data) || conflictPattern.test(this.outputBuffer)) {
                                    console.log('[Terminal] Session conflict detected! Old:', this.sessionId);
                                    this.term.write(msg.data);  // Show error
                                    this.term.write('\\r\\n\\x1b[33m[세션 충돌 감지 - 새 세션 생성 중...]\\x1b[0m\\r\\n');

                                    // Set flag FIRST to prevent auto-reconnect from onclose
                                    this.handlingSessionConflict = true;

                                    // Close current connection cleanly
                                    if (this.ws) {
                                        this.ws.onclose = null;  // Prevent onclose handler
                                        this.ws.close();
                                    }

                                    // Generate new session ID
                                    this.sessionId = generateUUID();
                                    console.log('[Terminal] New session ID:', this.sessionId);
                                    this.outputBuffer = '';  // Clear buffer
                                    saveState();

                                    // Reconnect with new session after delay
                                    setTimeout(() => {
                                        this.handlingSessionConflict = false;
                                        this.reconnectAttempts = 0;
                                        this.connect();
                                    }, 1500);
                                    return;
                                }
                            }
                            // 메시지 큐에 추가 (배칭)
                            this.messageQueue.push(msg.data);
                            // RAF가 없으면 예약
                            if (!this.rafId) {
                                this.rafId = requestAnimationFrame(() => {
                                    try {
                                        // 큐에 있는 모든 메시지 일괄 처리
                                        if (this.messageQueue.length > 0 && this.term && !this.disposed) {
                                            const combined = this.messageQueue.join('');
                                            this.term.write(combined);
                                            // 라우팅도 일괄 처리
                                            if (this.targetId) this.sendToTarget(combined);
                                        }
                                    } catch (e) {
                                        console.error('[Terminal] Error in message batch:', e);
                                    } finally {
                                        this.messageQueue = [];
                                        this.rafId = null;
                                    }
                                });
                            }
                            break;
                        case 'terminal_started':
                            this.term.write(`\\r\\n\\x1b[38;2;${this.hexToRgb(cfg.color)}m${cfg.icon} ${cfg.name} 준비 완료\\x1b[0m\\r\\n`);
                            this.term.write(`\\x1b[90m역할: ${this.role} | 작업폴더: ${workDir}\\x1b[0m\\r\\n\\r\\n`);
                            break;
                        case 'inject_input':
                            this.term.write(msg.data);
                            this.ws.send(JSON.stringify({ type: 'input', data: msg.data }));
                            break;
                        case 'image_added':
                            this.term.write(`\\r\\n\\x1b[36m[Image: ${msg.filename}]\\x1b[0m\\r\\n`);
                            break;
                        case 'terminal_closed':
                            this.term.write(`\\r\\n\\x1b[33m[터미널 프로세스 종료됨]\\x1b[0m\\r\\n`);
                            const dot = this.el.querySelector(`[data-dot-for="${this.id}"]`);
                            if (dot) {
                                dot.classList.remove('live');
                                dot.style.background = '#e06c75';  // 빨간색으로 종료 표시
                            }
                            break;
                        case 'error':
                            this.term.write(`\\r\\n\\x1b[31m${msg.message}\\x1b[0m\\r\\n`);
                            break;
                    }
                };

                this.ws.onclose = () => {
                    const dot = this.el.querySelector(`[data-dot-for="${this.id}"]`);
                    if (dot) dot.classList.remove('live');

                    // 연결 끊김 시 메시지 큐 정리
                    if (this.messageQueue.length > 0) {
                        console.log(`[Terminal ${this.id}] Dropped ${this.messageQueue.length} queued messages`);
                        this.messageQueue = [];
                    }

                    // Clear stable connection timer
                    if (this.stableConnectionTimer) {
                        clearTimeout(this.stableConnectionTimer);
                        this.stableConnectionTimer = null;
                    }

                    // Skip auto-reconnect if handling session conflict (we'll reconnect ourselves)
                    if (this.handlingSessionConflict) {
                        console.log('[Terminal] Skipping auto-reconnect (handling session conflict)');
                        return;
                    }

                    // Auto-reconnect with retry limit (max 3 attempts)
                    if (workDir && !this.disposed) {
                        this.reconnectAttempts = (this.reconnectAttempts || 0) + 1;
                        const maxRetries = 3;

                        console.log(`[Terminal ${this.id}] Connection closed, attempt ${this.reconnectAttempts}/${maxRetries}`);

                        if (this.reconnectAttempts <= maxRetries) {
                            this.term?.write(`\\r\\n\\x1b[33m[연결 끊김 - 재연결 시도 ${this.reconnectAttempts}/${maxRetries}...]\\x1b[0m\\r\\n`);
                            this.reconnectTimeout = setTimeout(() => {
                                if (!this.disposed) {
                                    this.connect();
                                }
                            }, 3000);
                        } else {
                            this.term?.write('\\r\\n\\x1b[31m[재연결 실패 - ↻ 버튼으로 수동 재연결하세요]\\x1b[0m\\r\\n');
                            // Don't reset - user must click manually
                        }
                    }
                };

                this.ws.onerror = () => {
                    this.term?.write('\\r\\n\\x1b[31m[Connection error]\\x1b[0m\\r\\n');
                };
            }

            hexToRgb(hex) {
                const r = parseInt(hex.slice(1,3), 16);
                const g = parseInt(hex.slice(3,5), 16);
                const b = parseInt(hex.slice(5,7), 16);
                return `${r};${g};${b}`;
            }

            routeTo(targetId) {
                this.targetId = targetId || null;
                const terminals = getActiveTerminals();
                if (targetId) {
                    const target = terminals.find(t => t.id === targetId);
                    if (target) {
                        const cfg = AGENT_CONFIG[target.type] || AGENT_CONFIG.shell;
                        const targetNum = terminals.indexOf(target) + 1;
                        this.term.write(`\\r\\n\\x1b[36m[출력 라우팅: #${targetNum} ${cfg.icon} ${cfg.name} (${target.role})로 전송]\\x1b[0m\\r\\n`);
                    }
                } else {
                    this.term.write(`\\r\\n\\x1b[36m[출력 라우팅 해제]\\x1b[0m\\r\\n`);
                }
                saveState();
            }

            sendToTarget(data) {
                const terminals = getActiveTerminals();
                const target = terminals.find(t => t.id === this.targetId);
                if (target?.ws?.readyState === WebSocket.OPEN) {
                    const cfg = AGENT_CONFIG[this.type] || AGENT_CONFIG.shell;
                    const myNum = terminals.indexOf(this) + 1;
                    target.ws.send(JSON.stringify({
                        type: 'input',
                        data: `\\n[#${myNum} ${cfg.name}]: ${data.replace(/\\x1b\\[[0-9;]*m/g, '').trim()}\\n`
                    }));
                }
            }

            dispose() {
                this.disposed = true;
                if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
                if (this.stableConnectionTimer) clearTimeout(this.stableConnectionTimer);
                if (this.rafId) cancelAnimationFrame(this.rafId);
                this.messageQueue = [];
                if (this.resizeObserver) this.resizeObserver.disconnect();
                if (this.ws) this.ws.close();
                if (this.term) this.term.dispose();
            }
        }

        // ========== Maximize/Minimize ==========
        let maximizedTerminalId = null;

        function toggleMaximize(terminalId) {
            const terminals = getActiveTerminals();
            const t = terminals.find(t => t.id === terminalId);
            if (!t) return;

            const btn = t.el.querySelector('[data-maximize-btn]');

            if (maximizedTerminalId === terminalId) {
                // Minimize
                t.el.classList.remove('maximized');
                document.getElementById('maximizeOverlay').classList.remove('show');
                maximizedTerminalId = null;
                if (btn) { btn.textContent = '⤢'; btn.title = 'Maximize'; }
                setTimeout(fitAll, 100);
            } else {
                // First minimize any other
                if (maximizedTerminalId) {
                    const prev = terminals.find(t => t.id === maximizedTerminalId);
                    if (prev) {
                        prev.el.classList.remove('maximized');
                        const prevBtn = prev.el.querySelector('[data-maximize-btn]');
                        if (prevBtn) { prevBtn.textContent = '⤢'; prevBtn.title = 'Maximize'; }
                    }
                }
                // Maximize this one
                t.el.classList.add('maximized');
                document.getElementById('maximizeOverlay').classList.add('show');
                maximizedTerminalId = terminalId;
                if (btn) { btn.textContent = '⤡'; btn.title = 'Minimize'; }
                setTimeout(() => {
                    t.fitAddon?.fit();
                    t.term?.focus();
                }, 100);
            }
        }

        // ========== Terminal Management ==========
        function createTerminal(type, role, id, sessionId, targetId = null, projectHash = null) {
            // projectHash가 명시되지 않으면 activeProjectHash 사용
            const targetProjectHash = projectHash || activeProjectHash;
            const t = new AgentTerminal(type, role, id, sessionId, targetProjectHash);
            if (targetId) t.targetId = targetId;
            // 해당 프로젝트에 터미널 추가
            if (targetProjectHash && projects[targetProjectHash]) {
                projects[targetProjectHash].terminals.push(t);
            }
            refreshRouterOptions();
            renderProjectTabs();  // 탭 카운트 업데이트
            return t;
        }

        function addAgent() {
            if (!getWorkDir()) {
                openFolderModal();
                showToast('먼저 작업 폴더를 선택해주세요', 'warning');
                return;
            }
            const terminals = getActiveTerminals();
            if (terminals.length >= 4) {
                showToast('최대 4개의 터미널까지만 가능합니다', 'warning');
                return;
            }
            const type = document.getElementById('newAgentType').value;
            const role = 'General';
            const cfg = AGENT_CONFIG[type];

            // 단일 인스턴스 에이전트 중복 체크
            if (!cfg.multiInstance) {
                const existing = terminals.find(t => t.type === type);
                if (existing) {
                    showToast(`${cfg.icon} ${cfg.name}은(는) 하나만 실행 가능합니다 (독립 세션 미지원)`, 'warning');
                    return;
                }
            }

            createTerminal(type, role);
            autoUpdateLayout();  // 터미널 개수에 맞게 레이아웃 자동 동기화
            showToast(`${cfg.icon} ${cfg.name} (${role}) 터미널 추가됨`, 'success');
        }

        function removeAgent(terminalId) {
            if (!activeProjectHash || !projects[activeProjectHash]) return;
            const project = projects[activeProjectHash];

            if (project.terminals.length <= 1) {
                showToast('최소 1개의 터미널은 유지해야 합니다', 'warning');
                return;
            }

            const idx = project.terminals.findIndex(t => t.id === terminalId);
            if (idx === -1) return;

            project.terminals[idx].dispose();
            project.terminals.splice(idx, 1);

            const el = document.querySelector(`[data-terminal-id="${terminalId}"]`);
            if (el) el.remove();

            refreshRouterOptions();
            renderProjectTabs();  // 탭 카운트 업데이트
            autoUpdateLayout();  // 터미널 개수에 맞게 레이아웃 자동 동기화
            fitAll();
        }

        function restartTerminal(terminalId) {
            const terminals = getActiveTerminals();
            const t = terminals.find(t => t.id === terminalId);
            if (t) {
                t.reconnectAttempts = 0;
                t.term?.write('\\r\\n\\x1b[33m[수동 재연결...]\\x1b[0m\\r\\n');
                t.connect();
            }
        }

        function refreshRouterOptions() {
            const terminals = getActiveTerminals();
            terminals.forEach(t => {
                const select = t.el.querySelector(`[data-router-for="${t.id}"]`);
                if (!select) return;
                const current = select.value;

                let opts = '<option value="">📡 None</option>';
                terminals.forEach((other, idx) => {
                    if (other.id !== t.id) {
                        const cfg = AGENT_CONFIG[other.type] || AGENT_CONFIG.shell;
                        const num = idx + 1;
                        opts += `<option value="${other.id}">#${num} ${cfg.icon} ${cfg.name} (${other.role})</option>`;
                    }
                });
                select.innerHTML = opts;
                select.value = current;
            });
        }

        function fitAll() {
            getActiveTerminals().forEach(t => t.fitAddon?.fit());
        }

        // ========== Clear Sessions ==========
        function clearAllSessions() {
            if (!confirm('모든 세션을 초기화할까요?\\n모든 프로젝트와 터미널이 삭제됩니다.')) return;

            // 모든 프로젝트의 터미널 종료
            Object.values(projects).forEach(project => {
                project.terminals.forEach(t => t.dispose());
                project.gridEl.remove();
                localStorage.removeItem(getSessionKey(project.hash));
            });
            projects = {};

            // 프로젝트 목록 초기화
            localStorage.removeItem('agent-terminal-open-projects');
            localStorage.removeItem(PROJECTS_KEY);

            // 상태 초기화
            activeProjectHash = null;
            updateUrlWithProject(null);
            favorites = [];
            recentProjects = [];

            // UI 초기화
            document.getElementById('gridsContainer').innerHTML = '';
            document.getElementById('workDirDisplay').textContent = '폴더를 선택하세요...';
            document.getElementById('fileTree').innerHTML = '';
            renderProjectLists();
            renderProjectTabs();

            showToast('모든 세션이 초기화되었습니다', 'success');
            setTimeout(openFolderModal, 300);
        }

        // ========== Server Restart ==========
        async function restartServer() {
            if (!confirm('서버를 재시작할까요?\\n모든 연결이 끊어집니다.\\n(터미널 구성은 유지됩니다)')) return;

            // 모든 프로젝트 상태 저장
            Object.keys(projects).forEach(hash => {
                const project = projects[hash];
                const state = {
                    workDir: project.path,
                    layoutCols: project.layoutCols,
                    terminals: project.terminals.map(t => ({
                        id: t.id, type: t.type, role: t.role,
                        sessionId: t.sessionId, targetId: t.targetId || null
                    }))
                };
                localStorage.setItem(getSessionKey(hash), JSON.stringify(state));
            });
            saveOpenProjectsList();
            console.log('[RestartServer] 모든 프로젝트 상태 저장 완료');

            updateServerStatus('reconnecting', '재시작 중...');
            showToast('서버 재시작 중... 잠시 후 자동 복원됩니다', 'warning');

            getAllTerminals().forEach(t => t.term?.write('\\r\\n\\x1b[33m[서버 재시작 중... 자동으로 복원됩니다]\\x1b[0m\\r\\n'));

            try {
                await fetch('/api/restart', { method: 'POST' });
                setTimeout(() => {
                    console.log('[RestartServer] 페이지 새로고침');
                    location.reload();
                }, 3000);
            } catch (e) {
                console.error('[RestartServer] 오류:', e);
                showToast('재시작 실패: ' + e.message, 'error');
                updateServerStatus('disconnected', '연결 끊김');
            }
        }

        // ========== Init ==========
        let windowResizeTimeout;
        window.onresize = () => {
            clearTimeout(windowResizeTimeout);
            windowResizeTimeout = setTimeout(fitAll, 300);
        };
        window.onbeforeunload = () => {
            console.log('[Unload] 모든 프로젝트 상태 저장');
            Object.keys(projects).forEach(hash => {
                const project = projects[hash];
                const state = {
                    workDir: project.path,
                    layoutCols: project.layoutCols,
                    terminals: project.terminals.map(t => ({
                        id: t.id, type: t.type, role: t.role,
                        sessionId: t.sessionId, targetId: t.targetId || null
                    }))
                };
                localStorage.setItem(getSessionKey(hash), JSON.stringify(state));
            });
            saveOpenProjectsList();
        };

        document.addEventListener('DOMContentLoaded', () => {
            console.log('[Init] 멀티 프로젝트 모드 시작');

            fetchVersion();
            startHealthCheck();
            loadProjects();

            // 저장된 열린 프로젝트들 복원
            const openData = loadOpenProjectsList();
            let restored = false;

            if (openData && openData.projects && openData.projects.length > 0) {
                console.log(`[Init] ${openData.projects.length}개 프로젝트 복원 시도`);

                // 각 프로젝트 복원 (먼저 모든 프로젝트 구조 생성)
                openData.projects.forEach(projectInfo => {
                    // 저장된 상태에서 layoutCols 미리 로드
                    const savedState = loadState(projectInfo.hash);
                    const savedLayoutCols = savedState?.layoutCols || 1;
                    const gridEl = createProjectGrid(projectInfo.hash, savedLayoutCols);
                    projects[projectInfo.hash] = {
                        hash: projectInfo.hash,
                        path: projectInfo.path,
                        terminals: [],
                        layoutCols: savedLayoutCols,
                        gridEl: gridEl
                    };
                });

                // 활성 프로젝트 먼저 전환
                const targetHash = openData.activeHash || openData.projects[0].hash;
                if (projects[targetHash]) {
                    switchProject(targetHash);
                    // 활성 프로젝트 터미널 복원
                    restored = restoreProjectSession(targetHash);
                }

                // 나머지 프로젝트도 터미널 복원 (백그라운드)
                openData.projects.forEach(projectInfo => {
                    if (projectInfo.hash !== targetHash) {
                        restoreProjectSession(projectInfo.hash);
                    }
                });

                renderProjectTabs();
            }

            // URL 또는 마지막 프로젝트로 폴백
            if (!restored) {
                const urlHash = getProjectFromUrl();
                const lastHash = getLastProject();

                if (urlHash || lastHash) {
                    const targetHash = urlHash || lastHash;
                    // 1. 최근 프로젝트에서 경로 찾기
                    let path = recentProjects.find(p => hashPath(p) === targetHash);
                    // 2. 없으면 저장된 세션 상태에서 workDir 가져오기
                    if (!path) {
                        const savedState = loadState(targetHash);
                        if (savedState?.workDir) {
                            path = savedState.workDir;
                            console.log(`[Init] 저장된 상태에서 workDir 복원: ${path}`);
                        }
                    }
                    if (path) {
                        openProject(path);
                        restored = true;
                    }
                }
            }

            if (!restored) {
                setTimeout(openFolderModal, 300);
            }

            console.log('[Init] 완료, 열린 프로젝트:', Object.keys(projects).length);
        });
    </script>
</body>
</html>
""";

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_CONTENT

if __name__ == "__main__":
    print("Agent Terminal Pro with ChatOps & Persona Injection Started...")
    uvicorn.run(app, host="0.0.0.0", port=8090)
