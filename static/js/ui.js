// ui.js - UI Management

let selectedAgent = 'claude';
let selectedRole = 'General';
let pendingAgentType = null;
let browsingPath = 'drives';

// --- Utils ---
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(msg, type = 'success') {
    const container = document.getElementById('toastContainer');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `<span>${msg}</span><button style="background:none;border:none;color:inherit;cursor:pointer;" onclick="this.parentElement.remove()">✕</button>`;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

function showShortcuts() {
    alert('Shortcuts:\nAlt+1/2/4: Change Layout\nCtrl+Shift+R: Restart Server\nCtrl+V: Paste (Text/Image)');
}

// --- Project Management UI ---
function openProject(path) {
    if (!path) return;

    const openCount = Object.keys(state.projects).length;
    if (openCount >= MAX_PROJECTS && !state.projects[path]) {
        showToast(`Max ${MAX_PROJECTS} projects allowed. Close one first.`, 'error');
        return;
    }

    if (!state.projects[path]) {
        state.projects[path] = {
            terminals: [],
            layout: 1
        };
        createProjectContent(path);
    }

    switchProject(path);
    addToProjectHistory(path);
    saveStateLater();
}

function switchProject(path) {
    if (!path || !state.projects[path]) return;

    state.activeProject = path;
    renderProjectTabs();

    document.querySelectorAll('.project-content').forEach(el => {
        el.classList.toggle('active', el.dataset.path === path);
    });

    document.getElementById('workDirDisplay').textContent = getProjectName(path);
    loadFiles(path);
    updateLayoutButtons();
    updateProjectEmptyState(path);
    setTimeout(() => fitAllTerminals(), 100);
    updateEmptyState();
}

function closeProject(path) {
    if (!state.projects[path]) return;

    const proj = state.projects[path];
    proj.terminals.forEach(t => {
        t.ws?.close();
        t.term?.dispose();
    });

    const content = document.querySelector(`.project-content[data-path="${CSS.escape(path)}"]`);
    if (content) content.remove();

    delete state.projects[path];

    const remaining = Object.keys(state.projects);
    if (remaining.length > 0) {
        switchProject(remaining[0]);
    } else {
        state.activeProject = null;
        document.getElementById('workDirDisplay').textContent = 'Select Folder...';
        document.getElementById('fileTree').innerHTML = '';
        renderProjectTabs();
        updateEmptyState();
    }

    saveStateLater();
}

function createProjectContent(path) {
    const container = document.getElementById('projectContents');
    const div = document.createElement('div');
    div.className = 'project-content';
    div.dataset.path = path;
    
    // Generate agent cards HTML
    const agentCardsHtml = Object.entries(AGENTS).map(([type, config]) => `
        <div class="agent-card" onclick="createTerminal('${type}', 'General')">
            <div class="icon">${config.icon}</div>
            <div class="name">${config.name}</div>
        </div>
    `).join('');
    
    div.innerHTML = `
        <div class="project-empty-state" data-empty="${path}">
            <h2>Select an Agent</h2>
            <p>Choose an agent to start working in this project</p>
            <div class="agent-cards">
                ${agentCardsHtml}
            </div>
        </div>
        <div class="grid-container grid-1" data-grid="${path}">
        </div>
    `;
    container.appendChild(div);
}

function updateProjectEmptyState(path) {
    const emptyState = document.querySelector(`.project-empty-state[data-empty="${CSS.escape(path)}"]`);
    const gridContainer = document.querySelector(`.grid-container[data-grid="${CSS.escape(path)}"]`);
    
    if (!emptyState || !gridContainer) return;
    
    const proj = state.projects[path];
    const hasTerminals = proj && proj.terminals.length > 0;
    
    if (hasTerminals) {
        emptyState.style.display = 'none';
        gridContainer.style.display = 'grid';
    } else {
        emptyState.style.display = 'flex';
        gridContainer.style.display = 'none';
    }
}

function renderProjectTabs() {
    const tabsContainer = document.getElementById('projectTabs');
    const paths = Object.keys(state.projects);

    if (paths.length === 0) {
        tabsContainer.innerHTML = '';
        return;
    }

    tabsContainer.innerHTML = paths.map(path => {
        const proj = state.projects[path];
        const name = escapeHtml(getProjectName(path));
        const escapedPath = escapeHtml(path);
        const jsPath = path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const termCount = proj.terminals.length;
        const isActive = path === state.activeProject;
        return `
            <div class="project-tab ${isActive ? 'active' : ''}" data-path="${escapedPath}" onclick="switchProject('${jsPath}')">
                <span class="tab-name" title="${escapedPath}">${name}</span>
                ${termCount > 0 ? `<span class="terminal-count">${termCount}</span>` : ''}
                <span class="tab-close" onclick="event.stopPropagation(); closeProject('${jsPath}')">✕</span>
            </div>
        `;
    }).join('');
}

// --- Agent UI ---
function initAgentUI() {
    const emptyCards = document.getElementById('emptyStateCards');
    emptyCards.innerHTML = Object.entries(AGENTS).map(([type, config]) => `
        <div class="agent-card" onclick="quickStartAgent('${type}')">
            <div class="icon">${config.icon}</div>
            <div class="name">${config.name}</div>
        </div>
    `).join('');

    const agentGrid = document.getElementById('agentGrid');
    agentGrid.innerHTML = Object.entries(AGENTS).map(([type, config]) => `
        <div class="agent-option ${type === 'claude' ? 'selected' : ''}" data-type="${type}" onclick="selectAgent('${type}')">
            <div class="icon">${config.icon}</div>
            <div class="name">${config.name}</div>
        </div>
    `).join('');

    updateEmptyState();
}

function updateEmptyState() {
    const emptyState = document.getElementById('emptyState');
    const hasProjects = Object.keys(state.projects).length > 0;
    if (hasProjects) {
        emptyState.classList.add('hidden');
    } else {
        emptyState.classList.remove('hidden');
    }
}

function quickStartAgent(type) {
    if (!state.activeProject) {
        pendingAgentType = type;
        openFolderModal();
        showToast('Select a folder to start', 'warning');
        return;
    }
    createTerminal(type, 'General');
}

function openNewTerminalModal() {
    if (!state.activeProject) {
        openFolderModal();
        showToast('Please select a working directory first', 'warning');
        return;
    }
    const proj = getActiveProject();
    if (proj && proj.terminals.length >= 4) {
        showToast('Max 4 terminals per project', 'error');
        return;
    }
    selectedAgent = 'claude';
    selectedRole = 'General';
    document.querySelectorAll('.agent-option').forEach(el => {
        el.classList.toggle('selected', el.dataset.type === 'claude');
    });
    document.querySelectorAll('.role-option').forEach(el => {
        el.classList.toggle('selected', el.dataset.role === 'General');
    });
    document.getElementById('newTerminalModal').classList.add('show');
}

function closeNewTerminalModal() {
    document.getElementById('newTerminalModal').classList.remove('show');
}

function selectAgent(type) {
    selectedAgent = type;
    document.querySelectorAll('.agent-option').forEach(el => {
        el.classList.toggle('selected', el.dataset.type === type);
    });
}

function selectRole(role) {
    selectedRole = role;
    document.querySelectorAll('.role-option').forEach(el => {
        el.classList.toggle('selected', el.dataset.role === role);
    });
}

function confirmNewTerminal() {
    createTerminal(selectedAgent, selectedRole);
    closeNewTerminalModal();
}

// --- Layout ---
function setLayout(cols) {
    const proj = getActiveProject();
    if (proj) {
        proj.layout = cols;
    }
    updateLayout();
    updateLayoutButtons();
    saveStateLater();
}

function autoLayout() {
    const proj = getActiveProject();
    if (!proj) return;
    
    const count = proj.terminals.length;
    let newLayout;
    
    if (count <= 1) {
        newLayout = 1;
    } else if (count === 2) {
        newLayout = 2;
    } else {
        newLayout = 4;
    }
    
    if (proj.layout !== newLayout) {
        proj.layout = newLayout;
        updateLayout();
        updateLayoutButtons();
    }
}

function updateLayoutButtons() {
    const layout = getActiveLayout();
    document.querySelectorAll('.layout-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.layout == layout);
    });
}

function updateLayout() {
    if (!state.activeProject) return;
    
    const grid = document.querySelector(`.project-content[data-path="${CSS.escape(state.activeProject)}"] .grid-container`);
    if (!grid) return;
    
    const layout = getActiveLayout();
    grid.className = `grid-container grid-${layout}`;
    
    requestAnimationFrame(() => {
        fitAllTerminals();
        setTimeout(() => fitAllTerminals(), 100);
        setTimeout(() => fitAllTerminals(), 300);
    });
}

function fitAllTerminals() {
    const terminals = getActiveTerminals();
    terminals.forEach(t => {
        t.fit.fit();
        if (t.ws && t.ws.readyState === WebSocket.OPEN) {
            t.ws.send(JSON.stringify({
                type: 'resize',
                rows: t.term.rows,
                cols: t.term.cols
            }));
        }
    });
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebarToggleBtn');
    sidebar.classList.toggle('collapsed');
    toggleBtn.classList.toggle('visible', sidebar.classList.contains('collapsed'));
    setTimeout(() => fitAllTerminals(), 300);
}

// --- File Explorer ---
let currentFilePath = null;  // Track current directory for navigation
let currentFilePreviewPath = null;  // Track file being previewed

function createFileItem(item) {
    const div = document.createElement('div');
    div.className = `file-item ${state.activeProject === item.path ? 'active' : ''}`;
    
    // Better file icons based on extension
    let icon = '📄';
    if (item.is_dir) {
        icon = '📂';
    } else {
        const ext = item.name.split('.').pop().toLowerCase();
        const iconMap = {
            'md': '📝', 'txt': '📝',
            'js': '🟨', 'ts': '🔷', 'jsx': '⚛️', 'tsx': '⚛️',
            'py': '🐍', 'rb': '💎', 'go': '🔵', 'rs': '🦀',
            'html': '🌐', 'css': '🎨', 'scss': '🎨',
            'json': '📋', 'yaml': '📋', 'yml': '📋', 'toml': '📋',
            'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️', 'svg': '🖼️',
            'pdf': '📕', 'doc': '📘', 'docx': '📘',
            'zip': '📦', 'tar': '📦', 'gz': '📦',
            'sh': '⚙️', 'bash': '⚙️', 'zsh': '⚙️',
            'gitignore': '🙈', 'env': '🔐'
        };
        icon = iconMap[ext] || '📄';
    }
    
    div.innerHTML = `<span class="file-icon">${icon}</span><span>${escapeHtml(item.name)}</span>`;
    div.addEventListener('click', () => {
        if (item.is_dir) {
            loadFiles(item.path);
        } else {
            openFilePreview(item.path);
        }
    });
    return div;
}

let currentParentPath = null;  // Track parent for navigation

async function loadFiles(path) {
    if (!path) return;
    try {
        const res = await fetch(`/api/files?path=${encodeURIComponent(path)}`);
        const data = await res.json();

        currentFilePath = data.path || path;
        currentParentPath = data.parent || null;

        const tree = document.getElementById('fileTree');
        tree.innerHTML = '';
        data.items.forEach(item => {
            tree.appendChild(createFileItem(item));
        });
    } catch (e) {
        console.error(e);
        showToast('Failed to load files', 'error');
    }
}

function refreshFiles() {
    if (currentFilePath) {
        loadFiles(currentFilePath);
    } else if (state.activeProject) {
        loadFiles(state.activeProject);
    }
}

function navigateToParent() {
    if (currentParentPath) {
        loadFiles(currentParentPath);
    } else if (currentFilePath && currentFilePath !== state.activeProject) {
        // Fallback: go to project root
        loadFiles(state.activeProject);
    } else {
        showToast('Already at root', 'warning');
    }
}

function pastePath(path) {
    const terminals = getActiveTerminals();
    const term = terminals.find(t => t.ws && t.ws.readyState === WebSocket.OPEN);
    if (term) {
        term.ws.send(JSON.stringify({ type: 'input', data: path }));
        showToast('Path sent to terminal', 'success');
    } else {
        showToast('No active terminal to send path', 'warning');
    }
}

// --- File Preview ---
async function openFilePreview(path) {
    currentFilePreviewPath = path;
    const modal = document.getElementById('filePreviewModal');
    const content = document.getElementById('filePreviewContent');
    const fileName = document.getElementById('filePreviewName');
    
    // Show modal with loading state
    modal.classList.add('show');
    content.innerHTML = `
        <div class="file-preview-loading">
            <div class="spinner"></div>
            <span>Loading...</span>
        </div>
    `;
    fileName.textContent = path.split(/[/\\]/).pop();
    
    try {
        const res = await fetch(`/api/file-content?path=${encodeURIComponent(path)}`);
        const data = await res.json();
        
        if (!res.ok || data.error) {
            content.innerHTML = `
                <div class="file-preview-error">
                    <span class="error-icon">⚠️</span>
                    <span>${escapeHtml(data.message || data.error || 'Failed to load file')}</span>
                </div>
            `;
            return;
        }
        
        // Render content based on file type
        if (data.language === 'markdown') {
            // Render markdown
            const rendered = marked.parse(data.content);
            content.innerHTML = `<div class="file-preview-markdown">${rendered}</div>`;
            // Apply syntax highlighting to code blocks in markdown
            content.querySelectorAll('pre code').forEach(block => {
                hljs.highlightElement(block);
            });
        } else {
            // Render as code with syntax highlighting
            const escaped = escapeHtml(data.content);
            content.innerHTML = `<pre class="file-preview-code"><code class="language-${data.language}">${escaped}</code></pre>`;
            content.querySelectorAll('pre code').forEach(block => {
                hljs.highlightElement(block);
            });
        }
    } catch (e) {
        console.error('File preview error:', e);
        content.innerHTML = `
            <div class="file-preview-error">
                <span class="error-icon">❌</span>
                <span>Failed to load file</span>
            </div>
        `;
    }
}

function closeFilePreview() {
    document.getElementById('filePreviewModal').classList.remove('show');
    currentFilePreviewPath = null;
}

function copyFilePath() {
    if (currentFilePreviewPath) {
        navigator.clipboard.writeText(currentFilePreviewPath).then(() => {
            showToast('Path copied!', 'success');
        }).catch(() => {
            showToast('Failed to copy', 'error');
        });
    }
}

// Close file preview with ESC key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modal = document.getElementById('filePreviewModal');
        if (modal && modal.classList.contains('show')) {
            closeFilePreview();
        }
    }
});

// Close file preview when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('filePreviewModal');
    if (modal && modal.classList.contains('show')) {
        if (e.target === modal) {
            closeFilePreview();
        }
    }
});

// --- Folder Modal ---
function openFolderModal() {
    document.getElementById('folderModal').classList.add('show');
    loadFolderList('drives');
}

function closeFolderModal() {
    document.getElementById('folderModal').classList.remove('show');
}

function createFolderItem(folder) {
    const div = document.createElement('div');
    div.className = 'file-item';
    div.innerHTML = `<span class="file-icon">${folder.is_drive ? '💾' : '📁'}</span><span>${escapeHtml(folder.name)}</span>`;
    div.addEventListener('click', () => {
        loadFolderList(folder.path);
    });
    return div;
}

async function loadFolderList(path) {
    try {
        const res = await fetch(`/api/folders?path=${encodeURIComponent(path)}`);
        const data = await res.json();

        browsingPath = data.current || path;
        document.getElementById('pathInput').value = browsingPath;

        const list = document.getElementById('folderList');
        list.innerHTML = '';

        if (data.folders && data.folders.length > 0) {
            data.folders.forEach(f => {
                list.appendChild(createFolderItem(f));
            });
        } else {
            const emptyMsg = document.createElement('div');
            emptyMsg.style.cssText = 'padding:10px; color:var(--text-muted)';
            emptyMsg.textContent = 'No folders found';
            list.appendChild(emptyMsg);
        }
    } catch (e) {
        showToast('Error loading folders', 'error');
    }
}

function navigateUp() {
    if (browsingPath === 'drives') return;
    loadFolderList(browsingPath + '/..');
}

function confirmFolder() {
    if (!browsingPath || browsingPath === 'drives') return;
    
    openProject(browsingPath);
    closeFolderModal();
    showToast(`Project opened: ${getProjectName(browsingPath)}`, 'success');
    
    if (pendingAgentType) {
        const agentType = pendingAgentType;
        pendingAgentType = null;
        setTimeout(() => createTerminal(agentType, 'General'), 200);
    }
}

// --- Project History ---
function addToProjectHistory(path) {
    if (!path) return;

    state.projectHistory = state.projectHistory.filter(p => p !== path);
    state.projectHistory.unshift(path);

    if (state.projectHistory.length > 10) {
        state.projectHistory = state.projectHistory.slice(0, 10);
    }

    renderProjectHistory();
    saveStateLater();
}

function renderProjectHistory() {
    const list = document.getElementById('recentProjectsList');
    if (!list) return;

    if (state.projectHistory.length === 0) {
        list.innerHTML = '<div style="padding:8px; color:var(--text-muted); font-size:11px;">No recent projects</div>';
        return;
    }

    list.innerHTML = state.projectHistory.map(path => {
        const isOpen = !!state.projects[path];
        const isActive = path === state.activeProject;
        const folderName = escapeHtml(getProjectName(path));
        const escapedPath = escapeHtml(path);
        const jsPath = path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        return `
            <div class="file-item ${isActive ? 'active' : ''}" onclick="openProject('${jsPath}')">
                <span class="file-icon">${isOpen ? '📂' : '📁'}</span>
                <span style="flex:1; overflow:hidden; text-overflow:ellipsis;" title="${escapedPath}">${folderName}</span>
                ${isOpen ? '<span style="font-size:9px; color:var(--accent);">●</span>' : ''}
                <span style="font-size:10px; color:var(--text-muted); cursor:pointer;" onclick="event.stopPropagation(); removeFromHistory('${jsPath}')">✕</span>
            </div>
        `;
    }).join('');
}

function removeFromHistory(path) {
    state.projectHistory = state.projectHistory.filter(p => p !== path);
    renderProjectHistory();
    saveStateLater();
}
