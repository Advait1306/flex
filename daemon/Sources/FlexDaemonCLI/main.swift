import AppKit
import AXSwift
import CryptoKit
import FlexDaemon

DotEnv.load()

// --tree <name>: print text tree of a running app and exit (local-only, no login)
// Usage: ./daemon.sh --tree Slack
//        ./daemon.sh --tree Safari
//        ./daemon.sh --tree "Google Chrome"
//        ./daemon.sh --tree "Google Chrome" --all-tabs
if let treeIdx = CommandLine.arguments.firstIndex(of: "--tree") {
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)

    guard UIElement.isProcessTrusted(withPrompt: false) else {
        print("Error: Accessibility permission not granted.")
        print("Grant access in System Settings → Privacy & Security → Accessibility, then retry.")
        exit(1)
    }

    guard treeIdx + 1 < CommandLine.arguments.count else {
        print("Usage: daemon --tree <AppName> [--all-tabs]")
        print("Example: daemon --tree Slack")
        print("         daemon --tree \"Google Chrome\" --all-tabs")
        exit(1)
    }
    let appName = CommandLine.arguments[treeIdx + 1]
    let allTabs = CommandLine.arguments.contains("--all-tabs")
    let rawMode = CommandLine.arguments.contains("--raw")

    // Strip non-printable / Unicode control characters for comparison
    func normalize(_ s: String) -> String {
        s.unicodeScalars.filter { !$0.properties.isDefaultIgnorableCodePoint && $0.properties.isXIDContinue || $0 == " " }
            .map { String($0) }.joined().lowercased()
    }

    // Find the app by name (case-insensitive, ignoring invisible Unicode chars)
    let needle = normalize(appName)
    guard let runningApp = NSWorkspace.shared.runningApplications.first(where: {
        guard let name = $0.localizedName else { return false }
        return normalize(name) == needle
    }) else {
        print("App '\(appName)' not found. Running apps:")
        let apps = NSWorkspace.shared.runningApplications
            .compactMap { $0.localizedName }
            .sorted()
        for name in apps {
            print("  \(name)")
        }
        exit(1)
    }

    let pid = runningApp.processIdentifier
    let bundleId = runningApp.bundleIdentifier ?? "unknown"
    let category = AppClassifier.classify(bundleId: bundleId)
    let method: String
    switch category {
    case .electron: method = "AX tree (AXManualAccessibility)"
    case .safari:   method = "AX tree"
    case .chromium: method = "AppleScript (execute javascript)"
    case .generic:  method = "AX tree (best effort)"
    }
    print("App: \(runningApp.localizedName ?? appName) (pid \(pid), \(bundleId), \(category.rawValue))")
    print("Method: \(method)")

    // --raw: dump full AX tree with all roles (for debugging)
    if rawMode {
        if category == .electron {
            let axRef = AXUIElementCreateApplication(pid)
            AXUIElementSetAttributeValue(axRef, "AXManualAccessibility" as CFString, kCFBooleanTrue)
            Thread.sleep(forTimeInterval: 0.5)
        }
        print(String(repeating: "─", count: 60))
        let raw = AXTreeHelper.getRawTree(pid: pid)
        if raw.isEmpty {
            print("(no AX tree found)")
        } else {
            print(raw)
        }
        exit(0)
    }

    switch category {
    case .electron:
        // Enable AX tree for Electron apps
        let axRef = AXUIElementCreateApplication(pid)
        AXUIElementSetAttributeValue(axRef, "AXManualAccessibility" as CFString, kCFBooleanTrue)
        Thread.sleep(forTimeInterval: 0.5)

        let windows = AXTreeHelper.getPerWindowTextTrees(pid: pid)
        if windows.isEmpty {
            print("(no text content found)")
        } else {
            for (i, window) in windows.enumerated() {
                if i > 0 { print("") }
                print("Window: \(window.title)")
                print(String(repeating: "─", count: 60))
                print(window.text)
                let hash = SHA256.hash(data: Data(window.text.utf8))
                let short = hash.prefix(8).map { String(format: "%02x", $0) }.joined()
                print(String(repeating: "─", count: 60))
                print("Hash: \(short)...")
            }
        }

    case .safari, .generic:
        let windows = AXTreeHelper.getPerWindowTextTrees(pid: pid)
        if windows.isEmpty {
            print("(no text content found)")
        } else {
            for (i, window) in windows.enumerated() {
                if i > 0 { print("") }
                print("Window: \(window.title)")
                print(String(repeating: "─", count: 60))
                print(window.text)
                let hash = SHA256.hash(data: Data(window.text.utf8))
                let short = hash.prefix(8).map { String(format: "%02x", $0) }.joined()
                print(String(repeating: "─", count: 60))
                print("Hash: \(short)...")
            }
        }

    case .chromium:
        if allTabs {
            let tabs = ChromiumHelper.extractAllTabs(appName: runningApp.localizedName ?? appName)
            if tabs.isEmpty {
                print("(no tabs found)")
            } else {
                for (i, tab) in tabs.enumerated() {
                    if i > 0 { print("") }
                    print("Tab \(i + 1): \(tab.title)")
                    print("URL: \(tab.url)")
                    print(String(repeating: "─", count: 60))
                    if tab.text.isEmpty {
                        print("(no text content)")
                    } else {
                        print(tab.text)
                        let hash = SHA256.hash(data: Data(tab.text.utf8))
                        let short = hash.prefix(8).map { String(format: "%02x", $0) }.joined()
                        print(String(repeating: "─", count: 60))
                        print("Hash: \(short)...")
                    }
                }
            }
        } else {
            if let tab = ChromiumHelper.extractActiveTab(appName: runningApp.localizedName ?? appName) {
                print("Tab: \(tab.title)")
                print("URL: \(tab.url)")
                print(String(repeating: "─", count: 60))
                if tab.text.isEmpty {
                    print("(no text content)")
                } else {
                    print(tab.text)
                    let hash = SHA256.hash(data: Data(tab.text.utf8))
                    let short = hash.prefix(8).map { String(format: "%02x", $0) }.joined()
                    print(String(repeating: "─", count: 60))
                    print("Hash: \(short)...")
                }
            } else {
                print("(could not extract active tab — is the browser open?)")
            }
        }
    }

    exit(0)
}

// Normal daemon mode: onboarding → login → accessibility → menu bar
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
