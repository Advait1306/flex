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
//        ./daemon.sh --tree Linear
//        ./daemon.sh --tree "Google Chrome"
if let treeIdx = CommandLine.arguments.firstIndex(of: "--tree") {
    guard treeIdx + 1 < CommandLine.arguments.count else {
        print("Usage: daemon --tree <AppName>")
        print("Example: daemon --tree Slack")
        exit(1)
    }
    let appName = CommandLine.arguments[treeIdx + 1]

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
    print("App: \(runningApp.localizedName ?? appName) (pid \(pid), \(bundleId))")

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
    exit(0)
}

let delegate = AppDelegate()
app.delegate = delegate
app.run()
