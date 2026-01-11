// websocket.js - WebSocket and Server Communication

let wasDisconnected = false;
let healthWs = null;

async function fetchVersion() {
    try {
        const res = await fetch('/api/version');
        const data = await res.json();
        document.getElementById('versionBadge').textContent = `v${data.version}`;
    } catch (e) {
        document.getElementById('versionBadge').textContent = '-';
    }
}

function connectHealthCheck() {
    document.getElementById('serverStatus').className = 'server-status reconnecting';
    document.getElementById('serverStatus').querySelector('.status-text').textContent = 'Connecting...';
    state.serverStatus = 'connecting';

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    healthWs = new WebSocket(`${protocol}//${location.host}/ws/health`);

    healthWs.onopen = () => {
        document.getElementById('serverStatus').className = 'server-status connected';
        document.getElementById('serverStatus').querySelector('.status-text').textContent = 'Connected';
        state.serverStatus = 'connected';

        fetchVersion();

        if (!stateLoaded) {
            stateLoaded = true;
            loadState();
        } else if (wasDisconnected) {
            const allTerminals = getAllTerminals();
            if (allTerminals.length > 0) {
                showToast('Server reconnected. Restoring terminals...', 'success');
                reconnectAllTerminals();
            }
        }

        wasDisconnected = false;
    };

    healthWs.onclose = () => {
        document.getElementById('serverStatus').className = 'server-status disconnected';
        document.getElementById('serverStatus').querySelector('.status-text').textContent = 'Disconnected';
        state.serverStatus = 'disconnected';
        wasDisconnected = true;
        healthWs = null;
        setTimeout(connectHealthCheck, 2000);
    };

    healthWs.onerror = () => {
        if (healthWs) healthWs.close();
    };
}

async function restartServer() {
    if (!confirm('Are you sure you want to restart the server? All terminals will be disconnected.')) return;

    showToast('Restarting server...', 'warning');
    try {
        await fetch('/api/restart', { method: 'POST' });

        for (let i = 0; i < 15; i++) {
            await new Promise(r => setTimeout(r, 1000));
            try {
                const res = await fetch('/api/version', { signal: AbortSignal.timeout(2000) });
                if (res.ok) {
                    showToast('Server restarted! Reloading...', 'success');
                    setTimeout(() => location.reload(), 500);
                    return;
                }
            } catch (e) {
                console.log(`Reconnect attempt ${i + 1}/15...`);
            }
        }
        showToast('Server restart timeout - please refresh manually', 'warning');
    } catch (e) {
        showToast('Failed to trigger restart', 'error');
    }
}
