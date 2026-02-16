// Uses AppKit directly (not SwiftUI) because the daemon runs on an NSApplication
// lifecycle with no main window. Could wrap in NSHostingController, but these are
// simple one-off onboarding screens where SwiftUI adds a dependency for minimal benefit.

import AppKit

public class LoginWindowController: NSObject, NSWindowDelegate {
    private var window: NSWindow!
    private var usernameField: NSTextField!
    private var passwordField: NSSecureTextField!
    private var errorLabel: NSTextField!
    private var spinner: NSProgressIndicator!
    private var signInButton: NSButton!
    private var didSucceed = false
    public var onSuccess: ((String) -> Void)?

    public func show() {
        let width: CGFloat = 400
        let height: CGFloat = 260

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: width, height: height),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = "Sign in to Flex"
        window.center()
        window.delegate = self
        window.isReleasedWhenClosed = false

        let contentView = NSView(frame: NSRect(x: 0, y: 0, width: width, height: height))
        window.contentView = contentView

        // Title
        let title = NSTextField(labelWithString: "Sign in to Flex")
        title.translatesAutoresizingMaskIntoConstraints = false
        title.font = .boldSystemFont(ofSize: 18)
        title.alignment = .center
        contentView.addSubview(title)

        // Username
        usernameField = NSTextField()
        usernameField.translatesAutoresizingMaskIntoConstraints = false
        usernameField.placeholderString = "Username"
        usernameField.controlSize = .large
        usernameField.font = .systemFont(ofSize: 14)
        contentView.addSubview(usernameField)

        // Password
        passwordField = NSSecureTextField()
        passwordField.translatesAutoresizingMaskIntoConstraints = false
        passwordField.placeholderString = "Password"
        passwordField.controlSize = .large
        passwordField.font = .systemFont(ofSize: 14)
        contentView.addSubview(passwordField)

        // Error label (hidden by default)
        errorLabel = NSTextField(labelWithString: "")
        errorLabel.translatesAutoresizingMaskIntoConstraints = false
        errorLabel.textColor = .systemRed
        errorLabel.font = .systemFont(ofSize: 12)
        errorLabel.alignment = .center
        errorLabel.isHidden = true
        contentView.addSubview(errorLabel)

        // Spinner (hidden by default)
        spinner = NSProgressIndicator()
        spinner.translatesAutoresizingMaskIntoConstraints = false
        spinner.style = .spinning
        spinner.controlSize = .small
        spinner.isHidden = true
        contentView.addSubview(spinner)

        // Sign in button
        signInButton = NSButton(title: "Sign In", target: self, action: #selector(signIn))
        signInButton.translatesAutoresizingMaskIntoConstraints = false
        signInButton.bezelStyle = .rounded
        signInButton.controlSize = .large
        signInButton.keyEquivalent = "\r"
        contentView.addSubview(signInButton)

        NSLayoutConstraint.activate([
            title.centerXAnchor.constraint(equalTo: contentView.centerXAnchor),
            title.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 25),

            usernameField.topAnchor.constraint(equalTo: title.bottomAnchor, constant: 20),
            usernameField.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 50),
            usernameField.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -50),

            passwordField.topAnchor.constraint(equalTo: usernameField.bottomAnchor, constant: 12),
            passwordField.leadingAnchor.constraint(equalTo: usernameField.leadingAnchor),
            passwordField.trailingAnchor.constraint(equalTo: usernameField.trailingAnchor),

            errorLabel.topAnchor.constraint(equalTo: passwordField.bottomAnchor, constant: 8),
            errorLabel.leadingAnchor.constraint(equalTo: usernameField.leadingAnchor),
            errorLabel.trailingAnchor.constraint(equalTo: usernameField.trailingAnchor),

            spinner.centerXAnchor.constraint(equalTo: contentView.centerXAnchor),
            spinner.topAnchor.constraint(equalTo: errorLabel.bottomAnchor, constant: 8),

            signInButton.centerXAnchor.constraint(equalTo: contentView.centerXAnchor),
            signInButton.topAnchor.constraint(equalTo: spinner.bottomAnchor, constant: 8),
        ])

        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        window.makeFirstResponder(usernameField)
    }

    @objc private func signIn() {
        let username = usernameField.stringValue.trimmingCharacters(in: .whitespaces)
        let password = passwordField.stringValue

        guard !username.isEmpty, !password.isEmpty else {
            showError("Please enter username and password.")
            return
        }

        setLoading(true)
        errorLabel.isHidden = true

        let token = Data("\(username):\(password)".utf8).base64EncodedString()

        Task {
            do {
                let valid = try await BackendClient.validateCredentials(token: token)
                await MainActor.run {
                    self.setLoading(false)
                    if valid {
                        self.handleSuccess(token: token)
                    } else {
                        self.showError("Invalid username or password.")
                    }
                }
            } catch {
                await MainActor.run {
                    self.setLoading(false)
                    self.showError("Could not connect to server.")
                }
            }
        }
    }

    private func handleSuccess(token: String) {
        do {
            try KeychainHelper.saveToken(token)
        } catch {
            print("[FlexDaemon] Warning: could not save token to Keychain: \(error)")
        }
        didSucceed = true
        window.close()
        onSuccess?(token)
    }

    private func showError(_ message: String) {
        errorLabel.stringValue = message
        errorLabel.isHidden = false
    }

    private func setLoading(_ loading: Bool) {
        spinner.isHidden = !loading
        if loading { spinner.startAnimation(nil) } else { spinner.stopAnimation(nil) }
        signInButton.isEnabled = !loading
        usernameField.isEnabled = !loading
        passwordField.isEnabled = !loading
    }

    // MARK: - NSWindowDelegate

    public func windowWillClose(_ notification: Notification) {
        if !didSucceed {
            NSApplication.shared.terminate(nil)
        }
    }
}
