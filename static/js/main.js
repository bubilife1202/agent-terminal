// main.js - Application Entry Point

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Agent UI
    initAgentUI();
    
    // Connect to health check WebSocket
    connectHealthCheck();

    // Global Keybindings
    window.addEventListener('keydown', (e) => {
        // Ctrl+Shift+R: Restart server
        if (e.ctrlKey && e.shiftKey && e.key === 'R') {
            e.preventDefault();
            restartServer();
        }

        // Layout shortcuts: Alt + 1/2/4
        if (e.altKey && !e.ctrlKey && !e.shiftKey) {
            if (e.key === '1') {
                e.preventDefault();
                setLayout(1);
                showToast('Layout: 1 column', 'success');
            } else if (e.key === '2') {
                e.preventDefault();
                setLayout(2);
                showToast('Layout: 2 columns', 'success');
            } else if (e.key === '4') {
                e.preventDefault();
                setLayout(4);
                showToast('Layout: 2x2 grid', 'success');
            }
        }
    });

    // Window resize handler
    window.addEventListener('resize', () => fitAllTerminals());
});
