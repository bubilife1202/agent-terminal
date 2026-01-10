# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
