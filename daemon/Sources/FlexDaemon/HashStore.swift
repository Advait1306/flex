import Foundation

final class HashStore {
    private var seenHashes: Set<String> = []
    private let fileURL: URL
    private var saveTimer: Timer?
    private let debounceInterval: TimeInterval = 2.0

    init() {
        let configDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".config/flex")
        try? FileManager.default.createDirectory(at: configDir, withIntermediateDirectories: true)
        fileURL = configDir.appendingPathComponent("seen-hashes.json")
    }

    func load() {
        guard let data = try? Data(contentsOf: fileURL),
              let hashes = try? JSONDecoder().decode([String].self, from: data)
        else { return }
        seenHashes = Set(hashes)
        print("[FlexDaemon] Loaded \(seenHashes.count) seen hashes from disk")
    }

    /// Returns `true` if the hash was already seen (duplicate).
    func checkAndRecord(_ hash: String) -> Bool {
        let (inserted, _) = seenHashes.insert(hash)
        if inserted {
            scheduleSave()
            return false
        }
        return true
    }

    func saveNow() {
        saveTimer?.invalidate()
        saveTimer = nil
        save()
    }

    private func scheduleSave() {
        saveTimer?.invalidate()
        saveTimer = Timer.scheduledTimer(withTimeInterval: debounceInterval, repeats: false) { [weak self] _ in
            self?.save()
        }
    }

    private func save() {
        let array = Array(seenHashes)
        guard let data = try? JSONEncoder().encode(array) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }
}
