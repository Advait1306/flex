import AppKit
import AXSwift

public struct ExtractedItem {
    public let text: String
    public let contextId: String
    public let context: String

    public init(text: String, contextId: String, context: String) {
        self.text = text
        self.contextId = contextId
        self.context = context
    }
}

protocol AppExtractor {
    var bundleId: String { get }
    var processName: String { get }
    func extractContent(pid: pid_t) -> [ExtractedItem]
}

// MARK: - AX tree helper

public enum AXTreeHelper {
    /// Roles that carry text content we care about
    private static let textRoles: Set<String> = [
        "AXStaticText", "AXTextField", "AXTextArea",
        "AXLink", "AXHeading", "AXCell",
    ]

    /// Roles that provide structural context (include if they have a meaningful name)
    private static let contextRoles: Set<String> = [
        "AXGroup", "AXList", "AXScrollArea", "AXWebArea",
    ]

    /// Walk the AX tree of all windows and return a YAML-like indented tree of text content.
    public static func getTextTree(pid: pid_t) -> String {
        let appRef = AXUIElementCreateApplication(pid)
        let windows = getAllWindows(appRef)
        guard !windows.isEmpty else { return "" }

        var lines: [String] = []
        for (i, window) in windows.enumerated() {
            let title = getString(window, kAXTitleAttribute) ?? "Window \(i + 1)"
            if windows.count > 1 {
                if i > 0 { lines.append("") }
                lines.append("[\(title)]:")
                walkTextTree(window, into: &lines, depth: 1, maxDepth: 50)
            } else {
                walkTextTree(window, into: &lines, depth: 0, maxDepth: 50)
            }
        }
        return lines.joined(separator: "\n")
    }

    /// Get the window title via AX API (from focused or first window).
    public static func windowTitle(pid: pid_t) -> String? {
        let appRef = AXUIElementCreateApplication(pid)
        if let window = getFocusedWindow(appRef) {
            return getString(window, kAXTitleAttribute)
        }
        let windows = getAllWindows(appRef)
        for window in windows {
            if let title = getString(window, kAXTitleAttribute) {
                return title
            }
        }
        return nil
    }

    // MARK: - Private

    private static func getFocusedWindow(_ appRef: AXUIElement) -> AXUIElement? {
        var value: CFTypeRef?
        let err = AXUIElementCopyAttributeValue(appRef, kAXFocusedWindowAttribute as CFString, &value)
        guard err == .success else { return nil }
        return (value as! AXUIElement)
    }

    private static func getAllWindows(_ appRef: AXUIElement) -> [AXUIElement] {
        var value: CFTypeRef?
        let err = AXUIElementCopyAttributeValue(appRef, kAXWindowsAttribute as CFString, &value)
        guard err == .success, let windows = value as? [AXUIElement] else { return [] }
        return windows
    }

    private static func walkTextTree(_ element: AXUIElement, into lines: inout [String], depth: Int, maxDepth: Int) {
        guard depth < maxDepth else { return }

        let role = getString(element, kAXRoleAttribute) ?? ""
        let title = getString(element, kAXTitleAttribute) ?? ""
        let value = getString(element, kAXValueAttribute) ?? ""
        let description = getString(element, kAXDescriptionAttribute) ?? ""

        let indent = String(repeating: "  ", count: depth)

        if textRoles.contains(role) {
            // Text element — emit its content
            let text = !value.isEmpty ? value : (!title.isEmpty ? title : description)
            if !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                lines.append("\(indent)- \(text)")
            }
        } else if contextRoles.contains(role) {
            // Structural element — emit name as context header if present
            let name = !title.isEmpty ? title : description
            if !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                lines.append("\(indent)\(name):")
            }
        }

        // Always recurse into children to find nested text
        let children = getChildren(element)
        for child in children {
            walkTextTree(child, into: &lines, depth: depth + 1, maxDepth: maxDepth)
        }
    }

    private static func getString(_ element: AXUIElement, _ attribute: String) -> String? {
        var value: CFTypeRef?
        let err = AXUIElementCopyAttributeValue(element, attribute as CFString, &value)
        guard err == .success, let str = value as? String, !str.isEmpty else { return nil }
        return str
    }

    private static func getChildren(_ element: AXUIElement) -> [AXUIElement] {
        var value: CFTypeRef?
        let err = AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &value)
        guard err == .success, let children = value as? [AXUIElement] else { return [] }
        return children
    }
}
