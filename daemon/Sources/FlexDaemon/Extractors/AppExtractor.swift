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

// MARK: - App classification

public enum AppCategory: String {
    case electron
    case safari
    case chromium
    case generic
}

public enum AppClassifier {
    private static let electronBundleIds: Set<String> = [
        "com.tinyspeck.slackmacgap",
        "com.linear",
        "com.microsoft.VSCode",
        "com.hnc.Discord",
        "com.figma.Desktop",
        "notion.id",
        "com.todesktop.230313mzl4w4u92",  // Cursor
    ]

    private static let chromiumBundleIds: Set<String> = [
        "com.google.Chrome",
        "com.brave.Browser",
        "com.microsoft.edgemac",
        "company.thebrowser.Browser",  // Arc
        "com.vivaldi.Vivaldi",
        "com.operasoftware.Opera",
    ]

    private static let safariBundleId = "com.apple.Safari"

    public static func classify(bundleId: String) -> AppCategory {
        if electronBundleIds.contains(bundleId) { return .electron }
        if chromiumBundleIds.contains(bundleId) { return .chromium }
        if bundleId == safariBundleId { return .safari }
        return .generic
    }

    public static func allKnownBundleIds() -> Set<String> {
        electronBundleIds.union(chromiumBundleIds).union([safariBundleId])
    }
}

// MARK: - Chromium AppleScript extraction

public enum ChromiumHelper {
    public struct TabContent {
        public let title: String
        public let url: String
        public let text: String
    }

    /// Extract the active tab from a Chromium browser via AppleScript.
    public static func extractActiveTab(appName: String) -> TabContent? {
        let script = """
        tell application "\(appName)"
            set t to active tab of front window
            set tabTitle to title of t
            set tabURL to URL of t
            set tabText to execute t javascript "document.body.innerText"
            return tabTitle & "<<<DELIM>>>" & tabURL & "<<<DELIM>>>" & tabText
        end tell
        """
        guard let result = runAppleScript(script) else { return nil }
        let parts = result.components(separatedBy: "<<<DELIM>>>")
        guard parts.count >= 3 else { return nil }
        return TabContent(title: parts[0], url: parts[1], text: parts.dropFirst(2).joined(separator: "<<<DELIM>>>"))
    }

    /// Extract all tabs from a Chromium browser via AppleScript.
    public static func extractAllTabs(appName: String) -> [TabContent] {
        let script = """
        tell application "\(appName)"
            set output to ""
            repeat with w in windows
                repeat with t in tabs of w
                    set tabTitle to title of t
                    set tabURL to URL of t
                    set tabText to execute t javascript "document.body.innerText"
                    set output to output & tabTitle & "<<<FIELD>>>" & tabURL & "<<<FIELD>>>" & tabText & "<<<TAB>>>"
                end repeat
            end repeat
            return output
        end tell
        """
        guard let result = runAppleScript(script) else { return [] }
        var tabs: [TabContent] = []
        for tabChunk in result.components(separatedBy: "<<<TAB>>>") {
            let fields = tabChunk.components(separatedBy: "<<<FIELD>>>")
            guard fields.count >= 3 else { continue }
            let title = fields[0]
            let url = fields[1]
            let text = fields.dropFirst(2).joined(separator: "<<<FIELD>>>")
            guard !title.isEmpty || !url.isEmpty else { continue }
            tabs.append(TabContent(title: title, url: url, text: text))
        }
        return tabs
    }

    private static func runAppleScript(_ source: String) -> String? {
        let script = NSAppleScript(source: source)
        var error: NSDictionary?
        let result = script?.executeAndReturnError(&error)
        if let error = error {
            print("[ChromiumHelper] AppleScript error: \(error)")
            return nil
        }
        return result?.stringValue
    }
}

// MARK: - Per-window content

public struct WindowContent {
    public let title: String
    public let text: String
}

// MARK: - AX tree helper

public enum AXTreeHelper {
    /// Roles that carry text content we care about
    private static let textRoles: Set<String> = [
        "AXStaticText",
        "AXLink", "AXHeading", "AXCell",
        "AXGenericElement", "AXButton",
    ]

    /// Roles for editable input fields — skip these entirely (content + children)
    /// to avoid triggering the pipeline on every keystroke
    private static let inputRoles: Set<String> = [
        "AXTextField", "AXTextArea",
    ]

    /// Roles that provide structural context (include if they have a meaningful name)
    private static let contextRoles: Set<String> = [
        "AXGroup", "AXList", "AXScrollArea", "AXWebArea",
    ]

    /// Extract each window's text tree independently as a `[WindowContent]`.
    public static func getPerWindowTextTrees(pid: pid_t) -> [WindowContent] {
        let appRef = AXUIElementCreateApplication(pid)
        let windows = getAllWindows(appRef)
        var results: [WindowContent] = []
        for (i, window) in windows.enumerated() {
            let title = getString(window, kAXTitleAttribute) ?? "Window \(i + 1)"
            var lines: [String] = []
            walkTextTree(window, into: &lines, depth: 0, maxDepth: 50)
            let text = lines.joined(separator: "\n")
            if !text.isEmpty {
                results.append(WindowContent(title: title, text: text))
            }
        }
        return results
    }

    /// Dump the raw AX tree with all roles and attributes (for debugging).
    public static func getRawTree(pid: pid_t) -> String {
        let appRef = AXUIElementCreateApplication(pid)
        let windows = getAllWindows(appRef)
        guard !windows.isEmpty else { return "" }

        var lines: [String] = []
        for (i, window) in windows.enumerated() {
            let title = getString(window, kAXTitleAttribute) ?? "Window \(i + 1)"
            if i > 0 { lines.append("") }
            lines.append("[\(title)]:")
            walkRawTree(window, into: &lines, depth: 1, maxDepth: 50)
        }
        return lines.joined(separator: "\n")
    }

    private static func walkRawTree(_ element: AXUIElement, into lines: inout [String], depth: Int, maxDepth: Int) {
        guard depth < maxDepth else { return }

        let role = getString(element, kAXRoleAttribute) ?? "?"
        let title = getString(element, kAXTitleAttribute)
        let value = getString(element, kAXValueAttribute)
        let desc = getString(element, kAXDescriptionAttribute)

        let indent = String(repeating: "  ", count: depth)
        var parts = [role]
        if let t = title { parts.append("title=\"\(t.prefix(80))\"") }
        if let v = value { parts.append("value=\"\(v.prefix(80))\"") }
        if let d = desc { parts.append("desc=\"\(d.prefix(80))\"") }
        lines.append("\(indent)\(parts.joined(separator: " | "))")

        let children = getChildren(element)
        for child in children {
            walkRawTree(child, into: &lines, depth: depth + 1, maxDepth: maxDepth)
        }
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

        // Skip input fields entirely — their changing values trigger
        // the pipeline on every keystroke (e.g. typing in Slack)
        if inputRoles.contains(role) { return }

        let title = getString(element, kAXTitleAttribute) ?? ""
        let value = getString(element, kAXValueAttribute) ?? ""
        let description = getString(element, kAXDescriptionAttribute) ?? ""

        let indent = String(repeating: "  ", count: depth)

        if textRoles.contains(role) {
            // Text element — emit its content
            let text = !value.isEmpty ? value : (!title.isEmpty ? title : description)
            if !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                let marker = roleMarker(role)
                lines.append("\(indent)- \(marker)\(text)")
            }
        } else if contextRoles.contains(role) {
            // Structural element — emit name as context header if present
            let name = !title.isEmpty ? title : description
            if !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                lines.append("\(indent)\(name):")
            }
        }

        // Recurse into children to find nested text
        let children = getChildren(element)
        for child in children {
            walkTextTree(child, into: &lines, depth: depth + 1, maxDepth: maxDepth)
        }
    }

    private static func roleMarker(_ role: String) -> String {
        switch role {
        case "AXButton":         return "[Button] "
        case "AXLink":           return "[Link] "
        case "AXHeading":        return "[Heading] "
        case "AXCell":           return "[Cell] "
        case "AXStaticText":     return ""
        case "AXGenericElement": return ""
        default:                 return ""
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
