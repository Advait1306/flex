import AppKit
import CryptoKit

public final class AccessibilityManager {
    private var pollingTimers: [String: Timer] = [:]           // bundleId -> timer
    private var categories: [String: AppCategory] = [:]        // bundleId -> category
    private var appNames: [String: String] = [:]               // bundleId -> display name
    private var pids: [String: pid_t] = [:]                    // bundleId -> pid
    private let hashStore = HashStore()
    private var isPaused = false
    public private(set) var enabledApps: Set<String> = []      // bundleId set

    /// Apps enabled by default on startup — others must be toggled on manually
    private static let defaultEnabledApps: Set<String> = [
        "com.tinyspeck.slackmacgap",   // Slack
        "com.linear",                   // Linear
        "net.whatsapp.WhatsApp",        // WhatsApp
    ]

    private var pollingInterval: TimeInterval = 1.0

    /// Called when content changes for an app: (appName, bundleId, content, category, contentHash)
    public var onContentChanged: ((String, String, String, AppCategory, String) -> Void)?

    public init() {
        hashStore.load()
    }

    public func updateMonitoredApps(_ apps: [MonitoredApp]) {
        let currentBundleIds = Set(apps.map(\.bundleId))
        let monitoredBundleIds = Set(categories.keys)

        // Detach apps that are no longer running
        for bundleId in monitoredBundleIds.subtracting(currentBundleIds) {
            detach(bundleId: bundleId)
        }

        // Attach new apps
        for app in apps where !monitoredBundleIds.contains(app.bundleId) {
            attach(app: app)
        }
    }

    public func setEnabled(bundleId: String, enabled: Bool) {
        if enabled {
            enabledApps.insert(bundleId)
            if !isPaused && categories[bundleId] != nil {
                startPolling(bundleId: bundleId)
            }
        } else {
            enabledApps.remove(bundleId)
            pollingTimers[bundleId]?.invalidate()
            pollingTimers.removeValue(forKey: bundleId)
        }
    }

    public func setPollingInterval(_ interval: TimeInterval) {
        pollingInterval = interval
        // Restart all active timers with the new interval
        let activeIds = Array(pollingTimers.keys)
        for bundleId in activeIds {
            startPolling(bundleId: bundleId)
        }
    }

    public func pause() {
        isPaused = true
        for (_, timer) in pollingTimers {
            timer.invalidate()
        }
        pollingTimers.removeAll()
    }

    public func resume() {
        isPaused = false
        for bundleId in categories.keys where enabledApps.contains(bundleId) {
            startPolling(bundleId: bundleId)
        }
    }

    // MARK: - Private

    private func attach(app: MonitoredApp) {
        let category = AppClassifier.classify(bundleId: app.bundleId)
        pids[app.bundleId] = app.pid
        categories[app.bundleId] = category
        appNames[app.bundleId] = app.name
        // Only auto-enable default apps; others are tracked but disabled until toggled on
        if Self.defaultEnabledApps.contains(app.bundleId) {
            enabledApps.insert(app.bundleId)
        }

        // Only Electron apps need AXManualAccessibility enabled
        if category == .electron {
            let axRef = AXUIElementCreateApplication(app.pid)
            AXUIElementSetAttributeValue(axRef, "AXManualAccessibility" as CFString, kCFBooleanTrue)
        }

        // Start polling only if the app is enabled
        if !isPaused && enabledApps.contains(app.bundleId) {
            startPolling(bundleId: app.bundleId)
        }

        print("[FlexDaemon] Attached to \(app.name) (pid \(app.pid), \(category.rawValue))")
    }

    private func detach(bundleId: String) {
        pollingTimers[bundleId]?.invalidate()
        pollingTimers.removeValue(forKey: bundleId)
        categories.removeValue(forKey: bundleId)
        appNames.removeValue(forKey: bundleId)
        pids.removeValue(forKey: bundleId)
        enabledApps.remove(bundleId)
        print("[FlexDaemon] Detached from \(bundleId)")
    }

    private func startPolling(bundleId: String) {
        pollingTimers[bundleId]?.invalidate()
        let timer = Timer.scheduledTimer(withTimeInterval: pollingInterval, repeats: true) { [weak self] _ in
            self?.extract(bundleId: bundleId)
        }
        pollingTimers[bundleId] = timer
        // Immediate extraction
        extract(bundleId: bundleId)
    }

    private func extract(bundleId: String) {
        guard !isPaused,
              enabledApps.contains(bundleId),
              let category = categories[bundleId],
              let pid = pids[bundleId],
              let appName = appNames[bundleId] else { return }

        switch category {
        case .chromium:
            if let tab = ChromiumHelper.extractActiveTab(appName: appName) {
                let content = "\(tab.title)\n\(tab.url)\n\(tab.text)"
                emitIfChanged(content: content, appName: appName, bundleId: bundleId, category: category)
            }
        case .electron, .safari, .generic:
            let windows = AXTreeHelper.getPerWindowTextTrees(pid: pid)
            for window in windows {
                emitIfChanged(content: window.text, appName: appName, bundleId: bundleId, category: category)
            }
        }
    }

    private func emitIfChanged(content: String, appName: String, bundleId: String, category: AppCategory) {
        let hashDigest = SHA256.hash(data: Data(content.utf8))
        let fullHash = hashDigest.map { String(format: "%02x", $0) }.joined()
        let short = hashDigest.prefix(8).map { String(format: "%02x", $0) }.joined()

        if hashStore.checkAndRecord(fullHash) {
            return
        }

        print("[FlexDaemon] Content changed: \(appName) (hash: \(short)...)")
        onContentChanged?(appName, bundleId, content, category, short)
    }

    public func flushState() {
        hashStore.saveNow()
    }
}
