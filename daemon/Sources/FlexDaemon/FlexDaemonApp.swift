import AppKit
import AXSwift

public class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem?
    private var appMonitor: AppMonitor?
    private var accessibilityManager: AccessibilityManager?
    private var isPaused = false
    private var monitoredApps: [MonitoredApp] = []
    private var authToken: String?
    private var coordinator: OnboardingCoordinator?

    private static let pollingIntervals: [(label: String, interval: TimeInterval)] = [
        ("1s", 1.0),
        ("5s", 5.0),
        ("10s", 10.0),
        ("20s", 20.0),
    ]
    private var selectedPollingInterval: TimeInterval = 1.0

    public override init() {
        super.init()
    }

    public func applicationDidFinishLaunching(_ notification: Notification) {
        coordinator = OnboardingCoordinator()
        coordinator?.start { [weak self] token in
            self?.startDaemon(token: token)
        }
    }

    public func startDaemon(token: String) {
        authToken = token
        coordinator = nil

        setupStatusItem()

        accessibilityManager = AccessibilityManager()

        appMonitor = AppMonitor { [weak self] runningApps in
            self?.monitoredApps = runningApps
            self?.accessibilityManager?.updateMonitoredApps(runningApps)
            self?.rebuildMenu()
        }
        appMonitor?.start()
    }

    private func stopDaemon() {
        appMonitor?.stop()
        appMonitor = nil
        accessibilityManager?.pause()
        accessibilityManager = nil
        monitoredApps = []
        isPaused = false

        if let item = statusItem {
            NSStatusBar.system.removeStatusItem(item)
            statusItem = nil
        }
    }

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = statusItem?.button {
            button.image = NSImage(systemSymbolName: "eye", accessibilityDescription: "Flex Daemon")
        }
        rebuildMenu()
    }

    private func rebuildMenu() {
        guard let statusItem = statusItem else { return }
        let menu = NSMenu()

        if monitoredApps.isEmpty {
            let item = NSMenuItem(title: "No target apps detected", action: nil, keyEquivalent: "")
            item.isEnabled = false
            menu.addItem(item)
        } else {
            let header = NSMenuItem(title: "Monitored Apps", action: nil, keyEquivalent: "")
            header.isEnabled = false
            menu.addItem(header)

            for app in monitoredApps.sorted(by: { $0.name < $1.name }) {
                let item = NSMenuItem(title: app.name, action: #selector(toggleApp(_:)), keyEquivalent: "")
                item.target = self
                item.representedObject = app.bundleId
                if let manager = accessibilityManager, manager.enabledApps.contains(app.bundleId) {
                    item.state = .on
                } else {
                    item.state = .off
                }
                menu.addItem(item)
            }
        }

        menu.addItem(NSMenuItem.separator())

        // Polling interval submenu
        let pollingItem = NSMenuItem(title: "Polling Interval", action: nil, keyEquivalent: "")
        let pollingSubmenu = NSMenu()
        for option in Self.pollingIntervals {
            let item = NSMenuItem(title: option.label, action: #selector(setPollingInterval(_:)), keyEquivalent: "")
            item.target = self
            item.representedObject = option.interval
            item.state = option.interval == selectedPollingInterval ? .on : .off
            pollingSubmenu.addItem(item)
        }
        pollingItem.submenu = pollingSubmenu
        menu.addItem(pollingItem)

        menu.addItem(NSMenuItem.separator())

        let pauseTitle = isPaused ? "Resume Monitoring" : "Pause Monitoring"
        let pauseItem = NSMenuItem(title: pauseTitle, action: #selector(togglePause), keyEquivalent: "p")
        pauseItem.target = self
        menu.addItem(pauseItem)

        menu.addItem(NSMenuItem.separator())

        let logoutItem = NSMenuItem(title: "Log Out", action: #selector(logOut), keyEquivalent: "")
        logoutItem.target = self
        menu.addItem(logoutItem)

        let quitItem = NSMenuItem(title: "Quit Flex Daemon", action: #selector(quit), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    @objc private func toggleApp(_ sender: NSMenuItem) {
        guard let bundleId = sender.representedObject as? String else { return }
        guard let manager = accessibilityManager else { return }
        let isCurrentlyEnabled = manager.enabledApps.contains(bundleId)
        manager.setEnabled(bundleId: bundleId, enabled: !isCurrentlyEnabled)
        rebuildMenu()
    }

    @objc private func setPollingInterval(_ sender: NSMenuItem) {
        guard let interval = sender.representedObject as? TimeInterval else { return }
        selectedPollingInterval = interval
        accessibilityManager?.setPollingInterval(interval)
        rebuildMenu()
    }

    @objc private func togglePause() {
        isPaused.toggle()
        if isPaused {
            accessibilityManager?.pause()
            print("[FlexDaemon] Monitoring paused")
        } else {
            accessibilityManager?.resume()
            print("[FlexDaemon] Monitoring resumed")
        }
        rebuildMenu()
    }

    @objc private func logOut() {
        KeychainHelper.deleteToken()
        authToken = nil
        stopDaemon()

        coordinator = OnboardingCoordinator()
        coordinator?.start { [weak self] token in
            self?.startDaemon(token: token)
        }
    }

    @objc private func quit() {
        NSApplication.shared.terminate(nil)
    }
}
