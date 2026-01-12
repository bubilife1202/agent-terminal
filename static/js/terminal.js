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
                <button class="auto-btn" onclick="toggleAutoContinue('${terminalId}')" title="Auto-Continue Mode">
                    <span class="auto-indicator"></span>
                    <span>Auto</span>
                    <span class="iteration-count"></span>
                </button>
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
        allowProposedApi: true,
        // Performance optimizations
        scrollback: 5000,           // Limit scrollback buffer (default 1000)
        fastScrollModifier: 'alt',  // Alt+scroll for fast scrolling
        smoothScrollDuration: 0,    // Disable smooth scroll for performance
        scrollSensitivity: 3        // Faster scroll response
    });
    
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(new WebLinksAddon.WebLinksAddon());
    
    // GPU-accelerated rendering (WebGL)
    let webglAddon = null;
    try {
        webglAddon = new WebglAddon.WebglAddon();
        webglAddon.onContextLoss(() => {
            webglAddon.dispose();
            webglAddon = null;
            console.warn('[Terminal] WebGL context lost, falling back to canvas');
        });
        term.loadAddon(webglAddon);
        console.log('[Terminal] WebGL renderer enabled');
    } catch (e) {
        console.warn('[Terminal] WebGL not available, using canvas renderer:', e);
    }
    
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
        resizeObserver: resizeObserver,
        // Auto-continue state
        auto: {
            enabled: false,
            lastOutputTime: 0,
            iterationCount: 0,
            maxIterations: 10,
            idleThreshold: 10000,  // 10 seconds
            checkInterval: null,
            outputBuffer: '',
            lastError: ''
        }
    };
    
    proj.terminals.push(termObj);
    resizeObserver.observe(cell.querySelector('.xterm-wrapper'));
    connectTerminal(termObj);

    renderProjectTabs();
    autoLayout();
    updateProjectEmptyState(state.activeProject);
    saveStateLater();

    term.onData(data => {
        if (termObj.ws && termObj.ws.readyState === WebSocket.OPEN) {
            termObj.ws.send(JSON.stringify({ type: 'input', data }));
        }
    });
    
    term.attachCustomKeyEventHandler((e) => {
        // Only handle keydown events to prevent duplicate actions
        if (e.type !== 'keydown') return true;
        
        // Ctrl+Shift+C: Copy selected text
        if (e.ctrlKey && e.shiftKey && e.key === 'C') {
            const selection = term.getSelection();
            if (selection) {
                navigator.clipboard.writeText(selection).then(() => {
                    showToast('Copied to clipboard', 'success');
                }).catch(() => {
                    showToast('Failed to copy', 'error');
                });
            }
            return false;
        }
        // Ctrl+V: Paste
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
                // Check if already at bottom before writing
                const buffer = termObj.term.buffer.active;
                const isAtBottom = buffer.baseY + termObj.term.rows >= buffer.length;
                
                termObj.term.write(msg.data);
                
                // Only auto-scroll if user was already at bottom
                if (isAtBottom) {
                    termObj.term.scrollToBottom();
                }
                
                // Auto-continue: track output
                if (termObj.auto.enabled) {
                    termObj.auto.lastOutputTime = Date.now();
                    termObj.auto.outputBuffer += msg.data;
                    
                    // Check for completion signal
                    if (termObj.auto.outputBuffer.includes('=== DONE ===')) {
                        stopAutoContinue(termObj.id);
                        showToast(`✅ 작업 완료! (${termObj.auto.iterationCount}회 반복)`, 'success');
                        termObj.term.write('\r\n\x1b[32m[Auto-Continue: Task completed!]\x1b[0m\r\n');
                    }
                    
                    // Stuck detection: same error repeating
                    const errorMatch = msg.data.match(/error|exception|failed|traceback/i);
                    if (errorMatch) {
                        const errorSnippet = msg.data.substring(0, 200);
                        if (termObj.auto.lastError === errorSnippet) {
                            stopAutoContinue(termObj.id);
                            showToast('⚠️ 동일 에러 반복 감지 - 자동 중단', 'warning');
                            termObj.term.write('\r\n\x1b[33m[Auto-Continue: Stopped - same error repeating]\x1b[0m\r\n');
                        }
                        termObj.auto.lastError = errorSnippet;
                    }
                }
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

    const { terminal: t, project: proj, projectPath } = found;
    const idx = proj.terminals.findIndex(x => x.id === id);
    if (idx !== -1) {
        // Stop auto-continue if active
        if (t.auto && t.auto.checkInterval) {
            clearInterval(t.auto.checkInterval);
        }
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
        updateProjectEmptyState(projectPath);
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

// ========== Auto-Continue Mode ==========

const AUTO_CONTINUE_PROMPT = `
지금까지 작성한 내용을 테스트해줘.
- 테스트가 실패하면 수정하고 다시 테스트해
- 테스트가 성공하면 edge case, 에러 처리, 코드 품질을 검토해서 개선해
- 더 이상 개선할 게 없으면 '=== DONE ===' 이라고 출력해
`;

function toggleAutoContinue(id) {
    const found = findTerminal(id);
    if (!found) return;
    
    const t = found.terminal;
    if (t.auto.enabled) {
        stopAutoContinue(id);
    } else {
        startAutoContinue(id);
    }
}

function startAutoContinue(id) {
    const found = findTerminal(id);
    if (!found) return;
    
    const t = found.terminal;
    t.auto.enabled = true;
    t.auto.iterationCount = 0;
    t.auto.outputBuffer = '';
    t.auto.lastOutputTime = Date.now();
    t.auto.lastError = '';
    
    // Update UI
    updateAutoButton(id, true);
    t.term.write('\r\n\x1b[36m[Auto-Continue: ON - 작업 완료까지 자동 진행]\x1b[0m\r\n');
    showToast('🔄 Auto-Continue 활성화', 'success');
    
    // Start check interval (every 3 seconds)
    t.auto.checkInterval = setInterval(() => {
        checkAutoContinue(t);
    }, 3000);
}

function stopAutoContinue(id) {
    const found = findTerminal(id);
    if (!found) return;
    
    const t = found.terminal;
    t.auto.enabled = false;
    
    if (t.auto.checkInterval) {
        clearInterval(t.auto.checkInterval);
        t.auto.checkInterval = null;
    }
    
    // Update UI
    updateAutoButton(id, false);
    t.term.write('\r\n\x1b[90m[Auto-Continue: OFF]\x1b[0m\r\n');
}

function checkAutoContinue(termObj) {
    if (!termObj.auto.enabled) return;
    
    const timeSinceLastOutput = Date.now() - termObj.auto.lastOutputTime;
    
    // Check if idle for threshold time
    if (timeSinceLastOutput >= termObj.auto.idleThreshold) {
        // Check max iterations
        if (termObj.auto.iterationCount >= termObj.auto.maxIterations) {
            stopAutoContinue(termObj.id);
            showToast(`⚠️ 최대 반복 횟수(${termObj.auto.maxIterations}) 도달`, 'warning');
            termObj.term.write('\r\n\x1b[33m[Auto-Continue: Max iterations reached]\x1b[0m\r\n');
            return;
        }
        
        // Send continuation prompt
        termObj.auto.iterationCount++;
        termObj.auto.outputBuffer = '';
        termObj.auto.lastOutputTime = Date.now();
        
        // Update iteration display
        updateAutoButton(termObj.id, true, termObj.auto.iterationCount);
        
        termObj.term.write(`\r\n\x1b[36m[Auto-Continue: Iteration ${termObj.auto.iterationCount}/${termObj.auto.maxIterations}]\x1b[0m\r\n`);
        
        if (termObj.ws && termObj.ws.readyState === WebSocket.OPEN) {
            termObj.ws.send(JSON.stringify({
                type: 'input',
                data: AUTO_CONTINUE_PROMPT + '\n'
            }));
        }
    }
}

function updateAutoButton(id, active, iteration = 0) {
    const btn = document.querySelector(`#term-${id} .auto-btn`);
    if (!btn) return;
    
    if (active) {
        btn.classList.add('active');
        const countSpan = btn.querySelector('.iteration-count');
        if (countSpan) {
            countSpan.textContent = iteration > 0 ? `(${iteration}/10)` : '';
        }
    } else {
        btn.classList.remove('active');
        const countSpan = btn.querySelector('.iteration-count');
        if (countSpan) {
            countSpan.textContent = '';
        }
    }
}
