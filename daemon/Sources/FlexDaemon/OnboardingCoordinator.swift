import AppKit
import AXSwift

public class OnboardingCoordinator {
    private var loginController: LoginWindowController?
    private var accessibilityController: AccessibilityWindowController?
    private var onComplete: ((String) -> Void)?
    private var token: String?

    public init() {}

    public func start(onComplete: @escaping (String) -> Void) {
        self.onComplete = onComplete

        // Show as regular app during onboarding (dock icon + focus)
        NSApp.setActivationPolicy(.regular)

        checkCredentials()
    }

    private func checkCredentials() {
        if let storedToken = KeychainHelper.loadToken() {
            // Validate stored token in background
            Task {
                do {
                    let valid = try await BackendClient.validateCredentials(token: storedToken)
                    await MainActor.run {
                        if valid {
                            self.token = storedToken
                            self.checkAccessibility()
                        } else {
                            // Stored token is invalid, show login
                            KeychainHelper.deleteToken()
                            self.showLogin()
                        }
                    }
                } catch {
                    // Backend unreachable but we have a stored token — proceed anyway
                    await MainActor.run {
                        print("[FlexDaemon] Backend unreachable, using stored credentials")
                        self.token = storedToken
                        self.checkAccessibility()
                    }
                }
            }
        } else {
            showLogin()
        }
    }

    private func showLogin() {
        loginController = LoginWindowController()
        loginController?.onSuccess = { [weak self] token in
            self?.loginController = nil
            self?.token = token
            self?.checkAccessibility()
        }
        loginController?.show()
    }

    private func checkAccessibility() {
        if UIElement.isProcessTrusted(withPrompt: true) {
            finishOnboarding()
        } else {
            showAccessibilityWindow()
        }
    }

    private func showAccessibilityWindow() {
        accessibilityController = AccessibilityWindowController()
        accessibilityController?.onGranted = { [weak self] in
            self?.accessibilityController = nil
            self?.finishOnboarding()
        }
        accessibilityController?.show()
    }

    private func finishOnboarding() {
        // Switch to accessory (menu bar only) mode
        NSApp.setActivationPolicy(.accessory)

        guard let token = token else { return }
        onComplete?(token)
    }
}
