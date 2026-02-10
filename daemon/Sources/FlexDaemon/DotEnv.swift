import Foundation

public enum DotEnv {
    public static func load(path: String? = nil) {
        let filePath = path ?? findEnvFile()
        guard let filePath, let contents = try? String(contentsOfFile: filePath, encoding: .utf8) else {
            return
        }

        for line in contents.components(separatedBy: .newlines) {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty || trimmed.hasPrefix("#") { continue }

            guard let eqIndex = trimmed.firstIndex(of: "=") else { continue }
            let key = String(trimmed[trimmed.startIndex..<eqIndex]).trimmingCharacters(in: .whitespaces)
            var value = String(trimmed[trimmed.index(after: eqIndex)...]).trimmingCharacters(in: .whitespaces)

            // Strip matching quotes
            if (value.hasPrefix("\"") && value.hasSuffix("\"")) ||
               (value.hasPrefix("'") && value.hasSuffix("'")) {
                value = String(value.dropFirst().dropLast())
            }

            // Don't override existing env vars
            if ProcessInfo.processInfo.environment[key] == nil {
                setenv(key, value, 0)
            }
        }
    }

    private static func findEnvFile() -> String? {
        // Look next to the executable, then in current directory
        let execDir = (CommandLine.arguments[0] as NSString).deletingLastPathComponent
        let candidates = [
            "\(execDir)/.env",
            ".env",
        ]
        return candidates.first { FileManager.default.fileExists(atPath: $0) }
    }
}
