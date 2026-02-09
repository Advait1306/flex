import AppKit
import AXSwift
import FlexDaemon

let app = NSApplication.shared
app.setActivationPolicy(.accessory)

guard UIElement.isProcessTrusted(withPrompt: true) else {
    let alert = NSAlert()
    alert.messageText = "Accessibility Permission Required"
    alert.informativeText = "Flex Daemon needs Accessibility access to monitor Slack and Linear. Please grant access in System Settings → Privacy & Security → Accessibility, then relaunch."
    alert.alertStyle = .critical
    alert.addButton(withTitle: "Quit")
    alert.runModal()
    exit(1)
}

// --tree <name>: print text tree of a running app and exit
// Usage: ./daemon.sh --tree Slack
//        ./daemon.sh --tree Safari
//        ./daemon.sh --tree "Google Chrome"
//        ./daemon.sh --tree "Google Chrome" --all-tabs
if let treeIdx = CommandLine.arguments.firstIndex(of: "--tree") {
    guard treeIdx + 1 < CommandLine.arguments.count else {
        print("Usage: daemon --tree <AppName> [--all-tabs]")
        print("Example: daemon --tree Slack")
        print("         daemon --tree \"Google Chrome\" --all-tabs")
        exit(1)
    }
    let appName = CommandLine.arguments[treeIdx + 1]
    let allTabs = CommandLine.arguments.contains("--all-tabs")

    // Find the app by name (case-insensitive)
    guard let runningApp = NSWorkspace.shared.runningApplications.first(where: {
        $0.localizedName?.lowercased() == appName.lowercased()
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

    switch category {
    case .electron:
        // Enable AX tree for Electron apps
        let axRef = AXUIElementCreateApplication(pid)
        AXUIElementSetAttributeValue(axRef, "AXManualAccessibility" as CFString, kCFBooleanTrue)
        Thread.sleep(forTimeInterval: 0.5)

        let title = AXTreeHelper.windowTitle(pid: pid) ?? "(no window title)"
        print("Window: \(title)")
        print(String(repeating: "─", count: 60))

        let tree = AXTreeHelper.getTextTree(pid: pid)
        if tree.isEmpty {
            print("(no text content found)")
        } else {
            print(tree)
        }

    case .safari, .generic:
        let title = AXTreeHelper.windowTitle(pid: pid) ?? "(no window title)"
        print("Window: \(title)")
        print(String(repeating: "─", count: 60))

        let tree = AXTreeHelper.getTextTree(pid: pid)
        if tree.isEmpty {
            print("(no text content found)")
        } else {
            print(tree)
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
                }
            } else {
                print("(could not extract active tab — is the browser open?)")
            }
        }
    }

    exit(0)
}

let delegate = AppDelegate()
app.delegate = delegate
app.run()
