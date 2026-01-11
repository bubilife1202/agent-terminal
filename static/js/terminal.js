// terminal.js - Terminal Management

function createTerminal(type, role = 'General', id = null) {
    if (!state.activeProject) {
        openFolderModal();
        showToast('Please select a working directory first', 'warning');
        return;
    }

    const proj = getActiveProject();
    if (!proj) return;

    if (proj.terminals.length >= 4) {
        showToast('Max 4 terminals per project', 'error');
        return;
    }

    const terminalId = id || crypto.randomUUID();
    const container = document.querySelector(`.project-content[data-path="${CSS.escape(state.activeProject)}"] .grid-container`);
    if (!container) {
        console.error('No grid container for project:', state.activeProject);
        return;
    }
    
    const cell = document.createElement('div');
    cell.className = 'term-cell';
    cell.id = `term-${terminalId}`;
    
    const config = AGENTS[type];
    
    cell.innerHTML = `
        <div class="term-header" style="border-left: 3px solid ${config.color}">
            <div class="term-title">
                <span>${config.icon}</span>
                <span>${config.name}</span>
                <span class="role-badge ${role}" onclick="cycleRole('${terminalId}')">${role}</span>
            </div>
            <div class="term-actions">
                <button class="term-btn" onclick="restartTerminal('${terminalId}')" title="Restart Session">↻</button>
                <button class="term-btn" onclick="toggleMaximize('${terminalId}')" title="Maximize">⤢</button>
                <button class="term-btn close" onclick="closeTerminal('${terminalId}')" title="Close">✕</button>
            </div>
        </div>
        <div class="xterm-wrapper"></div>
    `;
    
    container.appendChild(cell);

    const term = new Terminal({
        fontFamily: '"JetBrains Mono", "Consolas", monospace',
        fontSize: 13,
        cursorBlink: true,
        theme: {
            background: '#1a1b26',
            foreground: '#c0caf5',
            cursor: config.color,
            selection: 'rgba(122, 162, 247, 0.3)'
        },
        allowProposedApi: true
    });
    
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(new WebLinksAddon.WebLinksAddon());
    
    const wrapper = cell.querySelector('.xterm-wrapper');
    term.open(wrapper);
    
    const smartFit = () => {
        const rect = wrapper.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
            fitAddon.fit();
            return true;
        }
        return false;
    };
    
    smartFit();
    requestAnimationFrame(() => {
        if (!smartFit()) {
            setTimeout(() => smartFit(), 50);
        }
        setTimeout(() => smartFit(), 100);
        setTimeout(() => smartFit(), 200);
        setTimeout(() => smartFit(), 500);
        setTimeout(() => smartFit(), 1000);
    });

    const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
            if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
                fitAddon.fit();
                if (termObj.ws && termObj.ws.readyState === WebSocket.OPEN) {
                    termObj.ws.send(JSON.stringify({ 
                        type: 'resize', 
                        rows: term.rows,
                        cols: term.cols 
                    }));
                }
            }
        }
    });

    const termObj = {
        id: terminalId,
        type,
        role,
        term,
        fit: fitAddon,
        ws: null,
        el: cell,
        projectPath: state.activeProject,
        resizeObserver: resizeObserver
    };
    
    proj.terminals.push(termObj);
    resizeObserver.observe(cell.querySelector('.xterm-wrapper'));
    connectTerminal(termObj);

    renderProjectTabs();
    autoLayout();
    saveStateLater();

    term.onData(data => {
        if (termObj.ws && termObj.ws.readyState === WebSocket.OPEN) {
            termObj.ws.send(JSON.stringify({ type: 'input', data }));
        }
    });
    
    term.attachCustomKeyEventHandler((e) => {
        if (e.ctrlKey && e.key === 'v') {
            handlePaste(termObj);
            return false;
        }
        return true;
    });

    return termObj;
}

function connectTerminal(termObj, retryCount = 0) {
    const MAX_RETRIES = 5;
    const RETRY_DELAYS = [1000, 2000, 3000, 4000, 5000];

    if (termObj.ws) {
        termObj.ws.onopen = null;
        termObj.ws.onclose = null;
        termObj.ws.onerror = null;
        termObj.ws.onmessage = null;
        termObj.ws.close();
    }

    const workDir = termObj.projectPath;
    if (!workDir) {
        termObj.term.write('\r\n\x1b[33m[No working directory set. Please select a folder first.]\x1b[0m\r\n');
        return;
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws/terminal/${termObj.id}?workdir=${encodeURIComponent(workDir)}&agent=${encodeURIComponent(termObj.type)}&role=${encodeURIComponent(termObj.role)}`;

    console.log('[Terminal] Connecting to:', url, retryCount > 0 ? `(retry ${retryCount}/${MAX_RETRIES})` : '');

    if (retryCount > 0) {
        termObj.term.write(`\x1b[33m[Reconnecting... ${retryCount}/${MAX_RETRIES}]\x1b[0m\r\n`);
    }

    termObj.ws = new WebSocket(url);
    let connected = false;

    termObj.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        if (!connected && retryCount < MAX_RETRIES) {
            const delay = RETRY_DELAYS[retryCount] || 5000;
            termObj.term.write(`\r\n\x1b[31m[Connection failed - retrying in ${delay/1000}s...]\x1b[0m\r\n`);
            setTimeout(() => connectTerminal(termObj, retryCount + 1), delay);
        } else if (!connected) {
            termObj.term.write('\r\n\x1b[31m[Connection Error - Max retries exceeded]\x1b[0m\r\n');
            termObj.term.write('\x1b[33mClick ↻ to retry or check if server is running.\x1b[0m\r\n');
        }
    };

    termObj.ws.onopen = () => {
        connected = true;
        termObj.term.write(`\x1b[32m✔ Connected to ${AGENTS[termObj.type].name} (${termObj.role})\x1b[0m\r\n`);
        termObj.fit.fit();
        termObj.ws.send(JSON.stringify({
            type: 'resize',
            rows: termObj.term.rows,
            cols: termObj.term.cols
        }));
    };

    termObj.ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'terminal_output') {
                termObj.term.write(msg.data);
            } else if (msg.type === 'image_added') {
                termObj.term.write(`\r\n\x1b[35m[Image Added: ${msg.filename}]\x1b[0m\r\n`);
            } else if (msg.type === 'error') {
                showToast(msg.message, 'error');
            }
        } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
        }
    };

    termObj.ws.onclose = () => {
        if (connected) {
            termObj.term.write('\r\n\x1b[90m[Connection Closed]\x1b[0m\r\n');
        }
    };
}

function closeTerminal(id) {
    const found = findTerminal(id);
    if (!found) return;

    const { terminal: t, project: proj } = found;
    const idx = proj.terminals.findIndex(x => x.id === id);
    if (idx !== -1) {
        if (t.ws) {
            t.ws.onopen = null;
            t.ws.onclose = null;
            t.ws.onerror = null;
            t.ws.onmessage = null;
            t.ws.close();
        }
        t.resizeObserver?.disconnect();
        t.term?.dispose();
        t.el.remove();
        proj.terminals.splice(idx, 1);
        renderProjectTabs();
        autoLayout();
        saveStateLater();
    }
}

function restartTerminal(id) {
    const found = findTerminal(id);
    if (found) {
        found.terminal.term.reset();
        connectTerminal(found.terminal);
    }
}

function cycleRole(id) {
    const found = findTerminal(id);
    if (!found) return;
    
    const t = found.terminal;
    const roles = ['General', 'PM', 'Dev', 'QA'];
    const nextIdx = (roles.indexOf(t.role) + 1) % roles.length;
    t.role = roles[nextIdx];
    
    const badge = t.el.querySelector('.role-badge');
    badge.className = `role-badge ${t.role}`;
    badge.textContent = t.role;
    
    t.term.write(`\r\n\x1b[33m[Switching Role to ${t.role}...]\x1b[0m\r\n`);
    connectTerminal(t);
    saveStateLater();
}

function toggleMaximize(id) {
    const found = findTerminal(id);
    if (!found) return;
    
    const t = found.terminal;
    if (t.el.classList.contains('maximized')) {
        t.el.classList.remove('maximized');
    } else {
        found.project.terminals.forEach(x => x.el.classList.remove('maximized'));
        t.el.classList.add('maximized');
    }
    setTimeout(() => t.fit.fit(), 100);
}

function reconnectAllTerminals() {
    getAllTerminals().forEach(t => {
        t.term.write('\r\n\x1b[33m[Reconnecting...]\x1b[0m\r\n');
        connectTerminal(t);
    });
}

async function handlePaste(termObj) {
    try {
        const items = await navigator.clipboard.read();
        for (const item of items) {
            if (item.types.some(t => t.startsWith('image/'))) {
                const blob = await item.getType(item.types.find(t => t.startsWith('image/')));
                const reader = new FileReader();
                reader.onload = () => {
                    if (termObj.ws) {
                        termObj.ws.send(JSON.stringify({
                            type: 'image',
                            data: reader.result,
                            filename: 'pasted_image.png'
                        }));
                        showToast('Image pasted!', 'success');
                    }
                };
                reader.readAsDataURL(blob);
                return;
            }
        }
        const text = await navigator.clipboard.readText();
        if (termObj.term) termObj.term.paste(text);
    } catch (e) {
        try {
            const text = await navigator.clipboard.readText();
            if (termObj.term) termObj.term.paste(text);
        } catch (err) {
            showToast('Clipboard access denied', 'error');
        }
    }
}
