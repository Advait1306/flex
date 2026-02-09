import AppKit

public struct MonitoredApp {
    public let name: String
    public let bundleId: String
    public let pid: pid_t
}

public final class AppMonitor {
    private static let targetBundleIds: Set<String> = [
        "com.tinyspeck.slackmacgap",
        "com.linear",
    ]

    private var runningApps: [String: MonitoredApp] = [:]  // bundleId -> MonitoredApp
    private let onChange: ([MonitoredApp]) -> Void

    public init(onChange: @escaping ([MonitoredApp]) -> Void) {
        self.onChange = onChange
    }

    public func start() {
        // Scan already-running apps
        for app in NSWorkspace.shared.runningApplications {
            if let bundleId = app.bundleIdentifier, Self.targetBundleIds.contains(bundleId) {
                let name = app.localizedName ?? bundleId
                runningApps[bundleId] = MonitoredApp(name: name, bundleId: bundleId, pid: app.processIdentifier)
            }
        }
        notifyChange()

        let center = NSWorkspace.shared.notificationCenter
        center.addObserver(self, selector: #selector(appLaunched(_:)),
                           name: NSWorkspace.didLaunchApplicationNotification, object: nil)
        center.addObserver(self, selector: #selector(appTerminated(_:)),
                           name: NSWorkspace.didTerminateApplicationNotification, object: nil)
        center.addObserver(self, selector: #selector(appActivated(_:)),
                           name: NSWorkspace.didActivateApplicationNotification, object: nil)
    }

    public func currentAppNames() -> [String] {
        runningApps.values.map(\.name)
    }

    @objc private func appLaunched(_ notification: Notification) {
        guard let app = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication,
              let bundleId = app.bundleIdentifier,
              Self.targetBundleIds.contains(bundleId) else { return }

        let name = app.localizedName ?? bundleId
        runningApps[bundleId] = MonitoredApp(name: name, bundleId: bundleId, pid: app.processIdentifier)
        print("[FlexDaemon] \(name) launched (pid \(app.processIdentifier))")
        notifyChange()
    }

    @objc private func appTerminated(_ notification: Notification) {
        guard let app = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication,
              let bundleId = app.bundleIdentifier,
              Self.targetBundleIds.contains(bundleId) else { return }

        let name = runningApps[bundleId]?.name ?? bundleId
        runningApps.removeValue(forKey: bundleId)
        print("[FlexDaemon] \(name) quit")
        notifyChange()
    }

    @objc private func appActivated(_ notification: Notification) {
        guard let app = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication,
              let bundleId = app.bundleIdentifier,
              Self.targetBundleIds.contains(bundleId) else { return }

        print("[FlexDaemon] \(app.localizedName ?? bundleId) activated")
    }

    private func notifyChange() {
        onChange(Array(runningApps.values))
    }
}
