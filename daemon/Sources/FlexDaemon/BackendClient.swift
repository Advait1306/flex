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
}
