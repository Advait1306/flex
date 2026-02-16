import Foundation

public enum BackendClient {
    private static var baseURL: String {
        ProcessInfo.processInfo.environment["BACKEND_URL"] ?? "http://localhost:8000"
    }

    public static func validateCredentials(token: String) async throws -> Bool {
        guard let url = URL(string: "\(baseURL)/api/auth/check") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.setValue("Basic \(token)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 10

        let (_, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        switch httpResponse.statusCode {
        case 200: return true
        case 401: return false
        default: throw URLError(.badServerResponse)
        }
    }

    // MARK: - Daemon Snapshots

    public struct SnapshotPayload: Encodable {
        public let app_name: String
        public let bundle_id: String
        public let app_category: String
        public let content: String
        public let content_hash: String
    }

    public static func sendSnapshot(_ payload: SnapshotPayload, token: String) async throws {
        guard let url = URL(string: "\(baseURL)/api/daemon/snapshot") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Basic \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(payload)
        request.timeoutInterval = 30

        let (_, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw URLError(.badServerResponse)
        }
    }
}
