# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.7] - 2026-01-14

### Fixed
- **Ctrl+V Double Paste**: Fixed clipboard paste being executed twice
  - Added `isPasting` flag to prevent duplicate paste events
  - Send paste data directly via WebSocket instead of `term.paste()`
- **Korean IME Input**: Improved handling of Korean/CJK character composition
  - Track `compositionstart`, `compositionupdate`, `compositionend` events
  - Prevent sending incomplete characters during IME composition
  - Send composed text only after composition completes

### Changed
- **PTY Environment Variables**: Added proper terminal environment settings
  - Set `TERM=xterm-256color` for correct terminal capability detection
  - Set `COLORTERM=truecolor` for full color support
  - Set `LANG` for proper locale handling
  - May improve TUI app rendering (OpenCode, Gemini CLI, etc.)

## [1.7.5] - 2026-01-13

### Added
- **Connection Status Indicator**: Each terminal header now shows connection status
  - 🟢 Green: Connected
  - 🟡 Yellow (blinking): Connecting
  - 🔴 Red: Disconnected
  - Hover for tooltip with status details

### Changed
- **Manual Session Restart**: Disabled automatic reconnection on network restore
  - Previous content preserved when connection drops
  - User must click ↻ to start new session (allows reviewing previous work)
  - Shows "[Connection lost. Click ↻ to start new session.]" message

### Removed
- **Auto-Continue Button**: Removed non-functional Auto button from terminal header

## [1.7.4] - 2026-01-12

### Changed
- **Max Projects Increased**: Increased maximum simultaneous projects from 5 to 10
  - `MAX_PROJECTS` constant updated in `state.js`

## [1.7.3] - 2026-01-12

### Fixed
- **Session "already in use" Error**: Fixed Claude CLI session conflict after server restart
  - Page reload now creates new session IDs instead of reusing old ones
  - Restart Session (↻) button generates new session ID
  - Server reconnect creates new session IDs for all terminals
  - Prevents "Session ID xxx is already in use" error

### Changed
- `loadState()` now passes `null` to `createTerminal()` to generate fresh UUIDs
- `restartTerminal()` generates new UUID and updates all UI element references
- `reconnectAllTerminals()` generates new UUIDs for all terminals on reconnect

## [1.6.0] - 2026-01-11

### Added
- **File Preview Modal**: Click any file in sidebar to preview contents
  - Markdown files rendered beautifully (headings, lists, code blocks, tables)
  - Code files with syntax highlighting (Tokyo Night theme via highlight.js)
  - ESC / click outside / X button to close
  - Copy path button in modal header
  - Error handling for binary files and large files (>1MB limit)
- **Parent Folder Navigation**: Added ⬆ button in File Explorer header
  - Click to navigate to parent directory
  - Works with current browsing path, not just project root
- **Project Agent Selection**: When opening a new folder, shows agent selection cards
  - Select which agent (Claude, Gemini, Codex, OpenCode, Shell) to start
  - Cards reappear when all terminals are closed
- **File Type Icons**: Enhanced file icons in explorer
  - Different icons per file type (📝 md, 🐍 py, 🟨 js, 🔷 ts, etc.)
  - Visual distinction between file types at a glance

### Technical
- New API endpoint: `/api/file-content` for reading file contents
- Added marked.js CDN for markdown rendering
- Added highlight.js CDN with Tokyo Night theme
- New CSS: `.file-preview-modal`, `.file-preview-markdown`, `.project-empty-state`
- New functions: `openFilePreview()`, `closeFilePreview()`, `navigateToParent()`, `updateProjectEmptyState()`

## [1.5.0] - 2026-01-11

### Changed
- **Architecture Modernization**: Complete frontend modularization
  - `templates/index.html` reduced from 2,066 lines to 201 lines (90% reduction)
  - CSS extracted to `static/css/style.css` (722 lines)
  - JavaScript split into 5 modular files:
    - `static/js/state.js` - Configuration and state management (166 lines)
    - `static/js/terminal.js` - Terminal creation and WebSocket handling (318 lines)
    - `static/js/ui.js` - UI rendering, modals, layout management (454 lines)
    - `static/js/websocket.js` - Health check and server communication (83 lines)
    - `static/js/main.js` - Application entry point (38 lines)
  - Added static file serving via FastAPI StaticFiles middleware

### Benefits
- Improved maintainability with separated concerns
- Better cacheability of static assets
- Easier debugging and testing
- Foundation for future framework migration (React/Vue)

## [1.4.7] - 2026-01-11

### Fixed
- **Terminal half-screen rendering (ACTUAL FIX)**: Missing CSS for `#projectContents`
  - Added `flex: 1`, `display: flex`, `flex-direction: column`, `min-height: 0` to `#projectContents`
  - This was the ROOT CAUSE - container had no height!

## [1.4.6] - 2026-01-11

### Fixed
- **Terminal half-screen rendering (FINAL FIX)**: Complete CSS overhaul for flexbox layout
  - Added `min-height: 0` to ALL flex children (critical for proper sizing)
  - Added `height: 100%` to html, body, grid-container, project-content, term-cell
  - Added `grid-template-rows: 1fr` to all grid layouts
  - Added `overflow: hidden` to prevent content overflow
  - Force xterm to fill container with `height: 100% !important`

## [1.4.5] - 2026-01-11

### Added
- **Auto-layout**: Layout automatically adjusts based on terminal count
  - 1 terminal → full width (layout 1)
  - 2 terminals → side by side (layout 2)
  - 3-4 terminals → 2x2 grid (layout 4)

### Fixed
- **File explorer not clearing**: Now clears when all projects are closed
- **Terminal half-screen rendering**: Improved fit() with smart sizing
  - Added `smartFit()` that checks container has actual size before fitting
  - ResizeObserver now only fits when container width/height > 0
  - Added more delayed fit attempts (up to 1000ms)

## [1.4.4] - 2026-01-11

### Added
- **Version display**: Shows version badge (v1.4.4) in header next to title

### Fixed
- **Drive icon duplication**: Removed duplicate 💾 icon in folder picker (was showing "💾 💾 C:")
- **Console window issues on restart**: 
  - Fixed double console window opening on server restart
  - Fixed old console not closing (now uses `exit` instead of `exit /b`)
  - Added RESTART_MODE to prevent browser reopening on restart
- **Black terminal screen**: 
  - Agent card click now auto-creates terminal after folder selection
  - Added more fit() delays (100ms, 300ms, 500ms) for reliable initial render
  - Added `pendingAgentType` to track agent selection through folder picker flow

## [1.4.3] - 2026-01-11

### Fixed
- **Memory leak**: ResizeObserver now properly disconnected when terminal closes
- **XSS vulnerability**: Path strings now HTML-escaped in project tabs and history
- **Project name parsing**: Fixed "D:\" showing as empty string (now shows "D:")
- **WebSocket cleanup**: All handlers (onopen/onclose/onerror/onmessage) cleared on reconnect
- **Terminal fit timing**: Multiple fit() calls with delays for reliable initial render
- **Connection status**: Shows "Connecting..." before actual connection (not "Connected")
- **State restoration**: Terminals properly reconnect after server restart

### Changed
- **saveState debounce**: Added 500ms debounce to reduce localStorage writes
- **localStorage version**: Bumped to v4 (clears old data for fresh start)

### Added
- `clearAllData()` function for manual data reset
- `saveStateLater()` debounced save function

## [1.4.2] - 2026-01-11

### Changed
- **Header UI redesign**
  - Moved "New Terminal" button to header-actions group (more logical position)
  - Layout buttons now use visual SVG icons instead of confusing "1/2/4" numbers
  - Added `.btn-group` styling for layout buttons with active state
  - Added dividers between button groups for clearer separation

### Fixed
- **Server restart opens new console**: Restart now closes old console and opens fresh one
  - Uses flag file (`.restart-new-console`) to signal new console mode
  - Old console exits cleanly, new one opens with start.bat
- **Session ID conflict on restore**: Always generate new UUIDs when restoring terminals
  - Prevents "Session ID already in use" errors from Claude CLI
  - Old session IDs are not reused to avoid conflicts with Claude's internal tracking

## [1.4.1] - 2026-01-11

### Fixed
- **Terminal connection retry**: Added automatic retry mechanism with exponential backoff
  - Up to 5 retry attempts (1s, 2s, 3s, 4s, 5s delays)
  - Clear feedback messages during reconnection
  - Prevents "[Connection Error]" spam after server restart
  - Shows helpful message after max retries exceeded
- **Session restoration after restart**: Terminals now properly reconnect after server restart

## [1.4.0] - 2026-01-11

### Changed
- **UI/UX Complete Redesign**
  - Header simplified: buttons grouped into logical sections
  - Folder/File buttons grouped together
  - Layout buttons grouped together with SVG icons
  - Server restart and reset moved to ⚙️ dropdown menu
  - Agent Dock now uses popover for role selection
  - Click Agent icon to see options (start with role / change role / stop)
  - Removed standalone Agent Select Modal (replaced by inline popover)

### Removed
- Dead code cleanup: `addAgent()`, `openAgentSelectModal()`, `confirmAgentSelect()` functions
- Agent Select Modal HTML removed (functionality moved to Agent Dock popover)

### Fixed
- **Server restart now opens new console window**: Clicking restart in ⚙️ menu always opens a fresh console

### Added
- Settings dropdown menu (⚙️) with: Server restart, Session reset, Keyboard shortcuts, About
- `closeAllPopovers()` function for managing popover state
- Click-outside handlers for closing popovers and dropdowns
- `startAgentWithRole()`, `changeAgentRole()`, `stopAgent()` for Agent Dock operations

## [1.3.4] - 2026-01-11

### Fixed
- **Server restart console closing**: Console window now stays open after restart
  - Added RESTART_LOOP in start.bat to auto-restart server when process exits
  - Simplified server.py restart logic - just exits, start.bat handles restart
  - Removed subprocess.Popen with CREATE_NO_WINDOW (caused invisible server)
  - Console remains visible for monitoring and logs

## [1.3.3] - 2026-01-11

### Fixed
- **Server restart**: Major reliability improvements
  - Replaced `os._exit(0)` with `sys.exit(0)` for proper shutdown_event trigger
  - Removed duplicate window flags (CREATE_NO_WINDOW only)
  - Added stdin/stdout/stderr redirect to DEVNULL
  - Added 1 second delay before exit for new process startup
- **Image paste**: Fixed file extension mismatch
  - Now uses correct extension based on MIME type (.jpg, .gif, .webp)
  - Added WebSocket send() error handling
  - Improved permissions.query() browser compatibility
- **Restart reconnection**: Improved retry logic
  - Changed from fixed 3s wait to 10-retry loop (1s intervals)
  - Auto-reload on successful reconnection

## [1.3.2] - 2026-01-11

### Fixed
- **Restart endpoint**: Added TERMINAL_IMPORT_ERROR check before restart
  - Returns 503 error if terminal module not loaded
  - Prevents crash when pywinpty is missing
- **WebSocket handler**: Fixed parameter name mismatch in function call
  - Changed positional args to explicit keyword args (working_dir, agent_type)

## [1.3.1] - 2026-01-11

### Changed
- **Code structure**: Separated HTML/JS/CSS from server.py to templates/index.html
  - server.py reduced from ~2100 lines to ~315 lines
  - Frontend code now in dedicated template file
- **Mock Terminal**: Improved error handling when pywinpty is missing
  - Shows clear installation instructions in terminal
  - Console warning on server startup
  - User-friendly error messages instead of silent failure

### Added
- **README.md**: Comprehensive documentation with installation, usage, and API reference

## [1.3.0] - 2026-01-11

### Fixed
- **Session conflict loop**: Fixed "세션 충돌 감지" repeating infinitely
  - Always generate new UUID on restore (no reuse of old session IDs)
  - Conflict detection now only checks current message (not buffer)
  - Added `handlingSessionConflict` flag check before processing
- **Server restart console**: Fixed new console window opening on restart
  - Windows: Now uses `CREATE_NO_WINDOW` instead of `CREATE_NEW_CONSOLE`
  - Server restarts silently in background
- **Image paste improvements**:
  - Added clipboard permission check with user feedback
  - Added image format validation (PNG, JPEG, GIF, WebP only)
  - Added file size limit (50MB) with error message
  - Improved error messages for permission denied, network errors
  - Backend: Added base64 validation and size limit check
  - Backend: UUID added to temp filename to prevent overwrites
- **SessionManager concurrency**: Fixed dictionary iteration during modification
  - `broadcast()` and `send_direct()` now use dict copies
  - Dead sessions are auto-cleaned after failed sends
  - Duplicate session registration now closes old WebSocket first
- **Terminal duplication**: `createTerminal()` now checks for existing ID
  - Returns existing terminal instead of creating duplicate
- **Health check race condition**: Now skips terminals already reconnecting
  - Checks `reconnectTimeout` and `handlingSessionConflict` flags
  - Fixed server status not updating on response failure
- **taskkill timeout**: Added proper exception handling for Windows process kill

### Added
- **Shutdown handler**: `@app.on_event("shutdown")` cleans up all sessions
  - PTY processes properly terminated on server stop (Ctrl+C)

## [1.2.3] - 2026-01-11

### Fixed
- **Layout restore bug**: Server restart now correctly restores layout based on terminal count
- **Performance**: Major rendering optimizations to fix terminal lag
  - Disabled `cursorBlink` to reduce DOM repaints
  - WebSocket message batching with `requestAnimationFrame`
  - `window.onresize` debounce increased to 300ms with proper clearTimeout
  - `ResizeObserver` debounce: fit() 50ms, resize message 500ms
  - PTY read loop: `sleep(0.001)` active, `sleep(0.05)` idle (was 0/0.01)
- **Edge cases**: Improved robustness
  - `onmessage` now ignores messages after `dispose()`
  - RAF callback wrapped in try-catch-finally for safe cleanup
  - `onclose` clears message queue to prevent memory buildup

### Changed
- **Max terminals reduced to 4** (was 6) - cleaner 2x2 grid layout
- Removed 6-column layout button from UI
- `autoUpdateLayout()` max layout is now 4 (2x2 grid)

## [1.2.2] - 2026-01-11

### Added
- **Auto-sync layout**: Terminal count automatically adjusts grid layout and button state
  - 1 terminal: full screen (cols-1), button [1] active
  - 2 terminals: horizontal split (cols-2), button [2] active
  - 3~4 terminals: 2x2 grid (cols-4), button [4] active
- `autoUpdateLayout()` function called on terminal add/remove

### Fixed
- **Critical**: Background project restore now correctly adds terminals to their own project (not active project)
- `createTerminal()` and `AgentTerminal` constructor now accept explicit `projectHash` parameter
- `restoreProjectSession()` passes `projectHash` explicitly to prevent cross-project terminal mixing
- Memory leak: `ResizeObserver` now stored and disconnected on terminal dispose
- Memory leak: `stableConnectionTimer` now cleared on terminal dispose
- URL hash fallback now uses saved `workDir` from session state when not found in `recentProjects`
- `terminal.py`: Changed `_temp_files` from `list` to `set` to prevent duplicate path tracking
- `terminal.py`: Thread-safety improvement - copy set before iteration in `stop()` method

## [1.2.1] - 2026-01-11

### Fixed
- Layout restoration bug: projects no longer reset to 6-column layout after server restart
- `createProjectGrid()` now accepts `layoutCols` parameter for correct initial layout
- `restoreProjectSession()` only adds `active` class to the actual active project
- Init code pre-loads saved `layoutCols` before creating project grid elements

## [1.2.0] - 2026-01-11

### Added
- **Multi-project parallel work**: Run multiple projects simultaneously without closing terminals
- Project tabs bar at top of terminal area for quick switching
- Each project maintains independent terminals, layout, and state
- Open projects restored on page reload
- Maximum 5 projects can be open simultaneously (memory management)
- Close button on each project tab

### Changed
- Terminal state now stored per-project in `projects` object
- Project switching shows/hides terminal grids instead of disposing
- All terminal array references updated to use project-scoped functions
- Server restart now saves all open projects' states

### Technical
- New state: `projects = {}` replaces `terminals = []`
- New functions: `getActiveTerminals()`, `getAllTerminals()`, `getWorkDir()`
- New functions: `switchProject()`, `closeProject()`, `renderProjectTabs()`
- localStorage: Added `agent-terminal-open-projects` for multi-project tracking

## [1.1.3] - 2026-01-11

### Fixed
- Debounce resize events to prevent Claude CLI duplicate prompt display
- Remove duplicate initial resize from onopen (handled by ResizeObserver)

## [1.1.2] - 2026-01-11

### Added
- Auto-restore last used project on page load
- Last project hash saved to localStorage

## [1.1.1] - 2026-01-11

### Fixed
- Server restart now properly cleans up PTY processes before exit
- Root cause of session conflicts: `os._exit(0)` bypassed cleanup code
- Added `cleanup_all_sessions()` function called before restart

## [1.1.0] - 2026-01-11

### Added
- Project-specific URLs: each project gets unique URL with `?project={hash}`
- Per-project localStorage: session state saved separately for each project
- Project hash based on directory path for consistent identification

### Changed
- URL now reflects current project for bookmarking/sharing
- Sessions isolated per project (no more cross-project conflicts)

## [1.0.7] - 2026-01-11

### Fixed
- Double connection bug: prevent race condition between auto-reconnect and health check
- Restore original UUID for session continuity (session conflict detection handles conflicts)
- Force kill PTY process on Windows using taskkill /F /T for clean termination

## [1.0.6] - 2026-01-11

### Fixed
- Session conflict prevention: always generate new UUID on restore (never reuse old session IDs)
- Force kill PTY process on Windows using taskkill /F /T for clean termination

## [1.0.5] - 2026-01-11

### Changed
- Remove global role selector from header (role is now per-terminal only)
- New terminals default to "General" role, changeable in terminal header

## [1.0.4] - 2026-01-11

### Fixed
- Windows server restart now works automatically (no Enter key required)
- Uses subprocess.Popen with CREATE_NEW_CONSOLE instead of os.execv

## [1.0.3] - 2026-01-11

### Added
- Terminal numbering (#1, #2, etc.) in headers for easy identification
- Numbers in routing dropdown for inter-agent communication
- Source terminal number in routed messages

### Note
- Role selector was already per-terminal (not global)

## [1.0.2] - 2026-01-10

### Fixed
- Session conflict detection now works reliably (comprehensive ANSI stripping, case-insensitive matching, message buffering for split messages)
- Race condition between WebSocket onclose and session conflict handler resolved

## [1.0.1] - 2026-01-10

### Added
- Dynamic version display from API
- Terminal process closed detection with UI indicator
- Session ID migration (auto-convert old IDs to UUID format)
- File explorer click action (send path to terminal)
- Copy file path button in file explorer

### Fixed
- Session restoration now properly migrates non-UUID session IDs

## [1.0.0] - 2026-01-10

### Added
- Initial release
- Multi-agent terminal support (Claude, Gemini, Codex, OpenCode, Shell)
- Server connection status indicator (connected/reconnecting/disconnected)
- Server restart button with state preservation
- Per-terminal role selection (General/PM/Dev/QA)
- Agent-to-agent routing/communication
- Agent selection modal on new folder
- Session persistence (localStorage)
- Korean UI localization
- Version display in header
- Git version control setup
