import Foundation

public struct DiffResult {
    public let outputText: String
    public let changeType: ChangeType
}

public final class DiffEngine {
    private var lastContent: [String: String] = [:]  // contextKey -> last content
    private let stateStore: StateStore

    public init() {
        stateStore = StateStore()
        lastContent = stateStore.load()
    }

    /// For testing: create a DiffEngine without state persistence.
    init(withoutPersistence: Bool) {
        stateStore = StateStore()
        if !withoutPersistence {
            lastContent = stateStore.load()
        }
    }

    /// Returns nil if content is unchanged, otherwise the diff result.
    public func diff(bundleId: String, item: ExtractedItem) -> DiffResult? {
        let key = "\(bundleId):\(item.contextId)"
        let newContent = item.text

        guard !newContent.isEmpty else { return nil }

        defer {
            lastContent[key] = newContent
            stateStore.scheduleSave(lastContent)
        }

        guard let previous = lastContent[key] else {
            return DiffResult(outputText: newContent, changeType: .new)
        }

        if newContent == previous {
            return nil
        }

        // Check if content is append-only (new content starts with previous content)
        if newContent.hasPrefix(previous) {
            let appendedPart = String(newContent.dropFirst(previous.count)).trimmingCharacters(in: .whitespacesAndNewlines)
            if !appendedPart.isEmpty {
                return DiffResult(outputText: appendedPart, changeType: .appended)
            }
            return nil
        }

        return DiffResult(outputText: newContent, changeType: .changed)
    }
}
