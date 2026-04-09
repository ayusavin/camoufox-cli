# camoufox-cli

Anti-detect browser CLI & Skills for AI agents, powered by [Camoufox](https://github.com/daijro/camoufox).

### Highlights

- C++-level fingerprint spoofing via Camoufox (canvas, WebGL, audio, screen metrics, fonts)
- Accessibility-tree snapshots with `@ref` element targeting
- Session isolation with cookie import/export
- **CapSolver integration** — auto-solves reCAPTCHA, hCaptcha, Cloudflare Turnstile
- Shell commands, no code generation

### Works with

Claude Code, Cursor, Codex, and any agent that can run shell commands.

## Install

### Agent Skill (recommended)

```bash
# Install the skill for Claude Code / Cursor / Codex
npx skills add ayusavin/camoufox-cli
```

Then tell your agent:

> Use camoufox-cli to automate the browser

Or tell it directly:

> Install this CLI and skills from https://github.com/ayusavin/camoufox-cli

### Manual install

```bash
# via npm (Node.js) — GitHub Packages
npm install -g @ayusavin/camoufox-cli
camoufox-cli install              # Download browser

# via pip (Python) — GitHub Packages
pip install --index-url https://pypi.pkg.github.com/ayusavin/simple/ camoufox-cli
camoufox-cli install              # Download browser

# Linux: also install system dependencies
camoufox-cli install --with-deps
```

### CapSolver setup (optional, for CAPTCHA auto-solving)

```bash
camoufox-cli capsolver-setup CAP-yourApiKeyHere   # API key from capsolver.com
camoufox-cli capsolver-status                      # verify
```

## Quick Start

```bash
camoufox-cli open https://example.com    # Launch browser & navigate
camoufox-cli snapshot -i                  # Interactive elements only
# - link "More information..." [ref=e1]
camoufox-cli click @e1                    # Click by ref
camoufox-cli close                        # Done
```

## Commands

### Navigation

```bash
camoufox-cli open <url>                   # Navigate to URL (starts daemon if needed)
camoufox-cli back                         # Go back
camoufox-cli forward                      # Go forward
camoufox-cli reload                       # Reload page
camoufox-cli url                          # Print current URL
camoufox-cli title                        # Print page title
camoufox-cli close                        # Close browser and stop daemon
```

### Snapshot

```bash
camoufox-cli snapshot                     # Full accessibility tree
camoufox-cli snapshot -i                  # Interactive elements only
camoufox-cli snapshot -s "css-selector"   # Scoped to CSS selector
```

Output format:

```
- heading "Example Domain" [level=1] [ref=e1]
- paragraph [ref=e2]
  - link "More information..." [ref=e3]
```

### Interaction

```bash
camoufox-cli click @e1                    # Click element
camoufox-cli fill @e3 "search query"      # Clear + type into input
camoufox-cli type @e3 "append text"       # Type without clearing
camoufox-cli select @e5 "option text"     # Select dropdown option
camoufox-cli check @e6                    # Toggle checkbox
camoufox-cli hover @e2                    # Hover over element
camoufox-cli press Enter                  # Press keyboard key
camoufox-cli press "Control+a"            # Key combination
camoufox-cli mouse-click 222 144          # Click by pixel coordinates
```

### Data Extraction

```bash
camoufox-cli text @e1                     # Get text content of element
camoufox-cli text body                    # Get all page text
camoufox-cli eval "document.title"        # Execute JavaScript
camoufox-cli screenshot                   # Screenshot (JSON with base64)
camoufox-cli screenshot page.png          # Screenshot to file
camoufox-cli screenshot --full page.png   # Full page screenshot
```

### Scroll & Wait

```bash
camoufox-cli scroll down                  # Scroll down 500px
camoufox-cli scroll up 1000               # Scroll up 1000px
camoufox-cli wait 2000                    # Wait milliseconds
camoufox-cli wait @e1                     # Wait for element to appear
camoufox-cli wait --url "*/dashboard"     # Wait for URL pattern
```

### Tabs

```bash
camoufox-cli tabs                         # List open tabs
camoufox-cli switch 2                     # Switch to tab by index
camoufox-cli close-tab                    # Close current tab
```

### Sessions

```bash
camoufox-cli sessions                     # List active sessions
camoufox-cli --session work open <url>    # Use named session
camoufox-cli close --all                  # Close all sessions
```

### Network Inspection

```bash
camoufox-cli requests                     # All captured requests (method, URL, status, headers, body)
camoufox-cli requests --filter "api/"     # Filter by URL substring
camoufox-cli requests --n 20              # Last 20 requests
camoufox-cli requests --json              # Full JSON output
camoufox-cli requests clear               # Clear buffer
```

### Cookies

```bash
camoufox-cli cookies                      # Dump cookies as JSON
camoufox-cli cookies import file.json     # Import cookies
camoufox-cli cookies export file.json     # Export cookies
```

### Setup

```bash
camoufox-cli install                      # Download Camoufox browser
camoufox-cli install --with-deps          # + system libs (Linux)
camoufox-cli capsolver-setup <api-key>    # Download CapSolver extension + save API key
camoufox-cli capsolver-status             # Show CapSolver configuration
```

## Flags

```
--session <name>       Named session (default: "default")
--headed               Show browser window (default: headless)
--timeout <seconds>    Daemon idle timeout (default: 1800)
--json                 Output as JSON
--persistent [path]    Use persistent browser profile (default: ~/.camoufox-cli/profiles/<session>)
--proxy <url>          Proxy server (e.g. http://host:port or http://user:pass@host:port)
```

## Architecture

```
CLI (camoufox-cli)  ──Unix socket──▶  Daemon (Python)  ──Playwright──▶  Camoufox (Firefox)
```

The CLI sends JSON commands to a long-running daemon process via Unix socket. The daemon manages the Camoufox browser instance and maintains the ref registry between commands. The daemon auto-starts on the first command and auto-stops after 30 minutes of inactivity.

## License

MIT
