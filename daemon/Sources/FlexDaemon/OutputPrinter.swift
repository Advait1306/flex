import Foundation
import os.log

public final class OutputPrinter {
    private let logger = Logger(subsystem: "com.flex.daemon", category: "capture")

    public init() {}

    public func printCapture(item: ExtractedItem, source: String, changeType: ChangeType) {
        let timestamp = ISO8601DateFormatter().string(from: Date())
        let label: String
        switch changeType {
        case .new:
            label = "NEW"
        case .changed:
            label = "CHANGED"
        case .appended:
            label = "APPENDED"
        }

        let output = """
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        [\(timestamp)] \(label) content from \(source)
        Context: \(item.context)
        ──────────────────────────────────────────
        \(item.text)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
        print(output)
        logger.info("\(label) content from \(source) — \(item.context): \(item.text.prefix(200))")
    }
}

public enum ChangeType {
    case new
    case changed
    case appended
}
