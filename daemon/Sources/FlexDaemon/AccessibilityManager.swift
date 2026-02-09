import AppKit

public final class AccessibilityManager {
    private let diffEngine: DiffEngine
    private let outputPrinter: OutputPrinter
    private var pollingTimers: [String: Timer] = [:]           // bundleId -> timer
    private var categories: [String: AppCategory] = [:]        // bundleId -> category
    private var appNames: [String: String] = [:]               // bundleId -> display name
    private var pids: [String: pid_t] = [:]                    // bundleId -> pid
    private var isPaused = false

    private let pollingInterval: TimeInterval = 5.0

    public init(diffEngine: DiffEngine, outputPrinter: OutputPrinter) {
        self.diffEngine = diffEngine
        self.outputPrinter = outputPrinter
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

    public func pause() {
        isPaused = true
        for (_, timer) in pollingTimers {
            timer.invalidate()
        }
        pollingTimers.removeAll()
    }

    public func resume() {
        isPaused = false
        for (bundleId, _) in categories {
            startPolling(bundleId: bundleId)
        }
    }

    // MARK: - Private

    private func attach(app: MonitoredApp) {
        let category = AppClassifier.classify(bundleId: app.bundleId)
        pids[app.bundleId] = app.pid
        categories[app.bundleId] = category
        appNames[app.bundleId] = app.name

        // Only Electron apps need AXManualAccessibility enabled
        if category == .electron {
            let axRef = AXUIElementCreateApplication(app.pid)
            AXUIElementSetAttributeValue(axRef, "AXManualAccessibility" as CFString, kCFBooleanTrue)
        }

        // Start polling
        if !isPaused {
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
              let category = categories[bundleId],
              let pid = pids[bundleId],
              let appName = appNames[bundleId] else { return }

        let items: [ExtractedItem]

        switch category {
        case .chromium:
            if let tab = ChromiumHelper.extractActiveTab(appName: appName) {
                items = [ExtractedItem(text: tab.text, contextId: bundleId, context: "\(tab.title) — \(tab.url)")]
            } else {
                items = []
            }
        case .electron, .safari, .generic:
            let windowTitle = AXTreeHelper.windowTitle(pid: pid) ?? appName
            let tree = AXTreeHelper.getTextTree(pid: pid)
            if tree.isEmpty {
                items = []
            } else {
                items = [ExtractedItem(text: tree, contextId: bundleId, context: windowTitle)]
            }
        }

        if items.isEmpty {
            print("[FlexDaemon] No items from \(bundleId)")
            return
        }

        print("[FlexDaemon] Got \(items.count) item(s) from \(bundleId)")
        for item in items {
            guard !item.text.isEmpty else { continue }
            outputPrinter.printCapture(item: item, source: bundleId, changeType: .new)
        }
    }
}
