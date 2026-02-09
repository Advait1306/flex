import Foundation

final class StateStore {
    private let fileURL: URL
    private var saveTimer: Timer?
    private let debounceInterval: TimeInterval = 2.0
    private let maxAge: TimeInterval = 7 * 24 * 60 * 60  // 7 days

    struct Entry: Codable {
        let content: String
        let timestamp: Date
    }

    init() {
        let configDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".config/flex")
        try? FileManager.default.createDirectory(at: configDir, withIntermediateDirectories: true)
        fileURL = configDir.appendingPathComponent("daemon-state.json")
    }

    func load() -> [String: String] {
        guard let data = try? Data(contentsOf: fileURL),
              let entries = try? JSONDecoder.withISO8601.decode([String: Entry].self, from: data)
        else { return [:] }

        let now = Date()
        var result: [String: String] = [:]
        for (key, entry) in entries {
            if now.timeIntervalSince(entry.timestamp) < maxAge {
                result[key] = entry.content
            }
        }
        return result
    }

    func scheduleSave(_ content: [String: String]) {
        saveTimer?.invalidate()
        saveTimer = Timer.scheduledTimer(withTimeInterval: debounceInterval, repeats: false) { [weak self] _ in
            self?.save(content)
        }
    }

    private func save(_ content: [String: String]) {
        let now = Date()
        let entries = content.mapValues { Entry(content: $0, timestamp: now) }
        guard let data = try? JSONEncoder.withISO8601.encode(entries) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }
}

extension JSONDecoder {
    static let withISO8601: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()
}

extension JSONEncoder {
    static let withISO8601: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = .prettyPrinted
        return encoder
    }()
}
