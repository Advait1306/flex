import AppKit

public final class AccessibilityManager {
    private let diffEngine: DiffEngine
    private let outputPrinter: OutputPrinter
    private var pollingTimers: [String: Timer] = [:]           // bundleId -> timer
    private var extractors: [String: AppExtractor] = [:]       // bundleId -> extractor
    private var pids: [String: pid_t] = [:]                    // bundleId -> pid
    private var isPaused = false

    private let pollingInterval: TimeInterval = 5.0

    public init(diffEngine: DiffEngine, outputPrinter: OutputPrinter) {
        self.diffEngine = diffEngine
        self.outputPrinter = outputPrinter
    }

    public func updateMonitoredApps(_ apps: [MonitoredApp]) {
        let currentBundleIds = Set(apps.map(\.bundleId))
        let monitoredBundleIds = Set(extractors.keys)

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
        for (bundleId, _) in extractors {
            startPolling(bundleId: bundleId)
        }
    }

    // MARK: - Private

    private func attach(app: MonitoredApp) {
        pids[app.bundleId] = app.pid

        // Enable Chromium/Electron AX tree — makes all elements inspectable
        let axRef = AXUIElementCreateApplication(app.pid)
        AXUIElementSetAttributeValue(axRef, "AXManualAccessibility" as CFString, kCFBooleanTrue)

        let extractor: AppExtractor
        switch app.bundleId {
        case "com.tinyspeck.slackmacgap":
            extractor = SlackExtractor()
        case "com.linear":
            extractor = LinearExtractor()
        default:
            return
        }
        extractors[app.bundleId] = extractor

        // Start polling (AX extraction every 5s)
        if !isPaused {
            startPolling(bundleId: app.bundleId)
        }

        print("[FlexDaemon] Attached to \(app.name) (pid \(app.pid))")
    }

    private func detach(bundleId: String) {
        pollingTimers[bundleId]?.invalidate()
        pollingTimers.removeValue(forKey: bundleId)
        extractors.removeValue(forKey: bundleId)
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
              let extractor = extractors[bundleId],
              let pid = pids[bundleId] else { return }

        let items = extractor.extractContent(pid: pid)

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
