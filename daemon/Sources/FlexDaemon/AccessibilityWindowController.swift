// Uses AppKit directly (not SwiftUI) because the daemon runs on an NSApplication
// lifecycle with no main window. Could wrap in NSHostingController, but these are
// simple one-off onboarding screens where SwiftUI adds a dependency for minimal benefit.

import AppKit
import AXSwift

public class AccessibilityWindowController: NSObject, NSWindowDelegate {
    private var window: NSWindow!
    private var statusLabel: NSTextField!
    private var pollTimer: Timer?
    public var onGranted: (() -> Void)?

    public func show() {
        let width: CGFloat = 480
        let height: CGFloat = 280

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: width, height: height),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = "Flex Daemon"
        window.center()
        window.delegate = self
        window.isReleasedWhenClosed = false

        let contentView = NSView(frame: NSRect(x: 0, y: 0, width: width, height: height))
        window.contentView = contentView

        // Shield icon
        let icon = NSImageView()
        icon.translatesAutoresizingMaskIntoConstraints = false
        icon.image = NSImage(systemSymbolName: "lock.shield", accessibilityDescription: "Lock shield")
        icon.symbolConfiguration = NSImage.SymbolConfiguration(pointSize: 40, weight: .regular)
        icon.contentTintColor = .systemBlue
        contentView.addSubview(icon)

        // Title
        let title = NSTextField(labelWithString: "Accessibility Permission Required")
        title.translatesAutoresizingMaskIntoConstraints = false
        title.font = .boldSystemFont(ofSize: 18)
        title.alignment = .center
        contentView.addSubview(title)

        // Body
        let body = NSTextField(wrappingLabelWithString:
            "Flex Daemon needs Accessibility access to read content from your apps. " +
            "Grant permission in System Settings, then this window will close automatically."
        )
        body.translatesAutoresizingMaskIntoConstraints = false
        body.alignment = .center
        body.textColor = .secondaryLabelColor
        contentView.addSubview(body)

        // Open System Settings button
        let button = NSButton(title: "Open System Settings", target: self, action: #selector(openSettings))
        button.translatesAutoresizingMaskIntoConstraints = false
        button.bezelStyle = .rounded
        button.controlSize = .large
        contentView.addSubview(button)

        // Status label
        statusLabel = NSTextField(labelWithString: "Waiting for permission...")
        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        statusLabel.alignment = .center
        statusLabel.textColor = .tertiaryLabelColor
        statusLabel.font = .systemFont(ofSize: 12)
        contentView.addSubview(statusLabel)

        NSLayoutConstraint.activate([
            icon.centerXAnchor.constraint(equalTo: contentView.centerXAnchor),
            icon.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 30),

            title.centerXAnchor.constraint(equalTo: contentView.centerXAnchor),
            title.topAnchor.constraint(equalTo: icon.bottomAnchor, constant: 16),
            title.leadingAnchor.constraint(greaterThanOrEqualTo: contentView.leadingAnchor, constant: 20),
            title.trailingAnchor.constraint(lessThanOrEqualTo: contentView.trailingAnchor, constant: -20),

            body.centerXAnchor.constraint(equalTo: contentView.centerXAnchor),
            body.topAnchor.constraint(equalTo: title.bottomAnchor, constant: 10),
            body.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 30),
            body.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -30),

            button.centerXAnchor.constraint(equalTo: contentView.centerXAnchor),
            button.topAnchor.constraint(equalTo: body.bottomAnchor, constant: 20),

            statusLabel.centerXAnchor.constraint(equalTo: contentView.centerXAnchor),
            statusLabel.topAnchor.constraint(equalTo: button.bottomAnchor, constant: 12),
        ])

        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        startPolling()
    }

    private func startPolling() {
        pollTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            if UIElement.isProcessTrusted(withPrompt: false) {
                self?.permissionGranted()
            }
        }
    }

    private func permissionGranted() {
        pollTimer?.invalidate()
        pollTimer = nil
        window.close()
        onGranted?()
    }

    @objc private func openSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
            NSWorkspace.shared.open(url)
        }
    }

    // MARK: - NSWindowDelegate

    public func windowWillClose(_ notification: Notification) {
        // If the user closes the window before granting permission, quit
        if pollTimer != nil {
            pollTimer?.invalidate()
            pollTimer = nil
            NSApplication.shared.terminate(nil)
        }
    }
}
