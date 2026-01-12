// state.js - Configuration and State Management

const AGENTS = {
    claude: { name: 'Claude', icon: '🔵', color: '#7aa2f7' },
    gemini: { name: 'Gemini', icon: '🟢', color: '#9ece6a' },
    codex: { name: 'Codex', icon: '🟠', color: '#ff9e64' },
    opencode: { name: 'OpenCode', icon: '🟣', color: '#bb9af7' },
    shell: { name: 'Shell', icon: '⚪', color: '#a9b1d6' }
};

const MAX_PROJECTS = 10;

// Global State
let state = {
    projects: {},           // { [path]: { terminals: [], layout: 1 } }
    activeProject: null,    // current project path
    serverStatus: 'disconnected',
    projectHistory: []      // Recent projects (max 10)
};

// State loaded flag
let stateLoaded = false;

// --- Project Helpers ---
function getActiveProject() {
    if (!state.activeProject) return null;
    return state.projects[state.activeProject] || null;
}

function getActiveTerminals() {
    const proj = getActiveProject();
    return proj ? proj.terminals : [];
}

function getActiveLayout() {
    const proj = getActiveProject();
    return proj ? proj.layout : 1;
}

function getProjectName(path) {
    if (!path) return 'Unknown';
    const normalized = path.replace(/\\/g, '/');
    if (/^[A-Za-z]:[\\/]?$/.test(path)) {
        return path.replace(/[\\/]+$/, '');
    }
    const parts = normalized.replace(/\/+$/, '').split('/');
    for (let i = parts.length - 1; i >= 0; i--) {
        if (parts[i] && parts[i] !== '') {
            return parts[i];
        }
    }
    return path;
}

// Helper: find terminal by ID across all projects
function findTerminal(id) {
    for (const path of Object.keys(state.projects)) {
        const proj = state.projects[path];
        const t = proj.terminals.find(t => t.id === id);
        if (t) return { terminal: t, projectPath: path, project: proj };
    }
    return null;
}

// Helper: get all terminals from all projects
function getAllTerminals() {
    const all = [];
    for (const path of Object.keys(state.projects)) {
        all.push(...state.projects[path].terminals);
    }
    return all;
}

// --- Persistence ---
let saveStateTimer = null;

function saveStateLater() {
    if (saveStateTimer) clearTimeout(saveStateTimer);
    saveStateTimer = setTimeout(() => {
        saveState();
        saveStateTimer = null;
    }, 500);
}

function saveState() {
    const projectsData = {};
    for (const [path, proj] of Object.entries(state.projects)) {
        projectsData[path] = {
            layout: proj.layout,
            terminals: proj.terminals.map(t => ({
                id: t.id,
                type: t.type,
                role: t.role
            }))
        };
    }

    const persist = {
        projects: projectsData,
        activeProject: state.activeProject,
        projectHistory: state.projectHistory
    };
    localStorage.setItem('agent-terminal-v4', JSON.stringify(persist));
}

function clearAllData() {
    localStorage.removeItem('agent-terminal-v2');
    localStorage.removeItem('agent-terminal-v3');
    localStorage.removeItem('agent-terminal-v4');
    state.projects = {};
    state.activeProject = null;
    state.projectHistory = [];
    renderProjectHistory();
    renderProjectTabs();
    updateEmptyState();
    showToast('All data cleared', 'success');
}

function loadState() {
    try {
        localStorage.removeItem('agent-terminal-v2');
        localStorage.removeItem('agent-terminal-v3');
        
        let saved = JSON.parse(localStorage.getItem('agent-terminal-v4'));

        if (saved) {
            state.projectHistory = saved.projectHistory || [];
            renderProjectHistory();

            if (saved.projects) {
                for (const [path, projData] of Object.entries(saved.projects)) {
                    state.projects[path] = {
                        terminals: [],
                        layout: projData.layout || 1
                    };
                    createProjectContent(path);
                    state.activeProject = path;

                    if (projData.terminals && projData.terminals.length > 0) {
                        // 새 세션 ID 생성 (서버 재시작 후 "already in use" 에러 방지)
                        // Claude CLI는 같은 session-id로 재연결 시 에러 발생하므로 매번 새 ID 생성
                        projData.terminals.forEach(t => createTerminal(t.type, t.role, null));
                    }
                }
            }

            const activeProject = saved.activeProject || Object.keys(state.projects)[0];
            if (activeProject && state.projects[activeProject]) {
                switchProject(activeProject);
            } else if (Object.keys(state.projects).length > 0) {
                switchProject(Object.keys(state.projects)[0]);
            } else {
                state.activeProject = null;
                document.getElementById('workDirDisplay').textContent = 'Select Folder...';
            }

            renderProjectTabs();
            updateEmptyState();
        } else {
            renderProjectHistory();
            updateEmptyState();
        }
    } catch (e) {
        console.error('Failed to load state', e);
        renderProjectHistory();
        updateEmptyState();
    }
}
