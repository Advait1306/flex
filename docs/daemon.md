# Flex Daemon — Content Extraction

macOS menu bar daemon that extracts text content from running apps using the Accessibility (AX) API and AppleScript.

## App Categories

Every app is classified by bundle ID into one of four categories, each with a different extraction strategy:

| Category | Examples | Strategy |
|----------|----------|----------|
| **Electron** | Slack, Linear, VS Code, Discord, Figma, Notion | Set `AXManualAccessibility` on the process, then AX tree walk |
| **Safari** | Safari | AX tree walk directly (always exposed) |
| **Chromium** | Chrome, Brave, Edge, Arc, Vivaldi, Opera | AppleScript `execute javascript "document.body.innerText"` on tabs |
| **Generic** | Everything else (Dia, Finder, etc.) | AX tree walk as-is (best effort) |

Classification happens in `AppClassifier.classify(bundleId:)` which checks the bundle ID against known sets.

### Why the distinction?

- **Electron** apps embed Chromium but expose their AX tree only after `AXManualAccessibility` is set to true on the process. Without it, the tree is empty.
- **Safari** exposes its AX tree by default — no special setup needed.
- **Chromium** browsers don't respond to `AXManualAccessibility` (that's Electron-only). Instead, they support AppleScript with `execute javascript` to extract page content. This requires the user to enable "Allow JavaScript from Apple Events" in the browser's developer settings.
- **Generic** is the fallback — just walk whatever AX tree the app exposes. Works surprisingly well for many apps (e.g. Dia, a Chromium fork, exposes page content via AX tree without any special setup).

### AX Tree Extraction (`AXTreeHelper`)

Walks all windows of a process and produces a YAML-like indented text tree. Filters elements by role:

- **Text roles** (emitted as content): `AXStaticText`, `AXTextField`, `AXTextArea`, `AXLink`, `AXHeading`, `AXCell`
- **Context roles** (emitted as headers if named): `AXGroup`, `AXList`, `AXScrollArea`, `AXWebArea`

### Chromium AppleScript Extraction (`ChromiumHelper`)

Uses `NSAppleScript` (in-process, no subprocess) to talk to the browser. Two modes:

- **Active tab**: gets title, URL, and `document.body.innerText` from the front window's active tab
- **All tabs**: iterates all windows and tabs, gets title + URL + innerText for each

Uses delimiter-based output parsing (`<<<DELIM>>>`, `<<<FIELD>>>`, `<<<TAB>>>`) to pack multiple values into a single AppleScript return string.

## CLI Usage

```bash
# Build and run
./daemon.sh --tree <AppName> [--all-tabs]
```

### Examples

```bash
# Electron — sets AXManualAccessibility, then AX tree walk
./daemon.sh --tree Slack

# Safari — AX tree walk directly
./daemon.sh --tree Safari

# Chromium — AppleScript JS extraction (active tab)
./daemon.sh --tree "Google Chrome"

# Chromium — all tabs
./daemon.sh --tree "Google Chrome" --all-tabs

# Generic — AX tree best effort
./daemon.sh --tree Finder
./daemon.sh --tree Dia
```

The CLI auto-detects the app category from its bundle ID and prints it in the header:

```
App: Slack (pid 1234, com.tinyspeck.slackmacgap, electron)
```

### Output format

- **Electron/Safari/Generic**: window title + indented text tree
- **Chromium (default)**: tab title + URL + page text for active tab
- **Chromium (`--all-tabs`)**: same for every tab across all windows

## Known Limitations

### AX tree is empty for full-screen apps on other Spaces

macOS does not populate the Accessibility tree for windows that are in a full-screen Space other than the currently active one. This means `AXTreeHelper.getTextTree()` returns empty for apps like Slack or Safari when they're full-screened on a different desktop.

The app still appears as running and its window exists, but the tree has no children. Windowed mode (even minimized to the Dock) works fine — the limitation is specific to full-screen Spaces that aren't in the foreground.

This is a system-level limitation of the macOS Accessibility API, not something we can work around without bringing the app to the foreground. It affects all tools that use `AXUIElement` — see [alt-tab-macos #447](https://github.com/lwouis/alt-tab-macos/issues/447) and [Apple Developer Forums](https://developer.apple.com/forums/thread/121114) for discussion.

### Chromium `execute javascript` requires opt-in

Chrome (and other Chromium browsers that support it) require the user to manually enable "Allow JavaScript from Apple Events" via View > Developer. Without this, AppleScript JS extraction fails. Not all Chromium forks support this command at all (e.g. Dia doesn't expose `execute javascript` in its AppleScript dictionary).
