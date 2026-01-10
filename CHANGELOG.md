# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
