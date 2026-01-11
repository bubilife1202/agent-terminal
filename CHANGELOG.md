# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
