import AppKit
import AXSwift

public class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private var appMonitor: AppMonitor!
    private var accessibilityManager: AccessibilityManager!
    private var isPaused = false

    public override init() {
        super.init()
    }

    public func applicationDidFinishLaunching(_ notification: Notification) {
        setupStatusItem()

        let diffEngine = DiffEngine()
        let outputPrinter = OutputPrinter()
        accessibilityManager = AccessibilityManager(diffEngine: diffEngine, outputPrinter: outputPrinter)

        appMonitor = AppMonitor { [weak self] runningApps in
            self?.accessibilityManager.updateMonitoredApps(runningApps)
            self?.updateMenu(monitoredApps: runningApps.map(\.name))
        }
        appMonitor.start()
    }

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = statusItem.button {
            button.image = NSImage(systemSymbolName: "eye", accessibilityDescription: "Flex Daemon")
        }
        updateMenu(monitoredApps: [])
    }

    func updateMenu(monitoredApps: [String]) {
        let menu = NSMenu()

        if monitoredApps.isEmpty {
            let item = NSMenuItem(title: "No target apps detected", action: nil, keyEquivalent: "")
            item.isEnabled = false
            menu.addItem(item)
        } else {
            let item = NSMenuItem(
                title: "Monitoring: \(monitoredApps.joined(separator: ", "))",
                action: nil, keyEquivalent: "")
            item.isEnabled = false
            menu.addItem(item)
        }

        menu.addItem(NSMenuItem.separator())

        let pauseTitle = isPaused ? "Resume Monitoring" : "Pause Monitoring"
        let pauseItem = NSMenuItem(title: pauseTitle, action: #selector(togglePause), keyEquivalent: "p")
        pauseItem.target = self
        menu.addItem(pauseItem)

        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(title: "Quit Flex Daemon", action: #selector(quit), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    @objc private func togglePause() {
        isPaused.toggle()
        if isPaused {
            accessibilityManager.pause()
            print("[FlexDaemon] Monitoring paused")
        } else {
            accessibilityManager.resume()
            print("[FlexDaemon] Monitoring resumed")
        }
        updateMenu(monitoredApps: appMonitor.currentAppNames())
    }

    @objc private func quit() {
        NSApplication.shared.terminate(nil)
    }
}
