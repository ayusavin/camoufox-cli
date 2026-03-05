# camoufox-cli — Anti-detect Browser CLI for AI Agents

## What This Is

A CLI wrapper around Camoufox (anti-detect Firefox browser) that provides agent-browser-style commands for AI agent interaction. The key value prop: **anti-detect browsing with a simple CLI interface** — no Python scripts needed.

## Why It Exists

- **agent-browser** (Playwright Chromium) is great for AI agents but gets blocked by sites that detect `navigator.webdriver=true`
- **Camoufox** has C++-level fingerprint spoofing (`webdriver=false`, fake plugins, etc.) but only has a Python API — requires writing scripts for each interaction
- **No CLI exists** that combines Camoufox's anti-detection with agent-browser's "snapshot → interact → re-snapshot" workflow

## Target User

AI agents (Claude, GPT, etc.) that need to browse the web via CLI tool calls. The CLI should be optimized for:
- Minimal output (token-efficient)
- Ref-based interaction (`@e1`, `@e2`) — look at element, then act on it by ref
- Persistent sessions — browser stays open between commands

## Architecture

```
┌─────────┐     Unix Socket      ┌──────────────┐     Playwright      ┌───────────┐
│   CLI   │ ──────────────────> │   Daemon     │ ───────────────── │ Camoufox  │
│  (camoufox-cli) │ <────────────────── │  (Python)    │ <───────────────── │ (Firefox)  │
└─────────┘     JSON response   └──────────────┘                    └───────────┘
```

### Components

1. **CLI entry point** (`camoufox-cli`): Python client. Parses args, sends JSON command to daemon via Unix socket, prints response.
2. **Daemon** (`python -m camoufox_cli`): Long-running Python process. Manages Camoufox browser instance, handles commands, maintains ref registry. Auto-spawned by CLI on first command.
3. **Ref Registry**: Maps `@e1`, `@e2` refs to Playwright locators. Rebuilt on each `snapshot`.

### Session Management

- Default session: `default`
- Named sessions: `camoufox-cli --session mysession open https://...`
- Socket path: `/tmp/camoufox-cli-{session}.sock`
- PID file: `/tmp/camoufox-cli-{session}.pid`
- Auto-start: If daemon not running, CLI spawns it as background process
- Auto-shutdown: Daemon exits after 30 min idle (configurable via `--timeout`)

## Commands

### Navigation

```bash
camoufox-cli open <url>                    # Navigate to URL (starts daemon if needed)
camoufox-cli back                          # Go back
camoufox-cli forward                       # Go forward
camoufox-cli reload                        # Reload page
camoufox-cli close                         # Close browser and stop daemon
camoufox-cli url                           # Print current URL
camoufox-cli title                         # Print page title
```

### Snapshot (Core Feature)

```bash
camoufox-cli snapshot                      # Full aria tree of page
camoufox-cli snapshot -i                   # Interactive elements only (buttons, links, inputs, etc.)
camoufox-cli snapshot -s "css-selector"    # Scoped to CSS selector
```

**Output format** (matches agent-browser):
```
- link "About" [ref=e1]
- link "Gmail" [ref=e2]
- combobox "Search" [ref=e3]
- button "Google Search" [ref=e4]
- button "I'm Feeling Lucky" [ref=e5]
```

Refs are assigned sequentially per snapshot. Interactive-only mode (`-i`) filters to: `link`, `button`, `combobox`, `textbox`, `checkbox`, `radio`, `slider`, `switch`, `tab`, `menuitem`, `option`, `select`.

### Interaction (use refs from snapshot)

```bash
camoufox-cli click @e1                     # Click element
camoufox-cli fill @e3 "search query"       # Clear + type into input
camoufox-cli type @e3 "append text"        # Type without clearing
camoufox-cli select @e5 "option text"      # Select dropdown option
camoufox-cli check @e6                     # Toggle checkbox
camoufox-cli hover @e2                     # Hover over element
camoufox-cli press Enter                   # Press keyboard key
camoufox-cli press "Control+a"             # Key combination
```

### Data Extraction

```bash
camoufox-cli text @e1                      # Get text content of element
camoufox-cli text body                     # Get all page text (CSS selector)
camoufox-cli eval "document.title"         # Execute JavaScript
camoufox-cli screenshot                    # Screenshot to stdout (base64) or auto-save
camoufox-cli screenshot page.png           # Screenshot to file
camoufox-cli screenshot --full page.png    # Full page screenshot
camoufox-cli pdf output.pdf                # Save as PDF
```

### Scroll & Wait

```bash
camoufox-cli scroll down                   # Scroll down 500px
camoufox-cli scroll up                     # Scroll up 500px
camoufox-cli scroll down 1000              # Scroll down 1000px
camoufox-cli wait @e1                      # Wait for element to appear
camoufox-cli wait 2000                     # Wait milliseconds
camoufox-cli wait --url "*/dashboard"      # Wait for URL pattern
```

### Tab Management

```bash
camoufox-cli tabs                          # List open tabs
camoufox-cli switch 2                      # Switch to tab by index
camoufox-cli close-tab                     # Close current tab
```

### Session Management

```bash
camoufox-cli sessions                      # List active sessions
camoufox-cli --session work open <url>     # Use named session
camoufox-cli close --all                   # Close all sessions
```

### Cookies & State

```bash
camoufox-cli cookies                       # Dump cookies as JSON
camoufox-cli cookies import file.json      # Import cookies
camoufox-cli cookies export file.json      # Export cookies
```

## Global Flags

```
--session <name>       Named session (default: "default")
--headed               Show browser window (default: headless)
--timeout <seconds>    Daemon idle timeout (default: 1800)
--json                 Output as JSON instead of human-readable
--persistent <path>    Use persistent browser profile directory
```

## Implementation Details

### Tech Stack

- **Language**: Python 3.12 (already available at `/usr/local/Cellar/python@3.12/`)
- **Browser engine**: Camoufox (installed at `/Users/binhuang/.local/pipx/venvs/camoufox/`)
- **Camoufox Python API**: `from camoufox.sync_api import Camoufox` — wraps Playwright Firefox
- **IPC**: Unix domain sockets (JSON-line protocol)
- **Package**: Single Python package, installable via `pipx install .`

### Camoufox API Reference

```python
from camoufox.sync_api import Camoufox

# Basic launch
with Camoufox(headless=True) as browser:
    page = browser.new_page()
    page.goto("https://example.com")
    
    # aria_snapshot() returns accessibility tree as string
    # This is the basis for the snapshot command
    aria = page.locator("body").aria_snapshot()
    
    # Standard Playwright Page API works:
    page.click("button")
    page.fill("input", "text")
    page.evaluate("document.title")
    page.screenshot(path="shot.png")

# With persistent profile (keeps cookies/login state across restarts)
with Camoufox(headless=True, persistent_context=True, 
              user_data_dir="/path/to/profile") as context:
    # context is a BrowserContext, not Browser
    page = context.new_page()

# Key launch options:
# headless: True/False/None/"virtual"
# persistent_context: bool - use persistent profile
# user_data_dir: str - profile directory (with persistent_context)
# humanize: True/float - human-like mouse movements
# block_images: bool
# block_webrtc: bool  
# proxy: {"server": "http://host:port"}
# geoip: True - auto-set locale/timezone based on IP
```

### Ref System Implementation

The ref system maps `@e1`, `@e2` to elements:

1. `snapshot` calls `page.locator("body").aria_snapshot()` to get the full tree
2. Parse the tree text, assign sequential refs to each element
3. Store a mapping: `e1 -> "link 'About'"`, `e2 -> "combobox 'Search'"`, etc.
4. When user runs `camoufox-cli click @e1`, look up the aria role+name, use `page.get_by_role()` to find the element

**Key**: Use Playwright's `get_by_role()` for reliable element location:
```python
# For ref e1 which is: link "About"
page.get_by_role("link", name="About").click()

# For ref e3 which is: combobox "Search"  
page.get_by_role("combobox", name="Search").fill("query")
```

For elements with duplicate role+name (e.g., multiple "More actions" buttons), track the `nth` index.

### Daemon Protocol

CLI ↔ Daemon communicate via JSON-line over Unix socket:

**Request:**
```json
{"id": "r001", "action": "open", "params": {"url": "https://example.com"}}
{"id": "r002", "action": "snapshot", "params": {"interactive": true}}
{"id": "r003", "action": "click", "params": {"ref": "e1"}}
```

**Response:**
```json
{"id": "r001", "success": true, "data": {"url": "https://example.com", "title": "Example"}}
{"id": "r002", "success": true, "data": {"snapshot": "- link \"About\" [ref=e1]\n..."}}
{"id": "r003", "success": true}
```

**Error:**
```json
{"id": "r003", "success": false, "error": "Element @e1 not found. Run 'camoufox-cli snapshot' to refresh refs."}
```

### Daemon Lifecycle

```
camoufox-cli open https://example.com
  │
  ├── Check /tmp/camoufox-cli-default.sock exists?
  │   ├── YES → Connect, send command
  │   └── NO → Spawn daemon:
  │           python -m camoufox-cli.server --session default --headless &
  │           Wait for socket (up to 15s)
  │           Connect, send command
  │
  └── Print response
```

### Interactive-Only Filter

For `snapshot -i`, filter aria tree to only these roles:
- `link`, `button`, `combobox`, `textbox`, `textarea`
- `checkbox`, `radio`, `switch`, `slider`
- `tab`, `tabpanel`, `menuitem`, `option`
- `select`, `listbox`, `searchbox`
- `img` with alt text (sometimes clickable)

### Anti-Detection Features (from Camoufox)

These work automatically — no CLI flags needed:
- `navigator.webdriver` = `false`
- Real browser plugins (5+)
- Randomized fingerprint (canvas, WebGL, audio)
- Real Firefox UA string
- Human-like behavior (optional `--humanize` flag)

## Testing Plan

### Smoke Tests (must pass)

```bash
# 1. Basic lifecycle
camoufox-cli open https://example.com
camoufox-cli snapshot -i
camoufox-cli title
camoufox-cli close

# 2. Google search
camoufox-cli open https://www.google.com
camoufox-cli snapshot -i
camoufox-cli fill @e<search> "camoufox test"
camoufox-cli press Enter
camoufox-cli snapshot -i        # Should show search results

# 3. Anti-detection
camoufox-cli open https://bot.sannysoft.com/
camoufox-cli eval "navigator.webdriver"    # Should return "false"
camoufox-cli eval "navigator.plugins.length"  # Should return > 0

# 4. Twitter (agent-browser fails here)
camoufox-cli open https://x.com/elonmusk
camoufox-cli snapshot -i        # Should show profile info, not login wall

# 5. Session persistence
camoufox-cli --session test1 open https://example.com
camoufox-cli --session test2 open https://google.com
camoufox-cli sessions           # Should list both
camoufox-cli --session test1 title  # "Example Domain"
camoufox-cli close --all
```

## Project Structure

```
camoufox-cli/
├── pyproject.toml          # Package config (entry point: camoufox-cli)
├── README.md
├── package.json            # npm package config
├── src/
│   └── camoufox_cli/
│       ├── __init__.py
│       ├── __main__.py     # python -m camoufox_cli (daemon entry point)
│       ├── cli.py          # CLI argument parsing + socket client
│       ├── server.py       # Daemon: Unix socket server + lifecycle
│       ├── browser.py      # BrowserManager: Camoufox instance management
│       ├── refs.py         # Ref registry (aria tree → @e1 mapping)
│       ├── commands.py     # Command implementations (open, click, fill, etc.)
│       └── protocol.py     # JSON-line protocol helpers
```

## Environment Info

- **OS**: macOS (Darwin 24.1.0, x64)
- **Python 3.12**: `/usr/local/Cellar/python@3.12/3.12.12_1/`
- **Camoufox venv**: `/Users/binhuang/.local/pipx/venvs/camoufox/`
- **Camoufox version**: 0.4.11
- **Camoufox binary**: managed by camoufox package (auto-downloaded)
- **pipx**: available for installation

## Installation (after building)

```bash
cd camoufox-cli
pipx install . --python python3.12
# This makes `camoufox-cli` globally available
```

## Key Constraints

1. CLI startup must be fast (<100ms) — only stdlib imports in CLI client
2. Daemon handles all heavy imports (camoufox, playwright)
3. Output should be minimal and token-efficient for AI agents
4. Ref format must match agent-browser (`[ref=e1]`) for compatibility
5. Must work on macOS (primary target)
6. Camoufox is a dependency — don't vendor it, import from the existing pipx venv or declare as package dependency
